"""Resilient video and RTSP stream capture handler with auto-reconnection."""
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union, Dict, Any, Callable
import cv2
import numpy as np

from video.camera_config import (
    CameraConfig,
    CameraConnectionStatus,
    StreamType,
    mask_credentials,
)
from video.frame_buffer import BoundedFrameBuffer

logger = logging.getLogger("stream_capture")


class StreamCapture:
    """Manages low-latency frame ingestion from an RTSP stream, local video file, or webcam."""

    def __init__(
        self,
        config: CameraConfig,
        buffer: Optional[BoundedFrameBuffer] = None,
        loop_file: bool = True,
        on_status_change: Optional[Callable[[str, CameraConnectionStatus], None]] = None,
        capture_factory: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self.config = config
        self.camera_id = config.camera_id
        self.buffer = buffer or BoundedFrameBuffer(maxsize=config.buffer_size)
        self.loop_file = loop_file
        self.on_status_change = on_status_change
        self.capture_factory = capture_factory

        self._status: CameraConnectionStatus = CameraConnectionStatus.DISCONNECTED
        self._status_lock = threading.Lock()

        self._cap: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Telemetry
        self.native_fps: float = 0.0
        self.measured_fps: float = 0.0
        self.frame_width: int = 0
        self.frame_height: int = 0
        self.total_captured_frames: int = 0
        self.reconnect_count: int = 0
        self.last_frame_time: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.start_time: Optional[datetime] = None

    @property
    def status(self) -> CameraConnectionStatus:
        with self._status_lock:
            return self._status

    def _set_status(self, new_status: CameraConnectionStatus, error_msg: Optional[str] = None) -> None:
        with self._status_lock:
            old_status = self._status
            self._status = new_status
            if error_msg:
                self.last_error = error_msg
        if old_status != new_status:
            logger.info("[%s] Status change: %s -> %s", self.camera_id, old_status.value, new_status.value)
            if self.on_status_change:
                try:
                    self.on_status_change(self.camera_id, new_status)
                except Exception as e:
                    logger.error("[%s] Error in on_status_change callback: %s", self.camera_id, e)

    def _open_capture(self) -> bool:
        """Opens video capture using provided factory or cv2.VideoCapture."""
        url = self.config.rtsp_url

        try:
            if self.capture_factory is not None:
                cap = self.capture_factory(url)
                if cap is None or not getattr(cap, "isOpened", lambda: True)():
                    self.last_error = f"Failed to open stream via factory: {self.config.safe_url}"
                    return False
                self._cap = cap
                self.native_fps = getattr(cap, "fps", 25.0)
                self.frame_width = getattr(cap, "width", 640)
                self.frame_height = getattr(cap, "height", 480)
                return True

            if self.config.stream_type == StreamType.WEBCAM:
                device_idx = int(url)
                cap = cv2.VideoCapture(device_idx)
            elif self.config.stream_type == StreamType.RTSP:
                os_env_flags = cv2.CAP_FFMPEG
                cap = cv2.VideoCapture(url, os_env_flags)
            else:
                cap = cv2.VideoCapture(url)

            if not cap.isOpened():
                self.last_error = f"Failed to open stream: {self.config.safe_url}"
                return False

            self.native_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            if self.native_fps <= 0 or self.native_fps > 120:
                self.native_fps = 25.0

            self.frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self._cap = cap
            return True
        except Exception as e:
            self.last_error = f"Exception opening stream: {e}"
            return False

    def _release_capture(self) -> None:
        """Safely closes capture handle."""
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def start(self) -> None:
        """Starts background ingestion thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("[%s] StreamCapture is already running", self.camera_id)
            return

        self._stop_event.clear()
        self.start_time = datetime.now(timezone.utc)
        self._thread = threading.Thread(
            target=self._capture_loop,
            name=f"Capture-{self.camera_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info("[%s] Ingestion thread started for %s", self.camera_id, self.config.safe_url)

    def stop(self, timeout: float = 2.0) -> None:
        """Stops background ingestion and releases resources."""
        self._stop_event.set()
        self._set_status(CameraConnectionStatus.STOPPED)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

        self._release_capture()
        self.buffer.close()
        logger.info("[%s] StreamCapture stopped gracefully", self.camera_id)

    def _capture_loop(self) -> None:
        """Core frame grabbing and auto-reconnect loop."""
        consecutive_failures = 0
        frame_index = 0
        fps_frame_count = 0
        fps_start_time = time.perf_counter()

        while not self._stop_event.is_set():
            if self._cap is None or not getattr(self._cap, "isOpened", lambda: True)():
                if self._open_capture():
                    self._set_status(CameraConnectionStatus.CONNECTED)
                    consecutive_failures = 0
                else:
                    connected = self._handle_reconnect()
                    if not connected:
                        break
                    consecutive_failures = 0

            ret, frame = self._cap.read()

            if not ret or frame is None:
                consecutive_failures += 1

                # Local file handling when loop_file is disabled
                if self.config.stream_type == StreamType.FILE and not self.loop_file:
                    self._release_capture()
                    self._set_status(CameraConnectionStatus.DISCONNECTED, "File EOF reached")
                    break

                # Local file looping
                if self.config.stream_type == StreamType.FILE and self.loop_file and not self._stop_event.is_set():
                    try:
                        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        consecutive_failures = 0
                        time.sleep(0.01)
                        continue
                    except Exception:
                        pass

                if consecutive_failures >= 3:
                    self._release_capture()
                    self._set_status(CameraConnectionStatus.DISCONNECTED, "Stream disconnected or frame read error")
                    continue
                else:
                    time.sleep(0.02)
                    continue

            # Frame successfully acquired
            consecutive_failures = 0
            now = datetime.now(timezone.utc)
            self.last_frame_time = now
            frame_index += 1
            self.total_captured_frames += 1

            # Update live FPS measurement
            fps_frame_count += 1
            if fps_frame_count >= 15:
                elapsed = time.perf_counter() - fps_start_time
                if elapsed > 0:
                    self.measured_fps = round(fps_frame_count / elapsed, 1)
                fps_frame_count = 0
                fps_start_time = time.perf_counter()

            # Enqueue to ring buffer (drops stale frame if full)
            self.buffer.put(frame, frame_index, now)

            # Frame interval sleep for local file streams
            if self.config.stream_type == StreamType.FILE and self.native_fps > 0:
                frame_interval = 1.0 / self.native_fps
                time.sleep(frame_interval * 0.90)

    def _handle_reconnect(self) -> bool:
        """Executes exponential backoff reconnection up to max_reconnect_attempts."""
        attempt = 0
        max_attempts = self.config.reconnect_attempts
        delay = self.config.reconnect_delay
        backoff = self.config.backoff_factor

        while attempt < max_attempts and not self._stop_event.is_set():
            attempt += 1
            self.reconnect_count += 1
            self._set_status(
                CameraConnectionStatus.RECONNECTING,
                f"Reconnect attempt {attempt}/{max_attempts}",
            )
            logger.info(
                "[%s] Attempting reconnect (%d/%d) in %.2fs to %s",
                self.camera_id,
                attempt,
                max_attempts,
                delay,
                self.config.safe_url,
            )

            # Sleep with interruptible checks
            wake_time = time.time() + delay
            while time.time() < wake_time and not self._stop_event.is_set():
                time.sleep(0.02)

            if self._stop_event.is_set():
                return False

            if self._open_capture():
                self._set_status(CameraConnectionStatus.CONNECTED)
                logger.info("[%s] Reconnected successfully to %s", self.camera_id, self.config.safe_url)
                return True

            delay = min(delay * backoff, 30.0)

        # Max retries exhausted
        if not self._stop_event.is_set():
            err_msg = f"Failed to connect after {max_attempts} attempts to {self.config.safe_url}"
            self._set_status(CameraConnectionStatus.ERROR, err_msg)
            logger.error("[%s] %s", self.camera_id, err_msg)
        return False
