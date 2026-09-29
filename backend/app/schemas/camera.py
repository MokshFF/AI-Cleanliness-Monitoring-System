"""Pydantic schemas for camera management and configuration."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from video.camera_config import mask_credentials


class CameraStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"
    CONNECTING = "CONNECTING"


class DetectionMode(str, Enum):
    SOLID = "SOLID"
    LIQUID = "LIQUID"
    BOTH = "BOTH"


class CameraBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Friendly camera name")
    location_name: str = Field(..., min_length=2, max_length=150, description="Physical location or zone name")
    latitude: Optional[float] = Field(default=0.0, ge=-90.0, le=90.0, description="Geographical latitude")
    longitude: Optional[float] = Field(default=0.0, ge=-180.0, le=180.0, description="Geographical longitude")
    rtsp_url: str = Field(..., description="RTSP or video stream URI (stored securely)")
    detection_mode: DetectionMode = Field(default=DetectionMode.BOTH, description="AI detection mode")
    target_fps: float = Field(default=5.0, ge=0.5, le=60.0, description="Inference sampling rate")
    is_active: bool = Field(default=True, description="Whether camera is actively monitoring")


class CameraCreate(CameraBase):
    camera_id: str = Field(..., min_length=3, max_length=50, description="Unique camera identifier, e.g., CAM-001")


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rtsp_url: Optional[str] = None
    status: Optional[CameraStatus] = None
    detection_mode: Optional[DetectionMode] = None
    target_fps: Optional[float] = None
    is_active: Optional[bool] = None


class CameraResponse(BaseModel):
    camera_id: str
    name: str
    location_name: str
    latitude: float = 0.0
    longitude: float = 0.0
    status: CameraStatus = CameraStatus.ONLINE
    detection_mode: DetectionMode = DetectionMode.BOTH
    target_fps: float = 5.0
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None
    rtsp_url: Optional[str] = Field(default=None, description="Masked stream URL (passwords redacted)")

    @field_validator("rtsp_url", mode="before")
    @classmethod
    def redact_credentials(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return mask_credentials(v)
        return v
