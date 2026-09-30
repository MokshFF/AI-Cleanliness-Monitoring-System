"""Cleanliness Incident REST API endpoints."""
import math
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import FileResponse

from backend.app.core.config import settings
from backend.app.schemas.incident import (
    IncidentCreate,
    IncidentUpdateStatus,
    IncidentResponse,
    IncidentPaginationResponse,
    IncidentStatus,
    IncidentSeverity,
    WasteType,
)
from backend.app.schemas.user import UserResponse
from backend.app.schemas.audit import AuditAction
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.repositories.audit_repository import AuditRepository
from backend.app.api.deps import (
    get_incident_repo,
    get_audit_repo,
    require_operator_or_admin,
)
from backend.app.websocket.manager import get_connection_manager
from backend.app.websocket.alerts import create_incident_updated_event

logger = logging.getLogger("api_incidents")
router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.post("/", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    incident_in: IncidentCreate,
    request: Request,
    current_user: UserResponse = Depends(require_operator_or_admin),
    incident_repo: IncidentRepository = Depends(get_incident_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """Creates a new incident record in MongoDB."""
    existing = await incident_repo.get_by_id(incident_in.incident_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incident with ID '{incident_in.incident_id}' already exists",
        )

    doc = incident_in.model_dump()
    created = await incident_repo.create(doc)

    client_ip = request.client.host if request.client else "unknown"
    await audit_repo.create({
        "user_id": current_user.id,
        "username": current_user.username,
        "action": AuditAction.CREATE_INCIDENT.value,
        "resource_type": "incident",
        "resource_id": created["incident_id"],
        "ip_address": client_ip,
        "metadata": {
            "waste_type": created["waste_type"],
            "category": created["category"],
            "severity": created["severity"],
        },
    })

    return IncidentResponse(**created)


@router.get("/", response_model=IncidentPaginationResponse)
async def list_incidents(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    status: Optional[IncidentStatus] = Query(None, description="Filter by lifecycle status"),
    severity: Optional[IncidentSeverity] = Query(None, description="Filter by severity level"),
    waste_type: Optional[WasteType] = Query(None, description="Filter by SOLID or LIQUID"),
    category: Optional[str] = Query(None, description="Filter by class name, e.g. plastic_bottle"),
    start_date: Optional[datetime] = Query(None, description="Filter incidents on or after timestamp"),
    end_date: Optional[datetime] = Query(None, description="Filter incidents on or before timestamp"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max: 100)"),
    current_user: UserResponse = Depends(require_operator_or_admin),
    incident_repo: IncidentRepository = Depends(get_incident_repo),
):
    """Lists incidents with multi-field filtering and pagination."""
    skip = (page - 1) * page_size
    items, total = await incident_repo.list(
        camera_id=camera_id,
        status=status.value if status else None,
        severity=severity.value if severity else None,
        waste_type=waste_type.value if waste_type else None,
        category=category,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=page_size,
    )

    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    response_items = [IncidentResponse(**item) for item in items]

    return IncidentPaginationResponse(
        items=response_items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: str,
    current_user: UserResponse = Depends(require_operator_or_admin),
    incident_repo: IncidentRepository = Depends(get_incident_repo),
):
    """Retrieves an incident by incident_id."""
    inc = await incident_repo.get_by_id(incident_id)
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return IncidentResponse(**inc)


@router.patch("/{incident_id}/status", response_model=IncidentResponse)
async def update_incident_status(
    incident_id: str,
    update_data: IncidentUpdateStatus,
    request: Request,
    current_user: UserResponse = Depends(require_operator_or_admin),
    incident_repo: IncidentRepository = Depends(get_incident_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """Updates incident status (NEW, ACKNOWLEDGED, RESOLVED, DISMISSED) and logs an audit record."""
    target = await incident_repo.get_by_id(incident_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    new_status = update_data.status.value
    updated = await incident_repo.update_status(
        incident_id=incident_id,
        new_status=new_status,
        notes=update_data.notes,
    )

    # Determine action for audit log
    action_map = {
        "ACKNOWLEDGED": AuditAction.ACKNOWLEDGE_INCIDENT.value,
        "RESOLVED": AuditAction.RESOLVE_INCIDENT.value,
        "DISMISSED": AuditAction.DISMISS_INCIDENT.value,
    }
    action_name = action_map.get(new_status, "UPDATE_INCIDENT_STATUS")

    client_ip = request.client.host if request.client else "unknown"
    await audit_repo.create({
        "user_id": current_user.id,
        "username": current_user.username,
        "action": action_name,
        "resource_type": "incident",
        "resource_id": incident_id,
        "ip_address": client_ip,
        "metadata": {
            "old_status": target.get("status"),
            "new_status": new_status,
            "notes": update_data.notes,
        },
    })

    # Real-time WebSocket broadcast of INCIDENT_UPDATED event
    try:
        ws_manager = get_connection_manager()
        event = create_incident_updated_event(
            incident_id=incident_id,
            status=new_status,
            notes=update_data.notes,
            updated_at=updated.get("updated_at"),
            updated_by=current_user.username,
        )
        await ws_manager.broadcast(event)
    except Exception as e:
        logger.warning("Failed broadcasting INCIDENT_UPDATED for %s: %s", incident_id, e)

    return IncidentResponse(**updated)
 
 
@router.get("/{incident_id}/snapshot")
async def get_incident_snapshot(
    incident_id: str,
    current_user: UserResponse = Depends(require_operator_or_admin),
    incident_repo: IncidentRepository = Depends(get_incident_repo),
):
    """Securely streams the evidence snapshot image for an incident without exposing filesystem paths."""
    inc = await incident_repo.get_by_id(incident_id)
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    raw_path_str = inc.get("snapshot_path")
    if not raw_path_str:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No snapshot associated with this incident")

    # Safely resolve path and prevent path traversal
    candidate = Path(raw_path_str)
    if not candidate.is_absolute():
        candidate = (settings.BASE_DIR / candidate).resolve()
    else:
        candidate = candidate.resolve()

    # Security check: ensure path is within BASE_DIR
    base_resolved = settings.BASE_DIR.resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to requested snapshot path")

    if not candidate.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot image file not found on disk")

    suffix = candidate.suffix.lower()
    media_type = "image/jpeg"
    if suffix == ".png":
        media_type = "image/png"
    elif suffix == ".webp":
        media_type = "image/webp"

    return FileResponse(path=str(candidate), media_type=media_type)
