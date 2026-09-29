"""Idempotent index creation for MongoDB collections."""
import logging
from typing import Dict, List, Any
import pymongo

logger = logging.getLogger("db_indexes")


async def create_indexes(db: Any) -> Dict[str, List[str]]:
    """Creates required indexes on MongoDB collections idempotently.
    
    Collections indexed:
    - users: username (unique), email (unique)
    - cameras: camera_id (unique)
    - incidents: incident_id (unique), camera_id, timestamp, status, severity,
                 waste_type, category, and compound query indexes
    - audit_logs: timestamp, user_id, action
    
    Returns:
        Dictionary mapping collection name to list of index names created.
    """
    results: Dict[str, List[str]] = {}

    try:
        # 1. USERS COLLECTION
        user_col = db["users"]
        u_idx1 = await user_col.create_index([("username", pymongo.ASCENDING)], unique=True, sparse=True)
        u_idx2 = await user_col.create_index([("email", pymongo.ASCENDING)], unique=True)
        results["users"] = [u_idx1, u_idx2]

        # 2. CAMERAS COLLECTION
        cam_col = db["cameras"]
        c_idx1 = await cam_col.create_index([("camera_id", pymongo.ASCENDING)], unique=True)
        c_idx2 = await cam_col.create_index([("is_active", pymongo.ASCENDING)])
        results["cameras"] = [c_idx1, c_idx2]

        # 3. INCIDENTS COLLECTION
        inc_col = db["incidents"]
        i_idx1 = await inc_col.create_index([("incident_id", pymongo.ASCENDING)], unique=True)
        i_idx2 = await inc_col.create_index([("camera_id", pymongo.ASCENDING)])
        i_idx3 = await inc_col.create_index([("timestamp", pymongo.DESCENDING)])
        i_idx4 = await inc_col.create_index([("status", pymongo.ASCENDING)])
        i_idx5 = await inc_col.create_index([("severity", pymongo.ASCENDING)])
        i_idx6 = await inc_col.create_index([("waste_type", pymongo.ASCENDING)])
        i_idx7 = await inc_col.create_index([("category", pymongo.ASCENDING)])
        # Compound indexes for fast query filtering + sorting
        i_idx8 = await inc_col.create_index([("camera_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])
        i_idx9 = await inc_col.create_index([("status", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])
        i_idx10 = await inc_col.create_index([("severity", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])
        results["incidents"] = [
            i_idx1, i_idx2, i_idx3, i_idx4, i_idx5, i_idx6, i_idx7, i_idx8, i_idx9, i_idx10
        ]

        # 4. AUDIT LOGS COLLECTION
        audit_col = db["audit_logs"]
        a_idx1 = await audit_col.create_index([("timestamp", pymongo.DESCENDING)])
        a_idx2 = await audit_col.create_index([("user_id", pymongo.ASCENDING)])
        a_idx3 = await audit_col.create_index([("action", pymongo.ASCENDING)])
        results["audit_logs"] = [a_idx1, a_idx2, a_idx3]

        logger.info("Successfully ensured all required MongoDB indexes")
    except Exception as e:
        logger.error("Error creating MongoDB indexes: %s", e)
        raise

    return results
