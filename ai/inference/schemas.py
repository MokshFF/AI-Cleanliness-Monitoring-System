"""Structured data contracts for Solid Waste Detection inference."""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class BoundingBox(BaseModel):
    """Normalized or absolute bounding box coordinates."""
    x1: float = Field(..., description="Top-left x coordinate")
    y1: float = Field(..., description="Top-left y coordinate")
    x2: float = Field(..., description="Bottom-right x coordinate")
    y2: float = Field(..., description="Bottom-right y coordinate")

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

class SolidDetection(BaseModel):
    """Single solid waste object detection."""
    class_id: int = Field(..., description="Integer class ID from central taxonomy")
    class_name: str = Field(..., description="Label name, e.g. plastic_bottle")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score")
    bbox: BoundingBox = Field(..., description="Pixel bounding box in original image coordinates")
    normalized_bbox: Optional[BoundingBox] = Field(default=None, description="Normalized [0, 1] coordinates")

class SolidFrameDetectionResult(BaseModel):
    """Detection results for a single processed image or video frame."""
    frame_index: Optional[int] = Field(default=None, description="Frame number in video stream")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    image_width: int
    image_height: int
    detections: List[SolidDetection] = Field(default_factory=list)
    processing_time_ms: float = 0.0

    @property
    def count(self) -> int:
        return len(self.detections)

    @property
    def has_violations(self) -> bool:
        return len(self.detections) > 0
