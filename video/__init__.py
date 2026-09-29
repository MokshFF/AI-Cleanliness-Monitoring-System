"""Video ingestion, RTSP streaming, frame buffering, and multi-camera orchestration."""
from pathlib import Path

VIDEO_DIR = Path(__file__).resolve().parent

from video.camera_config import (
    CameraConfig,
    CameraConnectionStatus,
    StreamType,
    mask_credentials,
)
from video.frame_buffer import BoundedFrameBuffer
from video.stream_capture import StreamCapture
from video.ai_router import AIRouter, CameraFrameAIResult
from video.camera_manager import CameraWorker, CameraManager
from video.simulator import create_simulated_camera_config

__all__ = [
    "VIDEO_DIR",
    "CameraConfig",
    "CameraConnectionStatus",
    "StreamType",
    "mask_credentials",
    "BoundedFrameBuffer",
    "StreamCapture",
    "AIRouter",
    "CameraFrameAIResult",
    "CameraWorker",
    "CameraManager",
    "create_simulated_camera_config",
]
