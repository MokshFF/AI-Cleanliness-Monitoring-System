"""Database session and client management."""
from typing import Optional
from pymongo import MongoClient
from backend.app.core.config import settings

class DatabaseManager:
    """Manages MongoDB client connection lifecycle."""

    def __init__(self) -> None:
        self.client: Optional[MongoClient] = None

    def connect(self) -> MongoClient:
        if self.client is None:
            self.client = MongoClient(
                settings.MONGODB_URI,
                minPoolSize=settings.MONGODB_MIN_POOL_SIZE,
                maxPoolSize=settings.MONGODB_MAX_POOL_SIZE,
                serverSelectionTimeoutMS=3000,
            )
        return self.client

    def get_database(self):
        client = self.connect()
        return client[settings.MONGODB_DB_NAME]

    def close(self) -> None:
        if self.client:
            self.client.close()
            self.client = None

db_manager = DatabaseManager()

def get_db():
    """Dependency helper returning the current MongoDB database instance."""
    return db_manager.get_database()
