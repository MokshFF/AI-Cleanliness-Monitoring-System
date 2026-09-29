"""Audit repository for MongoDB persistence."""
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from backend.app.db.mongodb import async_db_manager

logger = logging.getLogger("audit_repository")


class AuditRepository:
    """Async repository for Audit Log storage and retrieval."""

    def __init__(self, db=None) -> None:
        self._db = db

    @property
    def collection(self):
        db = self._db if self._db is not None else async_db_manager.get_database()
        return db["audit_logs"]

    async def create(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Records an administrative audit log event in MongoDB."""
        doc = dict(log_data)
        if "id" not in doc or not doc["id"]:
            doc["id"] = str(uuid.uuid4())
        doc["timestamp"] = doc.get("timestamp") or datetime.now(timezone.utc)

        # Sanitize metadata to never persist sensitive passwords or tokens
        if "metadata" in doc and isinstance(doc["metadata"], dict):
            clean_meta = {}
            for k, v in doc["metadata"].items():
                if any(s in k.lower() for s in ["password", "secret", "token", "rtsp"]):
                    clean_meta[k] = "***REDACTED***"
                else:
                    clean_meta[k] = v
            doc["metadata"] = clean_meta

        await self.collection.insert_one(doc)
        doc.pop("_id", None)
        logger.debug("Recorded audit log: %s on %s/%s by %s", doc["action"], doc["resource_type"], doc["resource_id"], doc.get("username"))
        return doc

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Lists audit logs with optional user and action filters."""
        query: Dict[str, Any] = {}
        if user_id:
            query["user_id"] = user_id
        if action:
            query["action"] = action.upper()

        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)

        items = []
        async for doc in cursor:
            doc.pop("_id", None)
            items.append(doc)
        return items, total

    async def count(self) -> int:
        """Returns total audit logs count."""
        return await self.collection.count_documents({})
