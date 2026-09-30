"""WebSocket API endpoint for real-time surveillance alerts."""
import json
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status

from backend.app.websocket.auth import authenticate_websocket
from backend.app.websocket.manager import get_connection_manager
from backend.app.websocket.alerts import create_pong_event

logger = logging.getLogger("websocket_api")
router = APIRouter(tags=["WebSockets"])


async def handle_websocket_alerts(websocket: WebSocket, token: Optional[str] = None) -> None:
    """Shared handler for authenticated real-time WebSocket alerts."""
    user = await authenticate_websocket(websocket, token)
    if not user:
        # 1008 Policy Violation close code for authentication/authorization failures
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    manager = get_connection_manager()
    await manager.connect(websocket, user)

    try:
        while True:
            data = await websocket.receive_text()
            # Handle client-initiated heartbeat ping
            try:
                parsed = json.loads(data)
                if parsed.get("type") == "PING":
                    await manager.send_personal_message(websocket, create_pong_event())
            except Exception:
                pass
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.debug("WebSocket connection terminated: %s", e)
        await manager.disconnect(websocket)


@router.websocket("/ws/alerts")
async def websocket_alerts_route(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """FastAPI WebSocket endpoint for real-time incident notifications."""
    await handle_websocket_alerts(websocket, token)
