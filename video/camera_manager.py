"""Multi-Camera Stream Manager and isolated worker threads with health telemetry."""
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable
import numpy as np

from video.camera_config import CameraConfig, CameraConnectionStatus
from video.frame_buffer import BoundedFrameBuffer
from video.stream_capture import StreamCapture
from video.ai_router import AIRouter, CameraFrameAIResult

logger = logging.getLogger("camera_manager")


class CameraWorker:
    """Isolated processing worker for a single camera stream.
    
    Owns:
    1. StreamCapture thread (pulls RTSP/video into BoundedFrameBuffer)
    2. Processing thread (consumes, samples at target FPS, routes to AI)
    """

    def __init__(
        self,
        config: CameraConfig,
        router: Optional[AIRouter] = None,
        on_result: Optional[Callable[[CameraFrameAIResult], None]] = None,
        loop_file: bool = True,
        capture_factory: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self.config = config
        self.camera_id = config.camera_id
        self.router = router or AIRouter()
        self.on_result = on_result

        # Internal buffer & capture handler
        self.buffer = BoundedFrameBuffer(maxsize=config.buffer_size)
        self.capture = StreamCapture(
            config=config,
            buffer=self.buffer,
            loop_file=loop_file,
            on_status_change=self._on_connection_change,
            capture_factory=capture_factory,
        )

        self._proc_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Telemetry metrics
        self.frames_processed: int = 0
        self.frames_skipped_by_sampling: int = 0
        self.processing_fps: float = 0.0
        self.last_processed_time: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.start_time: Optional[datetime] = None

    def _on_connection_change(self, camera_id: str, new_status: CameraConnectionStatus) -> None:
        logger.info("[%s] Worker received connection status: %s", camera_id, new_status.value)

    def start(self) -> None:
        """Starts stream capture and processing worker threads."""
        if self._proc_thread and self._proc_thread.is_alive():
            logger.warning("[%s] CameraWorker is already running", self.camera_id)
            return

        self._stop_event.clear()
        self.start_time = datetime.now(timezone.utc)

        # 1. Start ingestion
        self.capture.start()

        # 2. Start frame consumer & AI processing thread
        self._proc_thread = threading.Thread(
            target=self._processing_loop,
            name=f"Proc-{self.camera_id}",
            daemon=True,
        )
        self._proc_thread.start()
        logger.info("[%s] CameraWorker started (target FPS: %.1f)", self.camera_id, self.config.target_fps)

    def stop(self, timeout: float = 3.0) -> None:
        """Gracefully stops both capture and processing threads."""
        self._stop_event.set()
        self.capture.stop(timeout=timeout)

        if self._proc_thread and self._proc_thread.is_alive():
            self._proc_thread.join(timeout=timeout)

        logger.info("[%s] CameraWorker stopped", self.camera_id)

    def _processing_loop(self) -> None:
        """Pulls frames from buffer, samples at target FPS, and runs AI routing."""
        target_fps = self.config.target_fps
        min_interval = 1.0 / target_fps if target_fps > 0 else 0.2
        last_process_wall_time = 0.0

        fps_count = 0
        fps_timer = time.perf_counter()

        while not self._stop_event.is_set():
            frame_item = self.buffer.get(timeout=0.2)
            if frame_item is None:
                continue

            frame_idx, ts, frame = frame_item

            # Frame sampling: check if enough time elapsed since last processed frame
            now_wall = time.perf_counter()
            time_since_last = now_wall - last_process_wall_time
            if time_since_last < (min_interval * 0.90):
                # Skip frame to preserve target FPS
                self.frames_skipped_by_sampling += 1
                continue

            last_process_wall_time = now_wall

            try:
                # Dispatch to AI router
                result = self.router.process_frame(
                    camera_id=self.camera_id,
                    frame=frame,
                    frame_index=frame_idx,
                    timestamp=ts,
                    detection_mode=self.config.detection_mode,
                )

                self.frames_processed += 1
                self.last_processed_time = ts

                # Update processing FPS metric
                fps_count += 1
                if fps_count >= 10:
                    elapsed = time.perf_counter() - fps_timer
                    if elapsed > 0:
                        self.processing_fps = round(fps_count / elapsed, 1)
                    fps_count = 0
                    fps_timer = time.perf_counter()

                # Dispatch result to callback
                if self.on_result:
                    self.on_result(result)

            except Exception as e:
                # Error isolation: never let one frame error crash the worker or system
                self.last_error = str(e)
                logger.error("[%s] Processing error on frame %d: %s", self.camera_id, frame_idx, e)

    def get_health_metrics(self) -> Dict[str, Any]:
        """Returns structured health telemetry for this camera."""
        uptime = 0.0
        if self.start_time:
            uptime = round((datetime.now(timezone.utc) - self.start_time).total_seconds(), 1)

        total_received = self.capture.total_captured_frames
        buffer_dropped = self.buffer.total_dropped
        total_dropped = buffer_dropped + self.frames_skipped_by_sampling

        return {
            "camera_id": self.camera_id,
            "name": self.config.name,
            "location_name": self.config.location_name,
            "status": self.capture.status.value,
            "stream_type": self.config.stream_type.value,
            "detection_mode": self.config.detection_mode,
            "capture_fps": self.capture.measured_fps or self.capture.native_fps,
            "processing_fps": self.processing_fps,
            "target_fps": self.config.target_fps,
            "frames_received": total_received,
            "frames_processed": self.frames_processed,
            "frames_dropped": total_dropped,
            "buffer_dropped": buffer_dropped,
            "sampled_skipped": self.frames_skipped_by_sampling,
            "buffer_size": self.buffer.size,
            "buffer_capacity": self.config.buffer_size,
            "reconnect_count": self.capture.reconnect_count,
            "last_error": self.last_error or self.capture.last_error,
            "uptime_seconds": uptime,
            "last_frame_time": self.last_processed_time.isoformat() if self.last_processed_time else None,
        }


class CameraManager:
    """Coordinates multiple independent CameraWorkers."""

    def __init__(self, router: Optional[AIRouter] = None) -> None:
        self.router = router or AIRouter()
        self._workers: Dict[str, CameraWorker] = {}
        self._lock = threading.Lock()

    def add_camera(
        self,
        config: CameraConfig,
        on_result: Optional[Callable[[CameraFrameAIResult], None]] = None,
        auto_start: bool = False,
        capture_factory: Optional[Callable[[str], Any]] = None,
        loop_file: bool = True,
    ) -> CameraWorker:
        """Registers a camera configuration and initializes its worker."""
        with self._lock:
            if config.camera_id in self._workers:
                raise ValueError(f"Camera with ID '{config.camera_id}' is already registered.")

            worker = CameraWorker(
                config=config,
                router=self.router,
                on_result=on_result,
                capture_factory=capture_factory,
                loop_file=loop_file,
            )
            self._workers[config.camera_id] = worker
            logger.info("Registered camera: %s (%s)", config.camera_id, config.name)

        if auto_start and config.enabled:
            worker.start()

        return worker

    def remove_camera(self, camera_id: str) -> bool:
        """Stops and unregisters a camera worker."""
        with self._lock:
            worker = self._workers.pop(camera_id, None)
        if worker:
            worker.stop()
            logger.info("Removed camera: %s", camera_id)
            return True
        return False

    def start_camera(self, camera_id: str) -> bool:
        """Starts an individual camera worker."""
        with self._lock:
            worker = self._workers.get(camera_id)
        if worker:
            worker.start()
            return True
        return False

    def stop_camera(self, camera_id: str) -> bool:
        """Stops an individual camera worker."""
        with self._lock:
            worker = self._workers.get(camera_id)
        if worker:
            worker.stop()
            return True
        return False

    def start_all(self) -> None:
        """Starts all registered and enabled camera workers."""
        with self._lock:
            workers = list(self._workers.values())
        for w in workers:
            if w.config.enabled:
                w.start()

    def stop_all(self) -> None:
        """Gracefully stops all camera workers."""
        with self._lock:
            workers = list(self._workers.values())
        for w in workers:
            w.stop()

    def get_camera_status(self, camera_id: str) -> Optional[Dict[str, Any]]:
        """Returns health metrics for a specific camera."""
        with self._lock:
            worker = self._workers.get(camera_id)
        return worker.get_health_metrics() if worker else None

    def get_all_statuses(self) -> List[Dict[str, Any]]:
        """Returns health telemetry for all cameras."""
        with self._lock:
            workers = list(self._workers.values())
        return [w.get_health_metrics() for w in workers]

    @property
    def camera_count(self) -> int:
        with self._lock:
            return len(self._workers)
