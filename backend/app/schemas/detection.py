"""Pydantic schemas for single-image and single-camera prototype detection."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from video.camera_config import mask_credentials


class DetectionItem(BaseModel):
    """Structured detection or segmentation result for a single waste object."""
    class_name: str = Field(..., description="Waste category name")
    waste_type: str = Field(..., description="SOLID or LIQUID")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    bbox: Optional[List[float]] = Field(default=None, description="Bounding box [x1, y1, x2, y2]")
    mask_polygon: Optional[List[List[float]]] = Field(default=None, description="Contour polygon for liquid waste")
    affected_area_percentage: Optional[float] = Field(default=None, description="Affected area percentage")
    affected_area_pixels: Optional[int] = Field(default=None, description="Affected area pixels")


class ImageDetectionResponse(BaseModel):
    """Response payload for image detection prototype endpoint."""
    success: bool = True
    image_id: str = Field(..., description="Unique image analysis transaction identifier")
    camera_id: str = Field(default="IMAGE_UPLOAD", description="Associated camera ID or IMAGE_UPLOAD")
    location_name: str = Field(default="Manual Inspection Zone", description="Physical location")
    detections: List[DetectionItem] = Field(default_factory=list, description="List of detected waste items")
    incident_created: bool = Field(default=False, description="Whether confirmed cleanliness incident was generated")
    incident_ids: List[str] = Field(default_factory=list, description="Created incident identifiers")
    annotated_image_url: Optional[str] = Field(default=None, description="Safe URL to stream annotated image")
    processing_time_ms: float = Field(default=0.0, description="Inference and processing latency in milliseconds")


class VideoProcessResponse(BaseModel):
    """Response payload for local video processing prototype endpoint."""
    success: bool = True
    video_name: str
    camera_id: str
    frames_processed: int
    detections_count: int
    incident_created: bool
    incident_ids: List[str]
    processing_fps: float
    duration_seconds: float
    annotated_frame_url: Optional[str] = None


class CameraTestStatusResponse(BaseModel):
    """Status and telemetry for the single-camera prototype runner."""
    is_running: bool
    camera_id: str
    camera_name: str
    location_name: str
    status: str
    fps: float = 0.0
    ai_fps: float = 0.0
    detections_count: int = 0
    incidents_count: int = 0
    latest_detection: Optional[str] = None
    latest_incident_id: Optional[str] = None
    latest_confidence: Optional[float] = None
    latest_timestamp: Optional[datetime] = None
    rtsp_url: Optional[str] = Field(default=None, description="Credential-masked stream URL")

    @field_validator("rtsp_url", mode="before")
    @classmethod
    def redact_credentials(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return mask_credentials(v)
        return v
