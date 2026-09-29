"""FastAPI dependencies for repository injection, JWT authentication, and RBAC."""
import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.app.core.security import decode_access_token
from backend.app.db.mongodb import async_db_manager
from backend.app.repositories.user_repository import UserRepository
from backend.app.repositories.camera_repository import CameraRepository
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.repositories.audit_repository import AuditRepository
from backend.app.schemas.user import UserResponse, UserRole

logger = logging.getLogger("api_deps")
security_bearer = HTTPBearer(auto_error=False)


def get_user_repo() -> UserRepository:
    return UserRepository()


def get_camera_repo() -> CameraRepository:
    return CameraRepository()


def get_incident_repo() -> IncidentRepository:
    return IncidentRepository()


def get_audit_repo() -> AuditRepository:
    return AuditRepository()


async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    user_repo: UserRepository = Depends(get_user_repo),
) -> UserResponse:
    """Validates JWT access token and returns authenticated UserResponse."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(auth.credentials)
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token subject missing",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception as e:
        logger.warning("Token validation error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database (supports user_id or username)
    user_dict = await user_repo.get_by_id(user_id)
    if not user_dict:
        user_dict = await user_repo.get_by_username(user_id)

    if not user_dict:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user_dict.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return UserResponse(
        id=user_dict["id"],
        username=user_dict["username"],
        email=user_dict["email"],
        full_name=user_dict.get("full_name", ""),
        role=UserRole(user_dict["role"]),
        is_active=user_dict.get("is_active", True),
        created_at=user_dict["created_at"],
        updated_at=user_dict.get("updated_at"),
        last_login=user_dict.get("last_login"),
    )


async def require_admin(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Enforces Admin-only access restriction."""
    if current_user.role != UserRole.ADMIN:
        logger.warning("Access denied: user %s has role %s (ADMIN required)", current_user.username, current_user.role)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required",
        )
    return current_user


async def require_operator_or_admin(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Enforces Operator or Admin access restriction."""
    allowed_roles = {UserRole.ADMIN, UserRole.OPERATOR, UserRole.SUPERVISOR}
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or Admin privileges required",
        )
    return current_user
