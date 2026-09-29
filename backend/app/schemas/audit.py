"""Pydantic schemas for audit logging and administrative action tracking."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class AuditAction(str, Enum):
    LOGIN = "LOGIN"
    CREATE_USER = "CREATE_USER"
    UPDATE_USER = "UPDATE_USER"
    CREATE_CAMERA = "CREATE_CAMERA"
    UPDATE_CAMERA = "UPDATE_CAMERA"
    DELETE_CAMERA = "DELETE_CAMERA"
    CREATE_INCIDENT = "CREATE_INCIDENT"
    ACKNOWLEDGE_INCIDENT = "ACKNOWLEDGE_INCIDENT"
    RESOLVE_INCIDENT = "RESOLVE_INCIDENT"
    DISMISS_INCIDENT = "DISMISS_INCIDENT"


class AuditLogCreate(BaseModel):
    user_id: Optional[str] = Field(default=None, description="Actor user ID (or 'system')")
    username: Optional[str] = Field(default=None, description="Actor username")
    action: str = Field(..., description="Action name, e.g. ACKNOWLEDGE_INCIDENT")
    resource_type: str = Field(..., description="Target resource type, e.g. incident, camera, user")
    resource_id: str = Field(..., description="Target entity ID")
    ip_address: Optional[str] = Field(default=None, description="Client IP address")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Contextual payload without sensitive data")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLogResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    action: str
    resource_type: str
    resource_id: str
    ip_address: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime


class AuditLogPaginationResponse(BaseModel):
    items: List[AuditLogResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
