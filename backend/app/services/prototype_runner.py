"""Prototype single-camera runner managing local video / RTSP live stream processing."""
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import cv2
import numpy as np

from backend.app.core.config import settings
from backend.app.schemas.detection import CameraTestStatusResponse
from backend.app.services.incident_event_service import get_incident_event_service
from video.camera_config import CameraConfig, StreamType, CameraConnectionStatus
from video.camera_manager import CameraWorker
from video.ai_router import AIRouter, CameraFrameAIResult
from ai.incident.incident_engine import IncidentEngine
from backend.app.schemas.incident import IncidentCreate

logger = logging.getLogger("prototype_runner")


class PrototypeCameraRunner:
    """Thread-safe singleton managing the single-camera prototype stream."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._worker: Optional[CameraWorker] = None
        self._engine: Optional[IncidentEngine] = None
        self._is_running: bool = False

        self.camera_id: str = settings.PROTOTYPE_CAMERA_ID
        self.camera_name: str = settings.PROTOTYPE_CAMERA_NAME
        self.location_name: str = settings.PROTOTYPE_CAMERA_LOCATION
        self.rtsp_url: Optional[str] = settings.PROTOTYPE_RTSP_URL

        # Telemetry & state
        self.status: str = "OFFLINE"
        self.fps: float = 0.0
        self.ai_fps: float = 0.0
        self.detections_count: int = 0
        self.incidents_count: int = 0
        self.latest_detection: Optional[str] = None
        self.latest_incident_id: Optional[str] = None
        self.latest_confidence: Optional[float] = None
        self.latest_timestamp: Optional[datetime] = None
        self._latest_frame_jpeg: Optional[bytes] = None

    def start_camera(
        self,
        camera_id: Optional[str] = None,
        camera_name: Optional[str] = None,
        location_name: Optional[str] = None,
        stream_source: Optional[str] = None,
        target_fps: float = 5.0,
        detection_mode: str = "BOTH",
    ) -> bool:
        """Starts the prototype camera ingestion and AI processing pipeline."""
        with self._lock:
            if self._is_running:
                logger.warning("Prototype camera is already running.")
                return True

            self.camera_id = camera_id or settings.PROTOTYPE_CAMERA_ID
            self.camera_name = camera_name or settings.PROTOTYPE_CAMERA_NAME
            self.location_name = location_name or settings.PROTOTYPE_CAMERA_LOCATION

            # Determine video or RTSP source
            source_uri = stream_source or settings.PROTOTYPE_RTSP_URL
            if not source_uri:
                # Fallback to local sample video as simulated CCTV
                default_test_vid = settings.BASE_DIR / "storage" / "test_videos" / "cctv_sample.mp4"
                if default_test_vid.is_file():
                    source_uri = str(default_test_vid)
                else:
                    source_uri = "0"  # Webcam fallback

            self.rtsp_url = source_uri

            # Configure Camera
            cfg = CameraConfig(
                camera_id=self.camera_id,
                name=self.camera_name,
                location_name=self.location_name,
                rtsp_url=source_uri,
                target_fps=target_fps,
                detection_mode=detection_mode.upper(),
                buffer_size=settings.FRAME_BUFFER_MAXSIZE,
            )

            # Initialize IncidentEngine and attach WebSocket persistence coordinator
            self._engine = IncidentEngine()
            event_svc = get_incident_event_service()
            event_svc.attach_to_engine(self._engine)

            # Track incidents created
            def on_incident_confirmed(inc: IncidentCreate):
                with self._lock:
                    self.incidents_count += 1
                    self.latest_incident_id = inc.incident_id
                    self.latest_timestamp = inc.timestamp
                    logger.info("Prototype camera confirmed incident: %s (%s)", inc.incident_id, inc.category)

            self._engine.on_incident(on_incident_confirmed)

            ai_router = AIRouter()

            # Frame processing callback
            def on_frame_result(result: CameraFrameAIResult):
                with self._lock:
                    self.ai_fps = self._worker.processing_fps if self._worker else target_fps
                    self.latest_timestamp = result.timestamp

                    # Check detections
                    has_dets = False
                    if result.solid_result and result.solid_result.has_violations:
                        has_dets = True
                        top = result.solid_result.detections[0]
                        self.latest_detection = f"{top.class_name} (SOLID)"
                        self.latest_confidence = top.confidence
                        self.detections_count += len(result.solid_result.detections)

                    if result.liquid_result and result.liquid_result.has_violations:
                        has_dets = True
                        top_l = result.liquid_result.detections[0]
                        self.latest_detection = f"{top_l.category} (LIQUID)"
                        self.latest_confidence = top_l.confidence
                        self.detections_count += len(result.liquid_result.detections)

                    # Encode latest frame with annotations
                    frame_to_show = result.frame.copy()
                    if result.solid_result and ai_router.solid_detector:
                        frame_to_show = ai_router.solid_detector.annotate_frame(frame_to_show, result.solid_result)
                    if result.liquid_result and ai_router.liquid_segmenter:
                        frame_to_show = ai_router.liquid_segmenter.annotate_frame(frame_to_show, result.liquid_result)

                    ret, buf = cv2.imencode(".jpg", frame_to_show, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    if ret:
                        self._latest_frame_jpeg = buf.tobytes()

                # Dispatch frame result to IncidentEngine
                if self._engine:
                    self._engine.process_camera_result(result)

            self._worker = CameraWorker(
                config=cfg,
                router=ai_router,
                on_result=on_frame_result,
                loop_file=True,
            )

            self._worker.start()
            self._is_running = True
            self.status = "ONLINE"
            logger.info("Prototype camera runner started for %s on %s", self.camera_id, source_uri)
            return True

    def stop_camera(self) -> None:
        """Stops the camera stream and processing worker."""
        with self._lock:
            if not self._is_running or not self._worker:
                return

            self._worker.stop()
            self._worker = None
            self._engine = None
            self._is_running = False
            self.status = "OFFLINE"
            self.fps = 0.0
            self.ai_fps = 0.0
            logger.info("Prototype camera runner stopped.")

    def get_status(self) -> CameraTestStatusResponse:
        """Returns live telemetry snapshot with credential masking."""
        with self._lock:
            fps_val = self._worker.processing_fps if self._worker else 0.0
            return CameraTestStatusResponse(
                is_running=self._is_running,
                camera_id=self.camera_id,
                camera_name=self.camera_name,
                location_name=self.location_name,
                status=self.status,
                fps=fps_val,
                ai_fps=fps_val,
                detections_count=self.detections_count,
                incidents_count=self.incidents_count,
                latest_detection=self.latest_detection,
                latest_incident_id=self.latest_incident_id,
                latest_confidence=self.latest_confidence,
                latest_timestamp=self.latest_timestamp or datetime.now(timezone.utc),
                rtsp_url=self.rtsp_url,
            )

    def get_latest_frame_jpeg(self) -> Optional[bytes]:
        """Returns the latest annotated JPEG frame bytes if available."""
        with self._lock:
            return self._latest_frame_jpeg


# Singleton accessor
_runner: Optional[PrototypeCameraRunner] = None


def get_prototype_runner() -> PrototypeCameraRunner:
    global _runner
    if _runner is None:
        _runner = PrototypeCameraRunner()
    return _runner
