"""WebSocket event models and factory functions."""
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, Union
from backend.app.schemas.incident import IncidentResponse, IncidentCreate
from backend.app.schemas.user import UserResponse, UserRole


class WebSocketEventType(str, Enum):
    CONNECTED = "CONNECTED"
    INCIDENT_CREATED = "INCIDENT_CREATED"
    INCIDENT_UPDATED = "INCIDENT_UPDATED"
    PING = "PING"
    PONG = "PONG"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_connected_event(user: UserResponse) -> Dict[str, Any]:
    """Generates the initial handshake event sent to authenticated clients upon connection."""
    return {
        "type": WebSocketEventType.CONNECTED.value,
        "timestamp": _now_iso(),
        "user_id": user.id,
        "username": user.username,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
    }


def create_incident_created_event(incident: Union[IncidentResponse, IncidentCreate, Dict[str, Any]]) -> Dict[str, Any]:
    """Generates the broadcast event when a new incident is confirmed and persisted.
    
    Ensures safe formatting without sensitive tokens or database internals.
    """
    if hasattr(incident, "model_dump"):
        data = incident.model_dump()
    elif isinstance(incident, dict):
        data = dict(incident)
    else:
        raise ValueError(f"Unsupported incident payload type: {type(incident)}")

    # Remove internal MongoDB _id if present, ensuring incident_id is top-level
    data.pop("_id", None)

    # Format datetime objects to ISO strings if needed
    for field in ("timestamp", "created_at", "updated_at"):
        val = data.get(field)
        if isinstance(val, datetime):
            data[field] = val.isoformat()

    return {
        "type": WebSocketEventType.INCIDENT_CREATED.value,
        "timestamp": _now_iso(),
        "incident": data,
    }


def create_incident_updated_event(
    incident_id: str,
    status: str,
    notes: Optional[str] = None,
    updated_at: Optional[Union[datetime, str]] = None,
    updated_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Generates the broadcast event when an existing incident status transitions."""
    timestamp = _now_iso()
    event_payload: Dict[str, Any] = {
        "type": WebSocketEventType.INCIDENT_UPDATED.value,
        "timestamp": timestamp,
        "incident_id": incident_id,
        "status": status,
    }
    if notes is not None:
        event_payload["notes"] = notes
    if updated_at is not None:
        event_payload["updated_at"] = updated_at.isoformat() if isinstance(updated_at, datetime) else str(updated_at)
    if updated_by is not None:
        event_payload["updated_by"] = updated_by

    return event_payload


def create_ping_event() -> Dict[str, Any]:
    """Generates a keepalive heartbeat ping."""
    return {
        "type": WebSocketEventType.PING.value,
        "timestamp": _now_iso(),
    }


def create_pong_event() -> Dict[str, Any]:
    """Generates a heartbeat pong response."""
    return {
        "type": WebSocketEventType.PONG.value,
        "timestamp": _now_iso(),
    }
