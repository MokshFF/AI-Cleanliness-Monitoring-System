"""Incident persistence service connecting IncidentEngine callbacks to MongoDB."""
import asyncio
import logging
from typing import Optional, Dict, Any
from backend.app.schemas.incident import IncidentCreate
from backend.app.repositories.incident_repository import IncidentRepository
from ai.incident.incident_engine import IncidentEngine

logger = logging.getLogger("incident_persistence")


class IncidentPersistenceService:
    """Bridges Phase 5 IncidentEngine confirmation events to MongoDB persistence."""

    def __init__(
        self,
        incident_repo: Optional[IncidentRepository] = None,
        event_loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        self.repo = incident_repo or IncidentRepository()
        self.loop = event_loop
        self.total_persisted: int = 0
        self.total_errors: int = 0

    def attach_to_engine(self, engine: IncidentEngine) -> None:
        """Registers listener on Phase 5 IncidentEngine to automatically persist incidents."""
        engine.on_incident(self.on_incident_confirmed)
        logger.info("IncidentPersistenceService attached to IncidentEngine")

    def on_incident_confirmed(self, incident: IncidentCreate) -> None:
        """Callback invoked synchronously or asynchronously by IncidentEngine."""
        doc = incident.model_dump()

        try:
            # Check if there is an active running event loop in this thread
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None

            if current_loop and current_loop.is_running():
                # Schedule task in current running loop
                current_loop.create_task(self._async_persist(doc))
            elif self.loop and self.loop.is_running():
                # Schedule task in designated application event loop from worker thread
                asyncio.run_coroutine_threadsafe(self._async_persist(doc), self.loop)
            else:
                # Run synchronously to completion in thread
                asyncio.run(self._async_persist(doc))
        except Exception as e:
            # Resilient failure isolation: never crash camera pipeline on DB errors
            self.total_errors += 1
            logger.error(
                "Failed to schedule persistence for incident %s: %s",
                incident.incident_id,
                e,
                exc_info=False,
            )

    async def _async_persist(self, incident_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Asynchronously writes incident to MongoDB."""
        inc_id = incident_dict.get("incident_id", "UNKNOWN")
        try:
            created = await self.repo.create(incident_dict)
            self.total_persisted += 1
            logger.info("Incident %s successfully persisted to MongoDB", inc_id)
            return created
        except Exception as e:
            self.total_errors += 1
            logger.error("Database error persisting incident %s: %s", inc_id, e)
            return None
