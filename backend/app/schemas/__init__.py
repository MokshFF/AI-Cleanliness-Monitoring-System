"""Schemas export for Cleanliness Monitoring API."""
from backend.app.schemas.camera import (
    CameraBase,
    CameraCreate,
    CameraUpdate,
    CameraResponse,
    CameraStatus,
    DetectionMode,
)
from backend.app.schemas.incident import (
    IncidentCreate,
    IncidentUpdateStatus,
    IncidentResponse,
    IncidentPaginationResponse,
    IncidentStatus,
    IncidentSeverity,
    WasteType,
)
from backend.app.schemas.user import (
    UserBase,
    UserCreate,
    UserUpdate,
    UserLogin,
    UserResponse,
    TokenResponse,
    UserRole,
)
from backend.app.schemas.audit import (
    AuditAction,
    AuditLogCreate,
    AuditLogResponse,
    AuditLogPaginationResponse,
)

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
    "IncidentPaginationResponse",
    "IncidentStatus",
    "IncidentSeverity",
    "WasteType",
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserLogin",
    "UserResponse",
    "TokenResponse",
    "UserRole",
    "AuditAction",
    "AuditLogCreate",
    "AuditLogResponse",
    "AuditLogPaginationResponse",
]
