"""Database layer initialization."""
from backend.app.db.session import db_manager, get_db

__all__ = ["db_manager", "get_db"]
