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
    SOLID = "solid"
    LIQUID = "liquid"

class IncidentCreate(BaseModel):
    incident_id: str = Field(..., description="Unique UUID or structured ID")
    camera_id: str = Field(..., description="Source camera ID")
    waste_type: WasteType = Field(..., description="solid or liquid")
    category: str = Field(..., description="Specific waste class name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score")
    affected_area: Optional[float] = Field(default=None, description="Affected area in pixels or percentage")
    snapshot_path: str = Field(..., description="Path to captured evidence snapshot")
    timestamp: datetime = Field(..., description="Incident occurrence timestamp")
    severity: IncidentSeverity = Field(default=IncidentSeverity.MEDIUM)
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
