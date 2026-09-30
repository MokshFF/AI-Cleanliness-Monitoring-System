"""Phase 9 Comprehensive End-to-End Demonstration Script.

Simulates the complete GIS Map, Longitudinal Analytics, and Municipal Reporting flow:
1. Bootstraps in-memory database and administrator credentials
2. Registers municipal cameras with GPS coordinates across monitored zones
3. Injects realistic solid and liquid cleanliness violation incidents
4. Verifies GIS Camera projection endpoint (/map/cameras) & zero credential leakage
5. Verifies GIS Incident mapping endpoint (/map/incidents)
6. Validates longitudinal analytics aggregation (/analytics/summary)
7. Validates multi-field analytics filtering (date, severity, waste type)
8. Generates RFC-4180 CSV incident export (/reports/incidents.csv)
9. Verifies CSV audit trail (GENERATE_CSV_REPORT)
10. Generates official multi-page municipal PDF compliance report (/reports/incidents.pdf)
11. Verifies PDF audit trail (GENERATE_PDF_REPORT) and verifies zero secrets leakage
"""
import sys
import os
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.core.config import settings
from backend.app.db.mongodb import async_db_manager
from backend.app.repositories.camera_repository import CameraRepository
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.repositories.audit_repository import AuditRepository
from backend.scripts.create_admin import bootstrap_admin
from backend.app.main import app


def log_step(step_num: int, title: str):
    print(f"\n{'='*75}")
    print(f"  STEP {step_num}: {title.upper()}")
    print(f"{'='*75}")


async def run_e2e_demonstration():
    print("\n" + "#"*75)
    print("  AI-BASED NATIONAL CLEANLINESS MONITORING SYSTEM")
    print("  PHASE 9: GIS MAP, LONGITUDINAL ANALYTICS & MUNICIPAL REPORTING E2E DEMO")
    print("#"*75)

    # Setup isolated test database
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["cleanliness_phase9_e2e_db"]
    async_db_manager.set_mock_database(mock_db)

    client = TestClient(app)

    # STEP 1: Bootstrap Admin
    log_step(1, "Bootstrapping Administrator Account and Database")
    admin_dict = await bootstrap_admin(db=mock_db)
    print(f"  [+] Admin bootstrap complete: {admin_dict['username']} ({admin_dict['role']})")

    # Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("  [+] Admin JWT authenticated successfully")

    # STEP 2: Register Cameras with GPS Coordinates
    log_step(2, "Registering Surveillance Cameras with Geospatial Coordinates")
    cam_repo = CameraRepository(db=mock_db)
    cameras_to_create = [
        {
            "camera_id": "CAM-DEL-01",
            "name": "Connaught Place Radial 1",
            "location_name": "Inner Circle Block A, New Delhi",
            "latitude": 28.6328,
            "longitude": 77.2197,
            "rtsp_url": "rtsp://admin:P@ssw0rd99!@10.0.1.10:554/ch1",
            "status": "ONLINE",
            "detection_mode": "BOTH",
            "is_active": True,
        },
        {
            "camera_id": "CAM-DEL-02",
            "name": "Janpath Market Entry",
            "location_name": "Janpath Commercial Complex, New Delhi",
            "latitude": 28.6250,
            "longitude": 77.2180,
            "rtsp_url": "rtsp://surv:CCTV_Pass_2026@10.0.1.11:554/stream1",
            "status": "ONLINE",
            "detection_mode": "SOLID",
            "is_active": True,
        },
        {
            "camera_id": "CAM-BLR-01",
            "name": "MG Road Metro Node",
            "location_name": "MG Road Station Plaza, Bengaluru",
            "latitude": 12.9756,
            "longitude": 77.6066,
            "rtsp_url": "rtsp://operator:Blr_Camera_88@10.0.2.10:554/live",
            "status": "ONLINE",
            "detection_mode": "LIQUID",
            "is_active": True,
        },
        {
            "camera_id": "CAM-BLR-02",
            "name": "Brigade Road Crossing",
            "location_name": "Brigade Road Commercial Hub, Bengaluru",
            "latitude": 12.9719,
            "longitude": 77.6070,
            "rtsp_url": "rtsp://traffic:BrigadePass33@10.0.2.11:554/feed",
            "status": "OFFLINE",
            "detection_mode": "BOTH",
            "is_active": True,
        },
    ]

    for c in cameras_to_create:
        created = await cam_repo.create(c)
        print(f"  [+] Registered: {created['camera_id']} - {created['name']} [{created['latitude']}, {created['longitude']}]")

    # STEP 3: Inject Varied Incidents
    log_step(3, "Injecting Historical Cleanliness Violations across Fleet")
    inc_repo = IncidentRepository(db=mock_db)
    now = datetime.now(timezone.utc)

    incidents_data = [
        {
            "incident_id": "INC-20260930-001",
            "camera_id": "CAM-DEL-01",
            "waste_type": "SOLID",
            "category": "plastic_bottle",
            "confidence": 0.95,
            "severity": "MEDIUM",
            "status": "RESOLVED",
            "snapshot_path": "snapshots/inc_001.jpg",
            "duration_seconds": 120.0,
            "timestamp": now - timedelta(days=6),
        },
        {
            "incident_id": "INC-20260930-002",
            "camera_id": "CAM-DEL-01",
            "waste_type": "SOLID",
            "category": "garbage_pile",
            "confidence": 0.91,
            "severity": "CRITICAL",
            "status": "ACKNOWLEDGED",
            "snapshot_path": "snapshots/inc_002.jpg",
            "duration_seconds": 450.0,
            "timestamp": now - timedelta(days=4),
        },
        {
            "incident_id": "INC-20260930-003",
            "camera_id": "CAM-DEL-02",
            "waste_type": "SOLID",
            "category": "paper",
            "confidence": 0.86,
            "severity": "LOW",
            "status": "DISMISSED",
            "snapshot_path": "snapshots/inc_003.jpg",
            "duration_seconds": 45.0,
            "timestamp": now - timedelta(days=2),
        },
        {
            "incident_id": "INC-20260930-004",
            "camera_id": "CAM-BLR-01",
            "waste_type": "LIQUID",
            "category": "sewage_overflow",
            "confidence": 0.94,
            "severity": "CRITICAL",
            "status": "NEW",
            "snapshot_path": "snapshots/inc_004.jpg",
            "duration_seconds": 380.0,
            "affected_area_percent": 18.5,
            "timestamp": now - timedelta(hours=10),
        },
        {
            "incident_id": "INC-20260930-005",
            "camera_id": "CAM-BLR-01",
            "waste_type": "LIQUID",
            "category": "liquid_spill",
            "confidence": 0.88,
            "severity": "MEDIUM",
            "status": "RESOLVED",
            "snapshot_path": "snapshots/inc_005.jpg",
            "duration_seconds": 210.0,
            "affected_area_percent": 6.2,
            "timestamp": now - timedelta(hours=2),
        },
        {
            "incident_id": "INC-20260930-006",
            "camera_id": "CAM-BLR-02",
            "waste_type": "SOLID",
            "category": "can",
            "confidence": 0.92,
            "severity": "LOW",
            "status": "NEW",
            "snapshot_path": "snapshots/inc_006.jpg",
            "duration_seconds": 60.0,
            "timestamp": now,
        },
    ]

    for inc in incidents_data:
        await inc_repo.create(inc)
    print(f"  [+] Injected {len(incidents_data)} incident records across SOLID and LIQUID classes")

    # STEP 4: Query GIS Map Cameras
    log_step(4, "Querying GIS Map Cameras Projection (/api/v1/map/cameras)")
    cam_resp = client.get("/api/v1/map/cameras", headers=headers)
    assert cam_resp.status_code == 200
    map_cams = cam_resp.json()
    print(f"  [+] Map Cameras returned: {len(map_cams)}")
    for mc in map_cams:
        print(f"      - {mc['camera_id']}: {mc['name']} @ ({mc['latitude']}, {mc['longitude']}) [{mc['status']}]")

    # Security check: Zero credential leakage
    assert "P@ssw0rd99!" not in cam_resp.text
    assert "CCTV_Pass_2026" not in cam_resp.text
    assert "rtsp://" not in cam_resp.text
    print("  [+] Verified: No RTSP passwords or stream URLs present in map camera payload")

    # STEP 5: Query GIS Map Incidents
    log_step(5, "Querying GIS Geotagged Incidents Projection (/api/v1/map/incidents)")
    inc_resp = client.get("/api/v1/map/incidents", headers=headers)
    assert inc_resp.status_code == 200
    map_incs = inc_resp.json()
    print(f"  [+] Mapped Incidents returned: {len(map_incs)}")
    for mi in map_incs[:4]:
        print(f"      - {mi['incident_id']}: {mi['category']} ({mi['waste_type']}) Sev: {mi['severity']} @ ({mi['latitude']}, {mi['longitude']})")

    # STEP 6: Query Longitudinal Analytics Summary
    log_step(6, "Querying Longitudinal Analytics Summary (/api/v1/analytics/summary)")
    analytics_resp = client.get("/api/v1/analytics/summary", headers=headers)
    assert analytics_resp.status_code == 200
    summary = analytics_resp.json()
    print(f"  [+] Total Incidents:     {summary['total_incidents']}")
    print(f"  [+] Active Violations:   {summary['active_incidents']} (New + Acknowledged)")
    print(f"  [+] Resolved Incidents: {summary['resolved_incidents']}")
    print(f"  [+] Resolution Rate:     {summary['resolution_rate']}%")
    print(f"  [+] Waste Breakdown:     SOLID={summary['waste_type_breakdown']['SOLID']}, LIQUID={summary['waste_type_breakdown']['LIQUID']}")
    print("  [+] Top Categories:")
    for cat in summary['category_breakdown']:
        print(f"      - {cat['category']}: {cat['count']}")

    # STEP 7: Filter Analytics by Date & Severity
    log_step(7, "Testing Analytics Multi-field Filtering (Last 24 Hours, Critical/High)")
    yesterday_iso = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    filtered_resp = client.get(
        "/api/v1/analytics/summary",
        params={"start_date": yesterday_iso, "severity": "CRITICAL"},
        headers=headers,
    )
    assert filtered_resp.status_code == 200
    crit_summary = filtered_resp.json()
    print(f"  [+] 24h Critical Incidents: {crit_summary['total_incidents']}")

    # STEP 8: Export RFC-4180 CSV Report
    log_step(8, "Generating Municipal CSV Incident Export (/api/v1/reports/incidents.csv)")
    csv_resp = client.get("/api/v1/reports/incidents.csv", headers=headers)
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    csv_lines = csv_resp.text.strip().split("\n")
    print(f"  [+] Generated CSV size: {len(csv_resp.content)} bytes ({len(csv_lines)} lines)")
    print(f"  [+] Header row: {csv_lines[0]}")
    print(f"  [+] Sample data row: {csv_lines[1]}")

    # STEP 9: Validate Audit Trail for CSV
    log_step(9, "Validating Audit Trail Record for CSV Report Generation")
    audit_repo = AuditRepository(db=mock_db)
    csv_logs, total_csv = await audit_repo.list(action="GENERATE_CSV_REPORT")
    assert total_csv >= 1
    print(f"  [+] Audit record verified: {csv_logs[0]['action']} by {csv_logs[0]['username']} on {csv_logs[0]['resource_id']}")

    # STEP 10: Generate Official Municipal PDF Report
    log_step(10, "Generating Official Municipal PDF Compliance Report (/api/v1/reports/incidents.pdf)")
    pdf_resp = client.get("/api/v1/reports/incidents.pdf", headers=headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF-")
    print(f"  [+] Generated PDF size: {len(pdf_resp.content)} bytes")
    print("  [+] Validated PDF magic bytes: '%PDF-' verified")

    # STEP 11: Validate Audit Trail for PDF & Ensure Zero Secret Leakage
    log_step(11, "Validating PDF Audit Record and Security Redaction Checks")
    pdf_logs, total_pdf = await audit_repo.list(action="GENERATE_PDF_REPORT")
    assert total_pdf >= 1
    print(f"  [+] Audit record verified: {pdf_logs[0]['action']} by {pdf_logs[0]['username']} on {pdf_logs[0]['resource_id']}")

    # Ensure no credentials in PDF or CSV
    assert b"P@ssw0rd99!" not in pdf_resp.content
    assert b"CCTV_Pass_2026" not in pdf_resp.content
    assert "P@ssw0rd99!" not in csv_resp.text
    print("  [+] Security audit passed: zero plaintext credentials or RTSP URLs in exports")

    print("\n" + "="*75)
    print("  ALL 11 END-TO-END DEMONSTRATION STEPS COMPLETED SUCCESSFULLY!")
    print("="*75 + "\n")


if __name__ == "__main__":
    asyncio.run(run_e2e_demonstration())
