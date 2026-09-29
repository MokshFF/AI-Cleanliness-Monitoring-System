"""Bootstrap administrator account in MongoDB.

Idempotent: if an admin user already exists with the configured username/email,
it does nothing and exits cleanly.
"""
import sys
import os
import asyncio
import logging
from typing import Optional, Dict, Any

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.core.config import settings
from backend.app.core.security import get_password_hash
from backend.app.db.mongodb import async_db_manager
from backend.app.repositories.user_repository import UserRepository
from backend.app.schemas.user import UserRole

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("create_admin")


async def bootstrap_admin(db=None) -> Optional[Dict[str, Any]]:
    """Creates the default admin user if one does not exist.

    Args:
        db: Optional database instance (for testing or mock DB).

    Returns:
        The created user dict, or existing user dict if already present.
    """
    repo = UserRepository(db=db)

    admin_username = settings.ADMIN_USERNAME.lower().strip()
    admin_email = settings.ADMIN_EMAIL.lower().strip()

    # Check by username
    existing_by_username = await repo.get_by_username(admin_username)
    if existing_by_username:
        logger.info(
            "Admin user '%s' already exists (id=%s). No action taken.",
            admin_username,
            existing_by_username.get("id"),
        )
        return existing_by_username

    # Check by email
    existing_by_email = await repo.get_by_email(admin_email)
    if existing_by_email:
        logger.info(
            "Admin user with email '%s' already exists (id=%s). No action taken.",
            admin_email,
            existing_by_email.get("id"),
        )
        return existing_by_email

    # Create new admin user
    password_hash = get_password_hash(settings.ADMIN_PASSWORD)
    user_data = {
        "username": admin_username,
        "email": admin_email,
        "password_hash": password_hash,
        "role": UserRole.ADMIN.value,
        "is_active": True,
    }

    created = await repo.create(user_data)
    logger.info(
        "Successfully created administrator: username='%s', email='%s', role='%s', id=%s",
        created["username"],
        created["email"],
        created["role"],
        created["id"],
    )
    return created


async def main() -> None:
    """CLI entrypoint."""
    try:
        await async_db_manager.connect()
        admin = await bootstrap_admin()
        logger.info("Admin bootstrap completed successfully.")
    except Exception as exc:
        logger.error("Admin bootstrap failed: %s", exc, exc_info=True)
        sys.exit(1)
    finally:
        await async_db_manager.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
