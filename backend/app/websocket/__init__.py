"""WebSocket package for real-time alerting and dashboard notifications."""
from backend.app.websocket.manager import ConnectionManager, get_connection_manager
from backend.app.websocket.alerts import (
    WebSocketEventType,
    create_connected_event,
    create_incident_created_event,
    create_incident_updated_event,
    create_ping_event,
    create_pong_event,
)

__all__ = [
    "ConnectionManager",
    "get_connection_manager",
    "WebSocketEventType",
    "create_connected_event",
    "create_incident_created_event",
    "create_incident_updated_event",
    "create_ping_event",
    "create_pong_event",
]
