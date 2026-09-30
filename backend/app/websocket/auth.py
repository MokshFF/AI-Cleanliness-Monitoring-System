"""WebSocket authentication utilities validating query-param JWT tokens safely."""
import logging
from typing import Optional
import jwt
from fastapi import WebSocket, status

from backend.app.core.security import decode_access_token
from backend.app.repositories.user_repository import UserRepository
from backend.app.schemas.user import UserResponse, UserRole

logger = logging.getLogger("websocket_auth")


async def authenticate_websocket(
    websocket: WebSocket,
    token: Optional[str],
    user_repo: Optional[UserRepository] = None,
) -> Optional[UserResponse]:
    """Authenticates a WebSocket connection using a JWT token passed in query parameters.
    
    Security Tradeoff Documentation:
    Browsers' native WebSocket API (`new WebSocket(url)`) does not support custom HTTP headers
    like `Authorization: Bearer <token>`. Transmitting the JWT via query parameter
    (`/ws/alerts?token=<JWT>`) is the established web standard for WebSocket handshakes.
    To mitigate query parameter leakage risks:
      1. Tokens are NEVER written to server log files.
      2. Invalid, expired, or deactivated tokens are rejected before accepting the socket.
      3. Tokens are never echoed back in alerts or event payloads.
      4. In production, TLS/WSS encrypts the full URL path and query string in transit.
    """
    if not token or not token.strip():
        logger.warning("WebSocket connection rejected: Missing authentication token")
        return None

    try:
        payload = decode_access_token(token.strip())
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("WebSocket connection rejected: Token subject missing")
            return None
    except jwt.ExpiredSignatureError:
        logger.warning("WebSocket connection rejected: Expired token")
        return None
    except Exception as e:
        logger.warning("WebSocket connection rejected: Invalid token signature or format (%s)", type(e).__name__)
        return None

    repo = user_repo or UserRepository()
    user_dict = await repo.get_by_id(user_id)
    if not user_dict:
        user_dict = await repo.get_by_username(user_id)

    if not user_dict:
        logger.warning("WebSocket connection rejected: User not found for token subject")
        return None

    if not user_dict.get("is_active", True):
        logger.warning("WebSocket connection rejected: User account %s is inactive", user_dict.get("username"))
        return None

    role = user_dict.get("role", "OPERATOR")
    if role not in {UserRole.ADMIN.value, UserRole.OPERATOR.value, UserRole.SUPERVISOR.value}:
        logger.warning("WebSocket connection rejected: Unauthorized role %s", role)
        return None

    return UserResponse(
        id=user_dict["id"],
        username=user_dict["username"],
        email=user_dict["email"],
        full_name=user_dict.get("full_name", ""),
        role=UserRole(role),
        is_active=user_dict.get("is_active", True),
        created_at=user_dict["created_at"],
        updated_at=user_dict.get("updated_at"),
        last_login=user_dict.get("last_login"),
    )
