"""Pydantic schemas for GIS Map, Analytics, and Municipal Reporting."""
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from backend.app.schemas.camera import CameraStatus, DetectionMode
from backend.app.schemas.incident import WasteType, IncidentSeverity, IncidentStatus


class CameraMapItem(BaseModel):
    """Lightweight camera projection optimized for GIS map visualization."""
    camera_id: str
    name: str
    location_name: str
    latitude: float
    longitude: float
    status: CameraStatus
    detection_mode: DetectionMode
    is_active: bool


class IncidentMapItem(BaseModel):
    """Lightweight incident projection linked to geospatial coordinates."""
    incident_id: str
    camera_id: str
    camera_name: str = ""
    location_name: str = "Unknown Location"
    latitude: float
    longitude: float
    waste_type: WasteType
    category: str
    severity: IncidentSeverity
    status: IncidentStatus
    confidence: float
    timestamp: datetime


class TrendDataPoint(BaseModel):
    date: str
    count: int


class CategoryCount(BaseModel):
    category: str
    count: int


class CameraCount(BaseModel):
    camera_id: str
    camera_name: str
    count: int
    active_count: int
    high_severity_count: int


class LocationCount(BaseModel):
    location_name: str
    count: int
    solid_count: int
    liquid_count: int
    active_count: int


class AnalyticsSummaryResponse(BaseModel):
    """Consolidated longitudinal analytics summary."""
    total_incidents: int
    active_incidents: int
    resolved_incidents: int
    dismissed_incidents: int
    resolution_rate: float
    waste_type_breakdown: Dict[str, int]
    category_breakdown: List[CategoryCount]
    severity_breakdown: Dict[str, int]
    status_breakdown: Dict[str, int]
    camera_breakdown: List[CameraCount]
    location_breakdown: List[LocationCount]
    trend: List[TrendDataPoint]
