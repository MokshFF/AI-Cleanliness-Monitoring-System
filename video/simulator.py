"""Local video stream simulator for development and offline testing."""
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from video.camera_config import CameraConfig
from video.stream_capture import StreamCapture
from video.frame_buffer import BoundedFrameBuffer

logger = logging.getLogger("camera_simulator")


def create_simulated_camera_config(
    camera_id: str,
    video_path: Path,
    name: Optional[str] = None,
    location_name: Optional[str] = None,
    detection_mode: str = "BOTH",
    target_fps: float = 5.0,
    buffer_size: int = 30,
) -> CameraConfig:
    """Helper factory to instantiate a CameraConfig pointing to a local test video file."""
    video_p = Path(video_path).resolve()
    if not video_p.is_file():
        raise FileNotFoundError(f"Simulation test video not found at: {video_p}")

    friendly_name = name or f"Simulated Camera ({camera_id})"
    loc = location_name or f"Zone for {camera_id}"

    return CameraConfig(
        camera_id=camera_id,
        name=friendly_name,
        location_name=loc,
        rtsp_url=str(video_p),
        latitude=28.6139,
        longitude=77.2090,
        enabled=True,
        detection_mode=detection_mode,
        target_fps=target_fps,
        reconnect_attempts=3,
        reconnect_delay=1.0,
        buffer_size=buffer_size,
    )
