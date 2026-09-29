"""Asynchronous MongoDB connection manager using Motor."""
import logging
from typing import Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from backend.app.core.config import settings

logger = logging.getLogger("mongodb")


class AsyncDatabaseManager:
    """Manages asynchronous Motor client and database connection lifecycle."""

    def __init__(self) -> None:
        self.client: Optional[AsyncIOMotorClient] = None
        self._mock_db: Optional[Any] = None

    def connect(self) -> AsyncIOMotorClient:
        """Initializes AsyncIOMotorClient connection pool."""
        if self.client is None:
            logger.info("Connecting to MongoDB at %s...", settings.MONGODB_URI)
            self.client = AsyncIOMotorClient(
                settings.MONGODB_URI,
                minPoolSize=settings.MONGODB_MIN_POOL_SIZE,
                maxPoolSize=settings.MONGODB_MAX_POOL_SIZE,
                serverSelectionTimeoutMS=2000,
            )
        return self.client

    def get_database(self, db_name: Optional[str] = None) -> AsyncIOMotorDatabase:
        """Retrieves active AsyncIOMotorDatabase instance."""
        if self._mock_db is not None:
            return self._mock_db
        client = self.connect()
        target_name = db_name or settings.database_name
        return client[target_name]

    def set_mock_database(self, mock_db: Any) -> None:
        """Allows injecting an in-memory/mock database for isolated unit testing."""
        self._mock_db = mock_db

    async def ping(self) -> bool:
        """Performs a health check ping against MongoDB."""
        if self._mock_db is not None:
            return True
        try:
            client = self.connect()
            await client.admin.command("ping")
            logger.debug("MongoDB health ping successful")
            return True
        except Exception as e:
            logger.warning("MongoDB ping failed: %s", e)
            return False

    def close(self) -> None:
        """Closes active client connections."""
        if self.client:
            self.client.close()
            self.client = None
            logger.info("MongoDB connection closed")


# Global singleton instance
async_db_manager = AsyncDatabaseManager()


async def get_async_db() -> AsyncIOMotorDatabase:
    """FastAPI dependency for accessing the async database."""
    return async_db_manager.get_database()
