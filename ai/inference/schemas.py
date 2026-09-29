"""Structured data contracts for Solid and Liquid Waste Detection and Segmentation inference."""
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


class RegionOfInterest(BaseModel):
    """Configurable Monitored Region of Interest (ROI) within a camera frame."""
    name: str = Field(default="full_frame", description="ROI identifier or zone name")
    polygon: Optional[List[List[float]]] = Field(
        default=None,
        description="Vertices [[x1, y1], [x2, y2], ...] defining polygonal monitored region",
    )
    bbox: Optional[BoundingBox] = Field(
        default=None,
        description="Rectangular bounding box defining monitored zone",
    )
    area_pixels: Optional[int] = Field(
        default=None,
        description="Precomputed or measured pixel count of monitored region",
    )


# ------------------------------------------------------------------------------
# SOLID WASTE SCHEMAS (Phase 2)
# ------------------------------------------------------------------------------
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


# ------------------------------------------------------------------------------
# LIQUID WASTE SCHEMAS (Phase 3)
# ------------------------------------------------------------------------------
class LiquidDetection(BaseModel):
    """Single liquid waste instance segmentation detection."""
    class_id: int = Field(..., description="Integer class ID from liquid taxonomy (0..3)")
    class_name: str = Field(..., description="Liquid category, e.g. waterlogging, sewage_overflow")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Segmentation confidence score")
    bbox: BoundingBox = Field(..., description="Enclosing bounding box in pixel coordinates")
    polygon: List[List[float]] = Field(
        default_factory=list,
        description="Contour polygon vertices [[x1, y1], [x2, y2], ...] in pixel space",
    )
    normalized_polygon: Optional[List[List[float]]] = Field(
        default=None,
        description="Contour polygon vertices normalized to [0, 1]",
    )
    affected_area_pixels: int = Field(
        ...,
        ge=0,
        description="Exact pixel area covered by the liquid mask inside the monitored region",
    )
    affected_area_percent: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of monitored region covered by this liquid instance",
    )
    monitored_region_pixels: int = Field(
        ...,
        gt=0,
        description="Total pixel area of the evaluated ROI or frame",
    )


class LiquidFrameDetectionResult(BaseModel):
    """Segmentation results for a single processed image or video frame."""
    frame_index: Optional[int] = Field(default=None, description="Frame number in video stream")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    image_width: int
    image_height: int
    monitored_region_name: str = Field(default="full_frame", description="Active ROI name")
    monitored_region_pixels: int = Field(..., gt=0, description="Total pixels in monitored area")
    total_affected_liquid_pixels: int = Field(default=0, ge=0, description="Combined liquid mask pixel count")
    total_affected_area_percent: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Combined percentage of monitored area covered by liquid",
    )
    detections: List[LiquidDetection] = Field(default_factory=list)
    processing_time_ms: float = 0.0

    @property
    def count(self) -> int:
        return len(self.detections)

    @property
    def has_violations(self) -> bool:
        return len(self.detections) > 0
