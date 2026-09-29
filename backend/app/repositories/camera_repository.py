"""Camera repository for MongoDB persistence."""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pymongo import ReturnDocument
from backend.app.db.mongodb import async_db_manager

logger = logging.getLogger("camera_repository")


class CameraRepository:
    """Async repository for Camera CRUD operations."""

    def __init__(self, db=None) -> None:
        self._db = db

    @property
    def collection(self):
        db = self._db if self._db is not None else async_db_manager.get_database()
        return db["cameras"]

    async def create(self, camera_data: Dict[str, Any]) -> Dict[str, Any]:
        """Registers a new camera document in MongoDB."""
        doc = dict(camera_data)
        now = datetime.now(timezone.utc)
        doc["created_at"] = doc.get("created_at") or now
        doc["updated_at"] = doc.get("updated_at") or now
        doc["is_active"] = doc.get("is_active", True)
        doc["status"] = doc.get("status", "ONLINE")

        await self.collection.insert_one(doc)
        doc.pop("_id", None)
        logger.info("Registered camera: %s (%s)", doc["camera_id"], doc["name"])
        return doc

    async def get_by_id(self, camera_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves camera by unique camera_id."""
        doc = await self.collection.find_one({"camera_id": camera_id})
        if doc:
            doc.pop("_id", None)
        return doc

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Lists cameras with optional is_active filter."""
        query: Dict[str, Any] = {}
        if is_active is not None:
            query["is_active"] = is_active

        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        items = []
        async for doc in cursor:
            doc.pop("_id", None)
            items.append(doc)
        return items

    async def update(self, camera_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Updates camera attributes."""
        updates = dict(update_data)
        updates["updated_at"] = datetime.now(timezone.utc)

        doc = await self.collection.find_one_and_update(
            {"camera_id": camera_id},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            doc.pop("_id", None)
            logger.info("Updated camera: %s", camera_id)
        return doc

    async def delete(self, camera_id: str) -> bool:
        """Decommissions/removes a camera from database."""
        res = await self.collection.delete_one({"camera_id": camera_id})
        deleted = res.deleted_count > 0
        if deleted:
            logger.info("Deleted camera: %s", camera_id)
        return deleted

    async def count(self, is_active: Optional[bool] = None) -> int:
        """Returns total camera count."""
        query = {}
        if is_active is not None:
            query["is_active"] = is_active
        return await self.collection.count_documents(query)
