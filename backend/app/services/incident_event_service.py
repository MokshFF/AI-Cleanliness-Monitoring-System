"""Incident event service coordinating persistence to MongoDB and real-time WebSocket broadcasting."""
import asyncio
import logging
from typing import Optional, Dict, Any, Union

from backend.app.schemas.incident import IncidentCreate, IncidentResponse
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.websocket.manager import ConnectionManager, get_connection_manager
from backend.app.websocket.alerts import (
    create_incident_created_event,
    create_incident_updated_event,
)
from ai.incident.incident_engine import IncidentEngine
from backend.app.services.incident_persistence import IncidentPersistenceService

logger = logging.getLogger("incident_event_service")


class IncidentEventService(IncidentPersistenceService):
    """Coordinates incident persistence to MongoDB and real-time WebSocket notifications.
    
    Adheres strictly to the persistence order:
    1. IncidentEngine confirms incident
    2. Persist incident to MongoDB
    3. If persistence succeeds -> Broadcast INCIDENT_CREATED WebSocket event
    4. If persistence fails -> Log error, increment failure telemetry, do NOT broadcast, isolate failure.
    """

    def __init__(
        self,
        incident_repo: Optional[IncidentRepository] = None,
        ws_manager: Optional[ConnectionManager] = None,
        event_loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        super().__init__(incident_repo=incident_repo, event_loop=event_loop)
        self.ws_manager = ws_manager or get_connection_manager()
        self.total_broadcasted: int = 0

    async def _async_persist(self, incident_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Asynchronously writes incident to MongoDB, then broadcasts if and only if persistence succeeded."""
        inc_id = incident_dict.get("incident_id", "UNKNOWN")
        created = None
        try:
            created = await self.repo.create(incident_dict)
            self.total_persisted += 1
            logger.info("Incident %s successfully persisted to MongoDB", inc_id)
        except Exception as e:
            self.total_errors += 1
            logger.error(
                "Database error persisting incident %s: %s (WebSocket broadcast cancelled)",
                inc_id,
                e,
            )
            return None

        # Persistence was successful: now broadcast the real-time event
        try:
            event = create_incident_created_event(created)
            dispatched = await self.ws_manager.broadcast(event)
            self.total_broadcasted += 1
            logger.info("Incident %s broadcasted to %d WebSocket clients", inc_id, dispatched)
        except Exception as e:
            # Resilient failure isolation: WebSocket broadcast issues must never crash caller
            logger.error("Failed broadcasting INCIDENT_CREATED for %s: %s", inc_id, e)

        return created

    async def broadcast_status_update(
        self,
        incident_id: str,
        status: str,
        notes: Optional[str] = None,
        updated_at: Optional[Any] = None,
        updated_by: Optional[str] = None,
    ) -> None:
        """Broadcasts INCIDENT_UPDATED after status mutation has succeeded in DB."""
        try:
            event = create_incident_updated_event(
                incident_id=incident_id,
                status=status,
                notes=notes,
                updated_at=updated_at,
                updated_by=updated_by,
            )
            dispatched = await self.ws_manager.broadcast(event)
            logger.info("Status update for %s broadcasted to %d clients", incident_id, dispatched)
        except Exception as e:
            logger.error("Failed broadcasting INCIDENT_UPDATED for %s: %s", incident_id, e)


# Singleton instance accessor
_incident_event_service: Optional[IncidentEventService] = None


def get_incident_event_service() -> IncidentEventService:
    """Returns the singleton IncidentEventService instance."""
    global _incident_event_service
    if _incident_event_service is None:
        _incident_event_service = IncidentEventService()
    return _incident_event_service
