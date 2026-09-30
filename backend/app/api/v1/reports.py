"""Municipal Cleanliness Reporting REST API endpoints for CSV and PDF exports."""
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from starlette import status as http_status

from backend.app.schemas.incident import WasteType, IncidentSeverity, IncidentStatus
from backend.app.schemas.user import UserResponse
from backend.app.schemas.audit import AuditAction
from backend.app.repositories.audit_repository import AuditRepository
from backend.app.services.reporting_service import ReportingService
from backend.app.api.deps import (
    get_audit_repo,
    get_reporting_service,
    require_operator_or_admin,
)

logger = logging.getLogger("api_reports")
router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/incidents.csv")
async def export_incidents_csv(
    request: Request,
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    waste_type: Optional[WasteType] = Query(None, description="Filter by waste type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[IncidentSeverity] = Query(None, description="Filter by severity"),
    status: Optional[IncidentStatus] = Query(None, description="Filter by status"),
    limit: int = Query(5000, ge=1, le=10000, description="Max records to include"),
    current_user: UserResponse = Depends(require_operator_or_admin),
    reporting_service: ReportingService = Depends(get_reporting_service),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """Generates an RFC-4180 compliant CSV export of filtered incident logs."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be after end_date",
        )

    try:
        csv_data = await reporting_service.generate_csv(
            start_date=start_date,
            end_date=end_date,
            camera_id=camera_id,
            waste_type=waste_type.value if waste_type else None,
            category=category,
            severity=severity.value if severity else None,
            status=status.value if status else None,
            limit=limit,
        )

        # Audit Log Record
        client_ip = request.client.host if request.client else "unknown"
        ts_tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        await audit_repo.create({
            "user_id": current_user.id,
            "username": current_user.username,
            "action": AuditAction.GENERATE_CSV_REPORT.value,
            "resource_type": "report",
            "resource_id": f"csv-{ts_tag}",
            "ip_address": client_ip,
            "metadata": {
                "camera_id": camera_id,
                "waste_type": waste_type.value if waste_type else None,
                "limit": limit,
            },
        })

        filename = f"incidents_export_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error("Error generating CSV report: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate CSV report: {str(e)}",
        )


@router.get("/incidents.pdf")
async def export_incidents_pdf(
    request: Request,
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    waste_type: Optional[WasteType] = Query(None, description="Filter by waste type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[IncidentSeverity] = Query(None, description="Filter by severity"),
    status: Optional[IncidentStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500, description="Max detailed rows to include in PDF"),
    current_user: UserResponse = Depends(require_operator_or_admin),
    reporting_service: ReportingService = Depends(get_reporting_service),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """Generates an official styled municipal PDF compliance report using ReportLab."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be after end_date",
        )

    try:
        user_label = f"{current_user.full_name or current_user.username} ({current_user.role.value})"
        pdf_bytes = await reporting_service.generate_pdf(
            start_date=start_date,
            end_date=end_date,
            camera_id=camera_id,
            waste_type=waste_type.value if waste_type else None,
            category=category,
            severity=severity.value if severity else None,
            status=status.value if status else None,
            generated_by=user_label,
            limit=limit,
        )

        # Audit Log Record
        client_ip = request.client.host if request.client else "unknown"
        ts_tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        await audit_repo.create({
            "user_id": current_user.id,
            "username": current_user.username,
            "action": AuditAction.GENERATE_PDF_REPORT.value,
            "resource_type": "report",
            "resource_id": f"pdf-{ts_tag}",
            "ip_address": client_ip,
            "metadata": {
                "camera_id": camera_id,
                "waste_type": waste_type.value if waste_type else None,
                "limit": limit,
            },
        })

        filename = f"municipal_cleanliness_report_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error("Error generating PDF report: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF report: {str(e)}",
        )
