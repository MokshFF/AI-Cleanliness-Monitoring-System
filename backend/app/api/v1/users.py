"""User management REST API endpoints (Admin only)."""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request

from backend.app.core.security import get_password_hash
from backend.app.schemas.user import UserCreate, UserUpdate, UserResponse, UserRole
from backend.app.schemas.audit import AuditAction
from backend.app.repositories.user_repository import UserRepository
from backend.app.repositories.audit_repository import AuditRepository
from backend.app.api.deps import get_user_repo, get_audit_repo, require_admin

logger = logging.getLogger("api_users")
router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    request: Request,
    current_admin: UserResponse = Depends(require_admin),
    user_repo: UserRepository = Depends(get_user_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """Admin-only: Registers a new user (Operator, Supervisor, or Admin)."""
    # Check duplicate email
    existing_email = await user_repo.get_by_email(user_in.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists",
        )

    # Check duplicate username
    uname = user_in.username or user_in.email.split("@")[0]
    existing_username = await user_repo.get_by_username(uname)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this username already exists",
        )

    password_hash = get_password_hash(user_in.password)
    user_dict = {
        "email": str(user_in.email).lower().strip(),
        "username": uname.lower().strip(),
        "full_name": user_in.full_name,
        "role": user_in.role.value,
        "is_active": user_in.is_active,
        "password_hash": password_hash,
    }

    created = await user_repo.create(user_dict)

    client_ip = request.client.host if request.client else "unknown"
    await audit_repo.create({
        "user_id": current_admin.id,
        "username": current_admin.username,
        "action": AuditAction.CREATE_USER.value,
        "resource_type": "user",
        "resource_id": created["id"],
        "ip_address": client_ip,
        "metadata": {"created_user": created["username"], "role": created["role"]},
    })

    return UserResponse(
        id=created["id"],
        username=created["username"],
        email=created["email"],
        full_name=created.get("full_name", ""),
        role=UserRole(created["role"]),
        is_active=created.get("is_active", True),
        created_at=created["created_at"],
        updated_at=created.get("updated_at"),
        last_login=created.get("last_login"),
    )


@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_admin: UserResponse = Depends(require_admin),
    user_repo: UserRepository = Depends(get_user_repo),
):
    """Admin-only: Lists registered users."""
    items = await user_repo.list(skip=skip, limit=limit)
    return [
        UserResponse(
            id=u["id"],
            username=u["username"],
            email=u["email"],
            full_name=u.get("full_name", ""),
            role=UserRole(u["role"]),
            is_active=u.get("is_active", True),
            created_at=u["created_at"],
            updated_at=u.get("updated_at"),
            last_login=u.get("last_login"),
        )
        for u in items
    ]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: str,
    current_admin: UserResponse = Depends(require_admin),
    user_repo: UserRepository = Depends(get_user_repo),
):
    """Admin-only: Retrieves a specific user by ID."""
    u = await user_repo.get_by_id(user_id)
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse(
        id=u["id"],
        username=u["username"],
        email=u["email"],
        full_name=u.get("full_name", ""),
        role=UserRole(u["role"]),
        is_active=u.get("is_active", True),
        created_at=u["created_at"],
        updated_at=u.get("updated_at"),
        last_login=u.get("last_login"),
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    request: Request,
    current_admin: UserResponse = Depends(require_admin),
    user_repo: UserRepository = Depends(get_user_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """Admin-only: Modifies user details, status, or resets password."""
    target = await user_repo.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_dict = {}
    if user_update.full_name is not None:
        update_dict["full_name"] = user_update.full_name
    if user_update.email is not None:
        update_dict["email"] = str(user_update.email).lower().strip()
    if user_update.role is not None:
        update_dict["role"] = user_update.role.value
    if user_update.is_active is not None:
        update_dict["is_active"] = user_update.is_active
    if user_update.password is not None:
        update_dict["password_hash"] = get_password_hash(user_update.password)

    updated = await user_repo.update(user_id, update_dict)
    client_ip = request.client.host if request.client else "unknown"

    await audit_repo.create({
        "user_id": current_admin.id,
        "username": current_admin.username,
        "action": AuditAction.UPDATE_USER.value,
        "resource_type": "user",
        "resource_id": user_id,
        "ip_address": client_ip,
        "metadata": {"updated_fields": list(update_dict.keys())},
    })

    return UserResponse(
        id=updated["id"],
        username=updated["username"],
        email=updated["email"],
        full_name=updated.get("full_name", ""),
        role=UserRole(updated["role"]),
        is_active=updated.get("is_active", True),
        created_at=updated["created_at"],
        updated_at=updated.get("updated_at"),
        last_login=updated.get("last_login"),
    )
