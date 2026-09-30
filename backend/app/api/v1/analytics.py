"""Analytics REST API endpoints for longitudinal trend and violation metrics."""
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from starlette import status as http_status

from backend.app.schemas.analytics import AnalyticsSummaryResponse
from backend.app.schemas.incident import WasteType, IncidentSeverity, IncidentStatus
from backend.app.schemas.user import UserResponse
from backend.app.services.analytics_service import AnalyticsService
from backend.app.api.deps import (
    get_analytics_service,
    require_operator_or_admin,
)

logger = logging.getLogger("api_analytics")
router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(
    start_date: Optional[datetime] = Query(None, description="Start of observation period"),
    end_date: Optional[datetime] = Query(None, description="End of observation period"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    waste_type: Optional[WasteType] = Query(None, description="Filter by waste type"),
    category: Optional[str] = Query(None, description="Filter by waste category"),
    severity: Optional[IncidentSeverity] = Query(None, description="Filter by severity"),
    status: Optional[IncidentStatus] = Query(None, description="Filter by status"),
    current_user: UserResponse = Depends(require_operator_or_admin),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """Calculates comprehensive longitudinal analytics and aggregations over the incident database."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be after end_date",
        )

    try:
        summary = await analytics_service.get_summary(
            start_date=start_date,
            end_date=end_date,
            camera_id=camera_id,
            waste_type=waste_type.value if waste_type else None,
            category=category,
            severity=severity.value if severity else None,
            status=status.value if status else None,
        )
        return summary
    except Exception as e:
        logger.error("Error generating analytics summary: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate analytics summary: {str(e)}",
        )
