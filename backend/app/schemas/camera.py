"""Pydantic schemas for camera management and configuration."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl

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
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Geographical latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Geographical longitude")
    rtsp_url: str = Field(..., description="RTSP or video stream URI (stored securely)")
    detection_mode: DetectionMode = Field(default=DetectionMode.BOTH, description="AI detection mode")

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

class CameraResponse(BaseModel):
    camera_id: str
    name: str
    location_name: str
    latitude: float
    longitude: float
    status: CameraStatus
    detection_mode: DetectionMode
    created_at: datetime
    # Note: rtsp_url is deliberately excluded from response to frontend as per security rule #20
