"""Strongly-typed camera configuration and connection status models."""
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator


class CameraConnectionStatus(str, Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    RECONNECTING = "RECONNECTING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class StreamType(str, Enum):
    RTSP = "RTSP"
    FILE = "FILE"
    WEBCAM = "WEBCAM"


def mask_credentials(url: str) -> str:
    """Masks credentials in RTSP or HTTP URLs for safe logging and display.
    
    Example:
        'rtsp://user:secret123@192.168.1.50:554/live' -> 'rtsp://user:***@192.168.1.50:554/live'
    """
    if not isinstance(url, str):
        return str(url)
    return re.sub(r"://([^:\s]+):(.+)@([^/@]+)", r"://\1:***@\3", url)


class CameraConfig(BaseModel):
    """Configuration model for a physical or simulated camera stream."""

    camera_id: str = Field(..., min_length=2, max_length=50, description="Unique camera ID (e.g. CAM-001)")
    name: str = Field(..., min_length=2, max_length=100, description="Camera friendly name")
    location_name: str = Field(..., min_length=2, max_length=150, description="Location / Zone name")
    rtsp_url: str = Field(..., description="RTSP URL, local file path, or webcam device index (e.g. '0')")
    latitude: float = Field(default=0.0, ge=-90.0, le=90.0, description="Latitude coordinate")
    longitude: float = Field(default=0.0, ge=-180.0, le=180.0, description="Longitude coordinate")
    enabled: bool = Field(default=True, description="Whether camera ingestion is active")
    detection_mode: str = Field(default="BOTH", description="SOLID, LIQUID, or BOTH")
    target_fps: float = Field(default=5.0, gt=0.0, le=60.0, description="AI processing frame rate")
    reconnect_attempts: int = Field(default=5, ge=0, description="Max reconnection retries before ERROR")
    reconnect_delay: float = Field(default=2.0, ge=0.01, description="Initial reconnect delay in seconds")
    backoff_factor: float = Field(default=1.5, ge=1.0, description="Exponential backoff multiplier")
    buffer_size: int = Field(default=30, ge=5, le=300, description="Max frames in ring buffer")

    @field_validator("detection_mode", mode="before")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        upper_v = str(v).upper().strip()
        if upper_v not in {"SOLID", "LIQUID", "BOTH"}:
            raise ValueError(f"detection_mode must be SOLID, LIQUID, or BOTH (got '{v}')")
        return upper_v

    @property
    def stream_type(self) -> StreamType:
        """Infers stream source type from url string."""
        url_lower = self.rtsp_url.lower().strip()
        if url_lower.startswith("rtsp://") or url_lower.startswith("rtsps://"):
            return StreamType.RTSP
        if url_lower.isdigit():
            return StreamType.WEBCAM
        return StreamType.FILE

    @property
    def safe_url(self) -> str:
        """Returns URL with masked credentials."""
        return mask_credentials(self.rtsp_url)

    def to_safe_dict(self) -> Dict[str, Any]:
        """Exports dictionary with masked credentials."""
        d = self.model_dump()
        d["rtsp_url"] = self.safe_url
        return d

    def __repr__(self) -> str:
        return (
            f"CameraConfig(camera_id='{self.camera_id}', name='{self.name}', "
            f"mode='{self.detection_mode}', url='{self.safe_url}')"
        )
