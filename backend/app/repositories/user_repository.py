"""User repository for MongoDB persistence."""
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pymongo import ReturnDocument
from backend.app.db.mongodb import async_db_manager

logger = logging.getLogger("user_repository")


class UserRepository:
    """Async repository for User CRUD operations."""

    def __init__(self, db=None) -> None:
        self._db = db

    @property
    def collection(self):
        db = self._db if self._db is not None else async_db_manager.get_database()
        return db["users"]

    async def create(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a new user document in MongoDB."""
        doc = dict(user_data)
        if "id" not in doc or not doc["id"]:
            doc["id"] = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        doc["created_at"] = doc.get("created_at") or now
        doc["updated_at"] = doc.get("updated_at") or now
        doc["is_active"] = doc.get("is_active", True)
        if "email" in doc:
            doc["email"] = doc["email"].lower().strip()
        if "username" in doc and doc["username"]:
            doc["username"] = doc["username"].lower().strip()
        else:
            doc["username"] = doc["email"].split("@")[0]

        await self.collection.insert_one(doc)
        doc.pop("_id", None)
        logger.info("Created user: %s (%s)", doc["username"], doc["role"])
        return doc

    async def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a user by ID."""
        doc = await self.collection.find_one({"$or": [{"id": user_id}, {"_id": user_id}]})
        if doc:
            doc.pop("_id", None)
        return doc

    async def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Retrieves a user by username."""
        clean_user = username.lower().strip()
        doc = await self.collection.find_one({"username": clean_user})
        if doc:
            doc.pop("_id", None)
        return doc

    async def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieves a user by email address."""
        clean_email = email.lower().strip()
        doc = await self.collection.find_one({"email": clean_email})
        if doc:
            doc.pop("_id", None)
        return doc

    async def update(self, user_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Updates user details."""
        updates = dict(update_data)
        updates["updated_at"] = datetime.now(timezone.utc)
        if "email" in updates and updates["email"]:
            updates["email"] = updates["email"].lower().strip()
        if "username" in updates and updates["username"]:
            updates["username"] = updates["username"].lower().strip()

        doc = await self.collection.find_one_and_update(
            {"$or": [{"id": user_id}, {"_id": user_id}]},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            doc.pop("_id", None)
        return doc

    async def update_last_login(self, user_id: str) -> None:
        """Updates last_login timestamp."""
        now = datetime.now(timezone.utc)
        await self.collection.update_one(
            {"$or": [{"id": user_id}, {"_id": user_id}]},
            {"$set": {"last_login": now, "updated_at": now}},
        )

    async def list(self, skip: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists users with pagination."""
        cursor = self.collection.find().sort("created_at", -1).skip(skip).limit(limit)
        items = []
        async for doc in cursor:
            doc.pop("_id", None)
            items.append(doc)
        return items

    async def count(self) -> int:
        """Returns total user count."""
        return await self.collection.count_documents({})
