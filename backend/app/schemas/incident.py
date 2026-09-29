"""Pydantic schemas for cleanliness violations and incidents."""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class IncidentStatus(str, Enum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"

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
    metadata: Optional[Dict[str, Any]] = None

class IncidentUpdateStatus(BaseModel):
    status: IncidentStatus = Field(..., description="Updated incident state")
    notes: Optional[str] = None

class IncidentResponse(BaseModel):
    incident_id: str
    camera_id: str
    waste_type: WasteType
    category: str
    confidence: float
    affected_area: Optional[float] = None
    snapshot_url: str
    timestamp: datetime
    status: IncidentStatus
    severity: IncidentSeverity
    created_at: datetime
    resolved_at: Optional[datetime] = None
    notes: Optional[str] = None
