"""Schemas export for Cleanliness Monitoring API."""
from backend.app.schemas.camera import CameraBase, CameraCreate, CameraUpdate, CameraResponse, CameraStatus, DetectionMode
from backend.app.schemas.incident import (
    IncidentCreate,
    IncidentUpdateStatus,
    IncidentResponse,
    IncidentStatus,
    IncidentSeverity,
    WasteType,
)
from backend.app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse, UserRole

__all__ = [
    "CameraBase",
    "CameraCreate",
    "CameraUpdate",
    "CameraResponse",
    "CameraStatus",
    "DetectionMode",
    "IncidentCreate",
    "IncidentUpdateStatus",
    "IncidentResponse",
    "IncidentStatus",
    "IncidentSeverity",
    "WasteType",
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "TokenResponse",
    "UserRole",
]
