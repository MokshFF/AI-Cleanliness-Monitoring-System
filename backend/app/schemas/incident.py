"""Pydantic schemas for cleanliness violations and incidents."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class IncidentStatus(str, Enum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class IncidentSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class WasteType(str, Enum):
    SOLID = "SOLID"
    LIQUID = "LIQUID"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            val_upper = value.upper()
            for member in cls:
                if member.value == val_upper:
                    return member
        return None


class IncidentCreate(BaseModel):
    incident_id: str = Field(..., description="Unique structured incident ID (e.g. INC-20260929-000001)")
    camera_id: str = Field(..., description="Source camera ID")
    waste_type: WasteType = Field(..., description="SOLID or LIQUID")
    category: str = Field(..., description="Specific waste class name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score")
    severity: IncidentSeverity = Field(default=IncidentSeverity.MEDIUM)
    snapshot_path: str = Field(..., description="Path to captured evidence snapshot")
    timestamp: datetime = Field(..., description="Incident confirmation timestamp")

    # Tracking & temporal persistence attributes (Phase 5)
    track_id: Optional[int] = Field(default=None, description="Tracker ID for solid waste object")
    first_seen: Optional[datetime] = Field(default=None, description="First timestamp object was detected")
    last_seen: Optional[datetime] = Field(default=None, description="Last timestamp object was confirmed")
    duration_seconds: Optional[float] = Field(default=0.0, description="Duration object remained present")

    # Liquid specific metrics (Phase 5)
    affected_area_pixels: Optional[int] = Field(default=None, description="Affected liquid area in pixels")
    affected_area_percent: Optional[float] = Field(default=None, description="Affected liquid area as percentage of ROI")
    roi_name: Optional[str] = Field(default="global", description="Monitored ROI zone identifier")
    affected_area: Optional[float] = Field(default=None, description="Backwards-compatible affected area metric")

    status: IncidentStatus = Field(default=IncidentStatus.NEW, description="Lifecycle status")
    bounding_box: Optional[List[float]] = Field(default=None, description="Bounding box [x1, y1, x2, y2]")
    mask_polygon: Optional[List[List[float]]] = Field(default=None, description="Liquid waste contour polygon")
    metadata: Optional[Dict[str, Any]] = None


class IncidentUpdateStatus(BaseModel):
    status: IncidentStatus = Field(..., description="Updated incident state: NEW, ACKNOWLEDGED, RESOLVED, DISMISSED")
    notes: Optional[str] = Field(default=None, description="Operator remarks or resolution summary")


class IncidentResponse(BaseModel):
    incident_id: str
    camera_id: str
    waste_type: WasteType
    category: str
    confidence: float
    severity: IncidentSeverity
    snapshot_path: Optional[str] = None
    snapshot_url: Optional[str] = None
    timestamp: datetime
    track_id: Optional[int] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    affected_area_pixels: Optional[int] = None
    affected_area_percent: Optional[float] = None
    affected_area: Optional[float] = None
    roi_name: Optional[str] = None
    bounding_box: Optional[List[float]] = None
    mask_polygon: Optional[List[List[float]]] = None
    status: IncidentStatus = IncidentStatus.NEW
    created_at: datetime
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class IncidentPaginationResponse(BaseModel):
    items: List[IncidentResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
