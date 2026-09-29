"""Incident repository for MongoDB persistence."""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from pymongo import ReturnDocument
from backend.app.db.mongodb import async_db_manager

logger = logging.getLogger("incident_repository")


class IncidentRepository:
    """Async repository for Cleanliness Incident CRUD operations."""

    def __init__(self, db=None) -> None:
        self._db = db

    @property
    def collection(self):
        db = self._db if self._db is not None else async_db_manager.get_database()
        return db["incidents"]

    async def create(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Persists a new cleanliness violation incident document in MongoDB."""
        doc = dict(incident_data)
        now = datetime.now(timezone.utc)
        doc["created_at"] = doc.get("created_at") or now
        doc["updated_at"] = doc.get("updated_at") or now
        doc["status"] = doc.get("status", "NEW")

        # Normalize waste_type enum to string if needed
        if "waste_type" in doc and hasattr(doc["waste_type"], "value"):
            doc["waste_type"] = doc["waste_type"].value
        if "severity" in doc and hasattr(doc["severity"], "value"):
            doc["severity"] = doc["severity"].value
        if "status" in doc and hasattr(doc["status"], "value"):
            doc["status"] = doc["status"].value

        await self.collection.insert_one(doc)
        doc.pop("_id", None)
        logger.info(
            "Persisted incident %s (%s, camera %s, severity %s)",
            doc["incident_id"],
            doc["category"],
            doc["camera_id"],
            doc["severity"],
        )
        return doc

    async def get_by_id(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves incident by structured incident_id."""
        doc = await self.collection.find_one({"incident_id": incident_id})
        if doc:
            doc.pop("_id", None)
        return doc

    async def list(
        self,
        camera_id: Optional[str] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        waste_type: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Lists incidents with multi-field filtering and pagination."""
        query: Dict[str, Any] = {}

        if camera_id:
            query["camera_id"] = camera_id
        if status:
            query["status"] = status.upper() if isinstance(status, str) else status
        if severity:
            query["severity"] = severity.upper() if isinstance(severity, str) else severity
        if waste_type:
            query["waste_type"] = waste_type.upper() if isinstance(waste_type, str) else waste_type
        if category:
            query["category"] = category.lower().strip()

        # Date range filtering on timestamp
        date_filter: Dict[str, Any] = {}
        if start_date:
            date_filter["$gte"] = start_date
        if end_date:
            date_filter["$lte"] = end_date
        if date_filter:
            query["timestamp"] = date_filter

        total_count = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)

        items = []
        async for doc in cursor:
            doc.pop("_id", None)
            items.append(doc)

        return items, total_count

    async def update_status(
        self,
        incident_id: str,
        new_status: str,
        notes: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Updates the lifecycle status of an incident (NEW, ACKNOWLEDGED, RESOLVED, DISMISSED)."""
        now = datetime.now(timezone.utc)
        status_str = new_status.upper() if isinstance(new_status, str) else new_status

        updates: Dict[str, Any] = {
            "status": status_str,
            "updated_at": now,
        }
        if notes is not None:
            updates["notes"] = notes
        if status_str == "RESOLVED":
            updates["resolved_at"] = now

        doc = await self.collection.find_one_and_update(
            {"incident_id": incident_id},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            doc.pop("_id", None)
            logger.info("Updated incident %s status to %s", incident_id, status_str)
        return doc

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Returns count of incidents matching filters."""
        query = filters or {}
        return await self.collection.count_documents(query)
