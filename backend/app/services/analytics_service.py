"""Analytics service providing MongoDB aggregations for longitudinal trend and violation metrics."""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from backend.app.db.mongodb import async_db_manager
from backend.app.schemas.analytics import (
    AnalyticsSummaryResponse,
    TrendDataPoint,
    CategoryCount,
    CameraCount,
    LocationCount,
)

logger = logging.getLogger("analytics_service")


class AnalyticsService:
    """Performs performant database-level aggregations across incidents and cameras."""

    def __init__(self, db: Optional[Any] = None) -> None:
        self._db = db

    def get_db(self):
        return self._db if self._db is not None else async_db_manager.get_database()

    def build_match_query(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        camera_id: Optional[str] = None,
        waste_type: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Constructs MongoDB query filter for aggregation pipelines."""
        match: Dict[str, Any] = {}

        if start_date or end_date:
            date_filter: Dict[str, Any] = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            match["timestamp"] = date_filter

        if camera_id:
            match["camera_id"] = camera_id
        if waste_type:
            match["waste_type"] = waste_type.upper()
        if category:
            match["category"] = category.lower()
        if severity:
            match["severity"] = severity.upper()
        if status:
            match["status"] = status.upper()

        return match

    async def get_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        camera_id: Optional[str] = None,
        waste_type: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
    ) -> AnalyticsSummaryResponse:
        """Computes comprehensive analytics summary using MongoDB aggregation pipelines."""
        db = self.get_db()
        incidents_coll = db["incidents"]
        cameras_coll = db["cameras"]

        match_query = self.build_match_query(
            start_date=start_date,
            end_date=end_date,
            camera_id=camera_id,
            waste_type=waste_type,
            category=category,
            severity=severity,
            status=status,
        )

        # 1. Fetch camera metadata dictionary for camera/location naming
        cameras_cursor = cameras_coll.find({}, {"camera_id": 1, "name": 1, "location_name": 1})
        camera_map: Dict[str, Dict[str, str]] = {}
        for cam in await cameras_cursor.to_list(1000):
            camera_map[cam["camera_id"]] = {
                "name": cam.get("name", cam["camera_id"]),
                "location_name": cam.get("location_name", "Unknown Location"),
            }

        # 2. Aggregation for overall Status & Total Count
        status_pipeline = [
            {"$match": match_query},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        status_results = await incidents_coll.aggregate(status_pipeline).to_list(100)
        status_breakdown: Dict[str, int] = {
            "NEW": 0,
            "ACKNOWLEDGED": 0,
            "RESOLVED": 0,
            "DISMISSED": 0,
        }
        for item in status_results:
            if item["_id"]:
                status_breakdown[item["_id"]] = item["count"]

        total_incidents = sum(status_breakdown.values())
        active_incidents = status_breakdown.get("NEW", 0) + status_breakdown.get("ACKNOWLEDGED", 0)
        resolved_incidents = status_breakdown.get("RESOLVED", 0)
        dismissed_incidents = status_breakdown.get("DISMISSED", 0)
        resolution_rate = (
            round((resolved_incidents / total_incidents) * 100, 1)
            if total_incidents > 0
            else 0.0
        )

        # 3. Waste Type Breakdown
        waste_pipeline = [
            {"$match": match_query},
            {"$group": {"_id": "$waste_type", "count": {"$sum": 1}}},
        ]
        waste_results = await incidents_coll.aggregate(waste_pipeline).to_list(100)
        waste_type_breakdown: Dict[str, int] = {"SOLID": 0, "LIQUID": 0}
        for item in waste_results:
            if item["_id"]:
                waste_type_breakdown[item["_id"]] = item["count"]

        # 4. Severity Breakdown
        severity_pipeline = [
            {"$match": match_query},
            {"$group": {"_id": "$severity", "count": {"$sum": 1}}},
        ]
        sev_results = await incidents_coll.aggregate(severity_pipeline).to_list(100)
        severity_breakdown: Dict[str, int] = {
            "LOW": 0,
            "MEDIUM": 0,
            "HIGH": 0,
            "CRITICAL": 0,
        }
        for item in sev_results:
            if item["_id"]:
                severity_breakdown[item["_id"]] = item["count"]

        # 5. Category Breakdown
        cat_pipeline = [
            {"$match": match_query},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        cat_results = await incidents_coll.aggregate(cat_pipeline).to_list(100)
        category_breakdown: List[CategoryCount] = [
            CategoryCount(category=item["_id"], count=item["count"])
            for item in cat_results
            if item["_id"]
        ]

        # 6. Camera Breakdown
        cam_pipeline = [
            {"$match": match_query},
            {
                "$group": {
                    "_id": "$camera_id",
                    "count": {"$sum": 1},
                    "active_count": {
                        "$sum": {
                            "$cond": [{"$in": ["$status", ["NEW", "ACKNOWLEDGED"]]}, 1, 0]
                        }
                    },
                    "high_severity_count": {
                        "$sum": {
                            "$cond": [{"$in": ["$severity", ["HIGH", "CRITICAL"]]}, 1, 0]
                        }
                    },
                }
            },
            {"$sort": {"count": -1}},
        ]
        cam_results = await incidents_coll.aggregate(cam_pipeline).to_list(200)
        camera_breakdown: List[CameraCount] = []
        for item in cam_results:
            cam_id = item["_id"]
            if not cam_id:
                continue
            cam_info = camera_map.get(cam_id, {})
            camera_breakdown.append(
                CameraCount(
                    camera_id=cam_id,
                    camera_name=cam_info.get("name", cam_id),
                    count=item["count"],
                    active_count=item.get("active_count", 0),
                    high_severity_count=item.get("high_severity_count", 0),
                )
            )

        # 7. Location Breakdown
        location_counts: Dict[str, Dict[str, int]] = {}
        # Iterate raw incidents or group by camera_id
        for cam_item in camera_breakdown:
            cam_info = camera_map.get(cam_item.camera_id, {})
            loc_name = cam_info.get("location_name", "Unknown Location")
            if loc_name not in location_counts:
                location_counts[loc_name] = {
                    "count": 0,
                    "solid_count": 0,
                    "liquid_count": 0,
                    "active_count": 0,
                }
            location_counts[loc_name]["count"] += cam_item.count
            location_counts[loc_name]["active_count"] += cam_item.active_count

        # For accurate solid vs liquid counts per location
        loc_type_pipeline = [
            {"$match": match_query},
            {"$group": {"_id": {"camera_id": "$camera_id", "waste_type": "$waste_type"}, "count": {"$sum": 1}}},
        ]
        loc_type_results = await incidents_coll.aggregate(loc_type_pipeline).to_list(500)
        for item in loc_type_results:
            grp = item["_id"]
            if isinstance(grp, dict):
                c_id = grp.get("camera_id")
                w_type = grp.get("waste_type")
                loc = camera_map.get(c_id, {}).get("location_name", "Unknown Location")
                if loc in location_counts:
                    if w_type == "SOLID":
                        location_counts[loc]["solid_count"] += item["count"]
                    elif w_type == "LIQUID":
                        location_counts[loc]["liquid_count"] += item["count"]

        location_breakdown: List[LocationCount] = [
            LocationCount(
                location_name=loc,
                count=data["count"],
                solid_count=data["solid_count"],
                liquid_count=data["liquid_count"],
                active_count=data["active_count"],
            )
            for loc, data in sorted(location_counts.items(), key=lambda x: x[1]["count"], reverse=True)
        ]

        # 8. Time-series Trend Data
        trend: List[TrendDataPoint] = []
        try:
            trend_pipeline = [
                {"$match": match_query},
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$timestamp",
                            }
                        },
                        "count": {"$sum": 1},
                    }
                },
                {"$sort": {"_id": 1}},
            ]
            trend_results = await incidents_coll.aggregate(trend_pipeline).to_list(365)
            for item in trend_results:
                if item["_id"]:
                    trend.append(TrendDataPoint(date=str(item["_id"]), count=item["count"]))
        except Exception as e:
            # Resilient fallback if $dateToString unsupported by in-memory mock driver
            logger.debug("Aggregation trend pipeline fallback: %s", e)
            date_buckets: Dict[str, int] = {}
            cursor = incidents_coll.find(match_query, {"timestamp": 1})
            for doc in await cursor.to_list(1000):
                ts = doc.get("timestamp")
                if isinstance(ts, datetime):
                    d_str = ts.strftime("%Y-%m-%d")
                elif isinstance(ts, str):
                    d_str = ts[:10]
                else:
                    continue
                date_buckets[d_str] = date_buckets.get(d_str, 0) + 1
            for d_str in sorted(date_buckets.keys()):
                trend.append(TrendDataPoint(date=d_str, count=date_buckets[d_str]))

        return AnalyticsSummaryResponse(
            total_incidents=total_incidents,
            active_incidents=active_incidents,
            resolved_incidents=resolved_incidents,
            dismissed_incidents=dismissed_incidents,
            resolution_rate=resolution_rate,
            waste_type_breakdown=waste_type_breakdown,
            category_breakdown=category_breakdown,
            severity_breakdown=severity_breakdown,
            status_breakdown=status_breakdown,
            camera_breakdown=camera_breakdown,
            location_breakdown=location_breakdown,
            trend=trend,
        )
