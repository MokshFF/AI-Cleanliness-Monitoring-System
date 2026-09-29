"""Camera management REST API endpoints."""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request

from backend.app.schemas.camera import CameraCreate, CameraUpdate, CameraResponse, CameraStatus, DetectionMode
from backend.app.schemas.user import UserResponse
from backend.app.schemas.audit import AuditAction
from backend.app.repositories.camera_repository import CameraRepository
from backend.app.repositories.audit_repository import AuditRepository
from backend.app.api.deps import (
    get_camera_repo,
    get_audit_repo,
    require_admin,
    require_operator_or_admin,
)

logger = logging.getLogger("api_cameras")
router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.post("/", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
async def create_camera(
    camera_in: CameraCreate,
    request: Request,
    current_admin: UserResponse = Depends(require_admin),
    camera_repo: CameraRepository = Depends(get_camera_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """Admin-only: Registers a new CCTV camera stream."""
    existing = await camera_repo.get_by_id(camera_in.camera_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Camera with ID '{camera_in.camera_id}' is already registered",
        )

    cam_dict = camera_in.model_dump()
    cam_dict["detection_mode"] = camera_in.detection_mode.value
    created = await camera_repo.create(cam_dict)

    client_ip = request.client.host if request.client else "unknown"
    await audit_repo.create({
        "user_id": current_admin.id,
        "username": current_admin.username,
        "action": AuditAction.CREATE_CAMERA.value,
        "resource_type": "camera",
        "resource_id": created["camera_id"],
        "ip_address": client_ip,
        "metadata": {"name": created["name"], "detection_mode": created["detection_mode"]},
    })

    return CameraResponse(**created)


@router.get("/", response_model=List[CameraResponse])
async def list_cameras(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    is_active: Optional[bool] = None,
    current_user: UserResponse = Depends(require_operator_or_admin),
    camera_repo: CameraRepository = Depends(get_camera_repo),
):
    """Admin or Operator: Lists cameras with credentials masked."""
    items = await camera_repo.list(skip=skip, limit=limit, is_active=is_active)
    return [CameraResponse(**c) for c in items]


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera_by_id(
    camera_id: str,
    current_user: UserResponse = Depends(require_operator_or_admin),
    camera_repo: CameraRepository = Depends(get_camera_repo),
):
    """Admin or Operator: Retrieves details for a specific camera with credentials masked."""
    c = await camera_repo.get_by_id(camera_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    return CameraResponse(**c)


@router.patch("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: str,
    camera_update: CameraUpdate,
    request: Request,
    current_admin: UserResponse = Depends(require_admin),
    camera_repo: CameraRepository = Depends(get_camera_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """Admin-only: Updates camera parameters."""
    target = await camera_repo.get_by_id(camera_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    update_dict = {k: v for k, v in camera_update.model_dump(exclude_unset=True).items() if v is not None}
    if "detection_mode" in update_dict and hasattr(update_dict["detection_mode"], "value"):
        update_dict["detection_mode"] = update_dict["detection_mode"].value
    if "status" in update_dict and hasattr(update_dict["status"], "value"):
        update_dict["status"] = update_dict["status"].value

    updated = await camera_repo.update(camera_id, update_dict)
    client_ip = request.client.host if request.client else "unknown"

    await audit_repo.create({
        "user_id": current_admin.id,
        "username": current_admin.username,
        "action": AuditAction.UPDATE_CAMERA.value,
        "resource_type": "camera",
        "resource_id": camera_id,
        "ip_address": client_ip,
        "metadata": {"updated_fields": list(update_dict.keys())},
    })

    return CameraResponse(**updated)


@router.delete("/{camera_id}", status_code=status.HTTP_200_OK)
async def delete_camera(
    camera_id: str,
    request: Request,
    current_admin: UserResponse = Depends(require_admin),
    camera_repo: CameraRepository = Depends(get_camera_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """Admin-only: Decommissions a camera."""
    deleted = await camera_repo.delete(camera_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    client_ip = request.client.host if request.client else "unknown"
    await audit_repo.create({
        "user_id": current_admin.id,
        "username": current_admin.username,
        "action": AuditAction.DELETE_CAMERA.value,
        "resource_type": "camera",
        "resource_id": camera_id,
        "ip_address": client_ip,
        "metadata": {"status": "DELETED"},
    })

    return {"message": f"Camera '{camera_id}' decommissioned successfully"}
