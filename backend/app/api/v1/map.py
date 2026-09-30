"""GIS Map REST API endpoints for cameras and geospatial incident visualization."""
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from backend.app.schemas.analytics import CameraMapItem, IncidentMapItem
from backend.app.schemas.camera import CameraStatus, DetectionMode
from backend.app.schemas.incident import WasteType, IncidentSeverity, IncidentStatus
from backend.app.schemas.user import UserResponse
from backend.app.repositories.camera_repository import CameraRepository
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.api.deps import (
    get_camera_repo,
    get_incident_repo,
    require_operator_or_admin,
)

logger = logging.getLogger("api_map")
router = APIRouter(prefix="/map", tags=["GIS Map"])


@router.get("/cameras", response_model=List[CameraMapItem])
async def get_map_cameras(
    is_active: Optional[bool] = Query(None, description="Filter active cameras"),
    current_user: UserResponse = Depends(require_operator_or_admin),
    camera_repo: CameraRepository = Depends(get_camera_repo),
):
    """Retrieves cameras with valid geographic coordinates for GIS map markers.
    Sensitive credentials and RTSP URLs are excluded by schema design.
    """
    cameras = await camera_repo.list(limit=1000, is_active=is_active)
    valid_map_cameras: List[CameraMapItem] = []

    for cam in cameras:
        lat = cam.get("latitude")
        lon = cam.get("longitude")
        # Ensure valid non-zero geospatial coordinates
        if lat is not None and lon is not None and (float(lat) != 0.0 or float(lon) != 0.0):
            try:
                valid_map_cameras.append(
                    CameraMapItem(
                        camera_id=cam["camera_id"],
                        name=cam.get("name", cam["camera_id"]),
                        location_name=cam.get("location_name", "Unknown Location"),
                        latitude=float(lat),
                        longitude=float(lon),
                        status=CameraStatus(cam.get("status", "ONLINE")),
                        detection_mode=DetectionMode(cam.get("detection_mode", "BOTH")),
                        is_active=bool(cam.get("is_active", True)),
                    )
                )
            except Exception as e:
                logger.warning("Error parsing camera %s for map: %s", cam.get("camera_id"), e)

    return valid_map_cameras


@router.get("/incidents", response_model=List[IncidentMapItem])
async def get_map_incidents(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    waste_type: Optional[WasteType] = Query(None, description="Filter by SOLID or LIQUID"),
    severity: Optional[IncidentSeverity] = Query(None, description="Filter by severity level"),
    status: Optional[IncidentStatus] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by class name"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    limit: int = Query(500, ge=1, le=2000, description="Max incidents to plot"),
    current_user: UserResponse = Depends(require_operator_or_admin),
    camera_repo: CameraRepository = Depends(get_camera_repo),
    incident_repo: IncidentRepository = Depends(get_incident_repo),
):
    """Retrieves incidents mapped to genuine coordinates for map markers and heat layers."""
    # 1. Fetch camera coordinates dictionary
    all_cameras = await camera_repo.list(limit=1000)
    cam_coords = {}
    for c in all_cameras:
        cid = c["camera_id"]
        lat = c.get("latitude")
        lon = c.get("longitude")
        if lat is not None and lon is not None and (float(lat) != 0.0 or float(lon) != 0.0):
            cam_coords[cid] = {
                "latitude": float(lat),
                "longitude": float(lon),
                "name": c.get("name", cid),
                "location_name": c.get("location_name", "Unknown Location"),
            }

    # 2. Fetch incidents matching filters
    incidents, _ = await incident_repo.list(
        camera_id=camera_id,
        waste_type=waste_type.value if waste_type else None,
        severity=severity.value if severity else None,
        status=status.value if status else None,
        category=category,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    map_incidents: List[IncidentMapItem] = []
    for inc in incidents:
        c_id = inc.get("camera_id", "")
        # Resolve coordinates from camera or incident metadata
        cam_info = cam_coords.get(c_id)
        inc_lat = inc.get("latitude")
        inc_lon = inc.get("longitude")

        final_lat = None
        final_lon = None
        cam_name = inc.get("camera_name", "")
        loc_name = inc.get("location_name", "")

        if inc_lat is not None and inc_lon is not None and (float(inc_lat) != 0.0 or float(inc_lon) != 0.0):
            final_lat = float(inc_lat)
            final_lon = float(inc_lon)
        elif cam_info:
            final_lat = cam_info["latitude"]
            final_lon = cam_info["longitude"]
            if not cam_name:
                cam_name = cam_info["name"]
            if not loc_name:
                loc_name = cam_info["location_name"]

        # Only include if valid coordinates exist (never fabricate locations)
        if final_lat is not None and final_lon is not None:
            ts = inc.get("timestamp")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts)
                except Exception:
                    ts = datetime.utcnow()

            map_incidents.append(
                IncidentMapItem(
                    incident_id=inc["incident_id"],
                    camera_id=c_id,
                    camera_name=cam_name or c_id,
                    location_name=loc_name or "Unknown Location",
                    latitude=final_lat,
                    longitude=final_lon,
                    waste_type=WasteType(inc["waste_type"]),
                    category=inc.get("category", ""),
                    severity=IncidentSeverity(inc.get("severity", "MEDIUM")),
                    status=IncidentStatus(inc.get("status", "NEW")),
                    confidence=float(inc.get("confidence", 0.0)),
                    timestamp=ts,
                )
            )

    return map_incidents
