"""Municipal reporting service generating compliant CSV and PDF reports."""
import io
import csv
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from backend.app.db.mongodb import async_db_manager
from backend.app.services.analytics_service import AnalyticsService

logger = logging.getLogger("reporting_service")


class ReportingService:
    """Produces structured CSV and styled PDF municipal cleanliness reports."""

    def __init__(self, db: Optional[Any] = None) -> None:
        self._db = db
        self.analytics_service = AnalyticsService(db=db)

    def get_db(self):
        return self._db if self._db is not None else async_db_manager.get_database()

    async def _fetch_filtered_incidents(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        camera_id: Optional[str] = None,
        waste_type: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 5000,
    ) -> List[Dict[str, Any]]:
        """Queries incidents matching filters, excluding any sensitive attributes."""
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date cannot be after end_date")

        db = self.get_db()
        incidents_coll = db["incidents"]
        cameras_coll = db["cameras"]

        match_query = self.analytics_service.build_match_query(
            start_date=start_date,
            end_date=end_date,
            camera_id=camera_id,
            waste_type=waste_type,
            category=category,
            severity=severity,
            status=status,
        )

        # Build camera map for camera names and locations
        cameras_cursor = cameras_coll.find({}, {"camera_id": 1, "name": 1, "location_name": 1})
        camera_map: Dict[str, Dict[str, str]] = {}
        for cam in await cameras_cursor.to_list(1000):
            camera_map[cam["camera_id"]] = {
                "name": cam.get("name", cam["camera_id"]),
                "location_name": cam.get("location_name", "Unknown Location"),
            }

        cursor = incidents_coll.find(match_query).sort("timestamp", -1).limit(limit)
        raw_items = await cursor.to_list(limit)

        enriched = []
        for inc in raw_items:
            c_id = inc.get("camera_id", "UNKNOWN")
            c_info = camera_map.get(c_id, {})

            # Format timestamp safely
            ts = inc.get("timestamp")
            if isinstance(ts, datetime):
                ts_str = ts.isoformat()
            else:
                ts_str = str(ts) if ts else ""

            # Extract metrics
            duration = inc.get("duration_seconds", 0.0)
            area_pct = inc.get("affected_area_percent") or inc.get("affected_area_percentage")
            area_str = f"{area_pct:.1f}%" if area_pct is not None else "N/A"

            item = {
                "incident_id": inc.get("incident_id", ""),
                "timestamp": ts_str,
                "camera_id": c_id,
                "camera_name": c_info.get("name", c_id),
                "location_name": c_info.get("location_name", "Unknown Location"),
                "waste_type": inc.get("waste_type", ""),
                "category": inc.get("category", ""),
                "confidence": inc.get("confidence", 0.0),
                "severity": inc.get("severity", ""),
                "status": inc.get("status", ""),
                "duration_seconds": duration,
                "affected_area": area_str,
            }
            enriched.append(item)

        return enriched

    async def generate_csv(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        camera_id: Optional[str] = None,
        waste_type: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 5000,
    ) -> str:
        """Generates RFC 4180 compliant CSV string representing filtered incident records."""
        items = await self._fetch_filtered_incidents(
            start_date=start_date,
            end_date=end_date,
            camera_id=camera_id,
            waste_type=waste_type,
            category=category,
            severity=severity,
            status=status,
            limit=limit,
        )

        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        writer.writerow([
            "Incident ID",
            "Timestamp",
            "Camera ID",
            "Camera Name",
            "Location",
            "Waste Type",
            "Category",
            "Confidence",
            "Severity",
            "Status",
            "Duration (s)",
            "Affected Area (%)",
        ])

        for item in items:
            writer.writerow([
                item["incident_id"],
                item["timestamp"],
                item["camera_id"],
                item["camera_name"],
                item["location_name"],
                item["waste_type"],
                item["category"],
                f"{item['confidence']:.2f}",
                item["severity"],
                item["status"],
                item["duration_seconds"],
                item["affected_area"],
            ])

        return output.getvalue()

    async def generate_pdf(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        camera_id: Optional[str] = None,
        waste_type: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        generated_by: str = "Authorized Personnel",
        limit: int = 50,
    ) -> bytes:
        """Generates an official municipal PDF report using ReportLab."""
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date cannot be after end_date")

        # 1. Fetch summary stats via AnalyticsService
        summary = await self.analytics_service.get_summary(
            start_date=start_date,
            end_date=end_date,
            camera_id=camera_id,
            waste_type=waste_type,
            category=category,
            severity=severity,
            status=status,
        )

        # 2. Fetch detailed incident rows
        items = await self._fetch_filtered_incidents(
            start_date=start_date,
            end_date=end_date,
            camera_id=camera_id,
            waste_type=waste_type,
            category=category,
            severity=severity,
            status=status,
            limit=limit,
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0B1120"),
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=styles["Normal"],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#374151"),
            spaceAfter=12,
        )
        section_style = ParagraphStyle(
            "SectionHeader",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#1F2937"),
            spaceBefore=12,
            spaceAfter=6,
        )
        meta_style = ParagraphStyle(
            "MetaText",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#4B5563"),
        )
        table_cell_style = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#1F2937"),
        )
        table_cell_bold = ParagraphStyle(
            "TableCellBold",
            parent=table_cell_style,
            fontName="Helvetica-Bold",
        )

        story = []

        # Header Branding
        story.append(Paragraph("AI-Based National Cleanliness Monitoring System", title_style))
        story.append(Paragraph("Municipal Cleanliness Incident & Compliance Audit Report", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563EB"), spaceAfter=10))

        # Metadata
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        period_start = start_date.strftime("%Y-%m-%d") if start_date else "System Inception"
        period_end = end_date.strftime("%Y-%m-%d") if end_date else "Present"

        meta_data = [
            [Paragraph(f"<b>Reporting Window:</b> {period_start} to {period_end}", meta_style),
             Paragraph(f"<b>Generated At:</b> {now_str}", meta_style)],
            [Paragraph(f"<b>Authorized Officer:</b> {generated_by}", meta_style),
             Paragraph(f"<b>Filters:</b> Camera={camera_id or 'ALL'}, Type={waste_type or 'ALL'}, Status={status or 'ALL'}", meta_style)]
        ]
        meta_table = Table(meta_data, colWidths=[270, 270])
        meta_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 10))

        # 1. Summary Metrics Table
        story.append(Paragraph("Executive Summary Metrics", section_style))
        kpi_data = [
            ["Total Incidents", "Solid Waste", "Liquid Waste", "Active Violations", "Resolved", "Resolution Rate"],
            [
                str(summary.total_incidents),
                str(summary.waste_type_breakdown.get("SOLID", 0)),
                str(summary.waste_type_breakdown.get("LIQUID", 0)),
                str(summary.active_incidents),
                str(summary.resolved_incidents),
                f"{summary.resolution_rate}%",
            ]
        ]
        kpi_table = Table(kpi_data, colWidths=[90, 90, 90, 90, 90, 90])
        kpi_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 12))

        # 2. Categorical & Severity Breakdown Table
        story.append(Paragraph("Violation Distribution", section_style))
        dist_headers = ["Severity Distribution", "Count", "Lifecycle Status", "Count"]
        sev_items = list(summary.severity_breakdown.items())
        stat_items = list(summary.status_breakdown.items())
        max_rows = max(len(sev_items), len(stat_items))

        dist_data = [dist_headers]
        for idx in range(max_rows):
            sev_k, sev_v = sev_items[idx] if idx < len(sev_items) else ("", "")
            stat_k, stat_v = stat_items[idx] if idx < len(stat_items) else ("", "")
            dist_data.append([str(sev_k), str(sev_v), str(stat_k), str(stat_v)])

        dist_table = Table(dist_data, colWidths=[135, 135, 135, 135])
        dist_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F9FAFB")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(dist_table)
        story.append(Spacer(1, 12))

        # 3. Camera / Location Summary Table
        story.append(Paragraph("Top Camera Fleet Nodes", section_style))
        cam_headers = ["Camera ID", "Name", "Total Incidents", "Active Unresolved", "High / Critical"]
        cam_data = [cam_headers]
        for c in summary.camera_breakdown[:10]:
            cam_data.append([
                c.camera_id,
                c.camera_name,
                str(c.count),
                str(c.active_count),
                str(c.high_severity_count),
            ])
        if len(cam_data) == 1:
            cam_data.append(["N/A", "No camera data in period", "0", "0", "0"])

        cam_table = Table(cam_data, colWidths=[100, 160, 95, 95, 90])
        cam_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(cam_table)
        story.append(Spacer(1, 12))

        # 4. Detailed Incident Records Table
        story.append(Paragraph(f"Recent Detailed Incident Records (Showing up to {limit})", section_style))
        item_headers = ["Incident ID", "Timestamp", "Camera", "Category", "Type", "Severity", "Status"]
        item_data = [item_headers]
        for itm in items:
            item_data.append([
                Paragraph(itm["incident_id"], table_cell_bold),
                Paragraph(itm["timestamp"][:19].replace("T", " "), table_cell_style),
                Paragraph(itm["camera_id"], table_cell_style),
                Paragraph(itm["category"].replace("_", " "), table_cell_style),
                Paragraph(itm["waste_type"], table_cell_style),
                Paragraph(itm["severity"], table_cell_style),
                Paragraph(itm["status"], table_cell_style),
            ])
        if len(item_data) == 1:
            item_data.append(["None", "No incidents recorded in specified timeframe", "-", "-", "-", "-", "-"])

        item_table = Table(item_data, colWidths=[105, 85, 75, 80, 55, 65, 75])
        item_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(item_table)

        # Build Document
        doc.build(story)
        return buffer.getvalue()
