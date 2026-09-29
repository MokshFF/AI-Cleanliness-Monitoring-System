"""Authentication API router for JWT token issuance and profile inspection."""
import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from backend.app.core.config import settings
from backend.app.core.security import verify_password, create_access_token
from backend.app.schemas.user import UserLogin, TokenResponse, UserResponse
from backend.app.schemas.audit import AuditAction
from backend.app.repositories.user_repository import UserRepository
from backend.app.repositories.audit_repository import AuditRepository
from backend.app.api.deps import get_user_repo, get_audit_repo, get_current_user

logger = logging.getLogger("api_auth")
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    request: Request,
    user_repo: UserRepository = Depends(get_user_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """Authenticates user via username or email and returns a signed JWT access token."""
    user = None
    identifier = login_data.username or login_data.email
    if not identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email is required",
        )

    # Lookup by username first, then email
    if login_data.username:
        user = await user_repo.get_by_username(login_data.username)
    if not user and login_data.email:
        user = await user_repo.get_by_email(login_data.email)
    if not user and identifier:
        user = await user_repo.get_by_username(identifier)
        if not user:
            user = await user_repo.get_by_email(identifier)

    if not user or not verify_password(login_data.password, user.get("password_hash", "")):
        logger.warning("Failed login attempt for identifier: %s", identifier)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # Record last login and emit audit event
    await user_repo.update_last_login(user["id"])
    client_ip = request.client.host if request.client else "unknown"
    await audit_repo.create({
        "user_id": user["id"],
        "username": user["username"],
        "action": AuditAction.LOGIN.value,
        "resource_type": "user",
        "resource_id": user["id"],
        "ip_address": client_ip,
        "metadata": {"role": user["role"]},
    })

    # Issue JWT token
    expires_minutes = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    access_token = create_access_token(
        subject=user["id"],
        expires_delta=timedelta(minutes=expires_minutes),
        extra_claims={
            "username": user["username"],
            "role": user["role"],
            "email": user["email"],
        },
    )

    user_resp = UserResponse(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        full_name=user.get("full_name", ""),
        role=user["role"],
        is_active=user.get("is_active", True),
        created_at=user["created_at"],
        updated_at=user.get("updated_at"),
        last_login=user.get("last_login"),
    )

    logger.info("User authenticated: %s (%s)", user["username"], user["role"])
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_minutes * 60,
        user=user_resp,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_profile(
    current_user: UserResponse = Depends(get_current_user),
):
    """Returns the profile of the currently authenticated user."""
    return current_user
