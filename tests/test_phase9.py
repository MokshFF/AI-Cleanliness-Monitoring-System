"""Phase 9 Comprehensive Test Suite: GIS Map, Longitudinal Analytics & Municipal Reporting.

Covers:
1.  Map cameras endpoint returns cameras with valid coordinates (/map/cameras)
2.  Map cameras excludes cameras with zero (0.0, 0.0) or null coordinates
3.  Map cameras excludes RTSP URLs and credentials
4.  Map cameras requires authentication
5.  Map cameras filter by is_active status
6.  Map incidents endpoint returns incidents mapped with camera coordinates (/map/incidents)
7.  Map incidents filter by waste_type (SOLID / LIQUID)
8.  Map incidents filter by severity (CRITICAL / HIGH / MEDIUM / LOW)
9.  Map incidents filter by status (NEW / ACKNOWLEDGED / RESOLVED / DISMISSED)
10. Map incidents excludes incidents for cameras without coordinates
11. Map incidents requires authentication
12. Analytics summary total, active, resolved, dismissed counts (/analytics/summary)
13. Analytics summary resolution rate percentage calculation
14. Analytics summary waste type breakdown
15. Analytics summary category breakdown sorted by frequency
16. Analytics summary camera and location aggregations
17. Analytics summary date range filtering (start_date / end_date)
18. Analytics summary invalid date range rejected (start_date > end_date -> 400)
19. Analytics summary requires authentication
20. Reports CSV generation RFC-4180 format (/reports/incidents.csv)
21. Reports CSV generation creates audit log entry (GENERATE_CSV_REPORT)
22. Reports PDF generation creates valid PDF bytes starting with %PDF- (/reports/incidents.pdf)
23. Reports PDF generation creates audit log entry (GENERATE_PDF_REPORT)
24. Reports date validation rejects start_date > end_date with HTTP 400
25. Security: No RTSP credentials, passwords, or JWT tokens in CSV or PDF exports
"""
import pytest
import asyncio
import csv
import io
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from backend.app.core.config import settings
from backend.app.db.mongodb import async_db_manager
from backend.app.schemas.user import UserRole
from backend.app.repositories.camera_repository import CameraRepository
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.repositories.audit_repository import AuditRepository
from backend.scripts.create_admin import bootstrap_admin
from backend.app.main import app


@pytest.fixture(autouse=True)
def setup_mock_db():
    """Sets up an isolated in-memory MongoDB instance for each Phase 9 test."""
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["cleanliness_phase9_test_db"]
    async_db_manager.set_mock_database(mock_db)
    yield mock_db
    mock_client.close()


@pytest.fixture
def client():
    """FastAPI TestClient instance."""
    return TestClient(app)


@pytest.fixture
def auth_headers(setup_mock_db, client):
    """Bootstraps administrator and returns authorized Authorization headers."""
    asyncio.run(bootstrap_admin(db=setup_mock_db))
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def populated_dataset(setup_mock_db):
    """Seeds test database with sample cameras and varied incidents."""
    cam_repo = CameraRepository(db=setup_mock_db)
    inc_repo = IncidentRepository(db=setup_mock_db)

    # 1. Cameras: 2 with valid coordinates, 1 with zero coordinates
    cam1 = {
        "camera_id": "CAM-001",
        "name": "North Gate Surveillance",
        "location_name": "Terminal 1 Gate A",
        "latitude": 28.5562,
        "longitude": 77.1000,
        "rtsp_url": "rtsp://admin:SecretPass123@192.168.1.101:554/h264",
        "status": "ONLINE",
        "detection_mode": "BOTH",
        "is_active": True,
    }
    cam2 = {
        "camera_id": "CAM-002",
        "name": "Central Plaza Camera",
        "location_name": "Main Food Court",
        "latitude": 28.5600,
        "longitude": 77.1050,
        "rtsp_url": "rtsp://operator:CameraPass456@192.168.1.102:554/live",
        "status": "OFFLINE",
        "detection_mode": "SOLID",
        "is_active": True,
    }
    cam3_no_coords = {
        "camera_id": "CAM-003",
        "name": "Warehouse Camera",
        "location_name": "Basement Storage",
        "latitude": 0.0,
        "longitude": 0.0,
        "rtsp_url": "rtsp://192.168.1.103:554/stream",
        "status": "ONLINE",
        "detection_mode": "LIQUID",
        "is_active": False,
    }

    asyncio.run(cam_repo.create(cam1))
    asyncio.run(cam_repo.create(cam2))
    asyncio.run(cam_repo.create(cam3_no_coords))

    # 2. Incidents with varied attributes and dates
    now = datetime.now(timezone.utc)
    two_days_ago = now - timedelta(days=2)
    five_days_ago = now - timedelta(days=5)

    incidents = [
        {
            "incident_id": "INC-20260901-000001",
            "camera_id": "CAM-001",
            "waste_type": "SOLID",
            "category": "plastic_bottle",
            "confidence": 0.94,
            "severity": "MEDIUM",
            "status": "NEW",
            "snapshot_path": "snapshots/snap1.jpg",
            "timestamp": now,
        },
        {
            "incident_id": "INC-20260901-000002",
            "camera_id": "CAM-001",
            "waste_type": "SOLID",
            "category": "garbage_pile",
            "confidence": 0.88,
            "severity": "CRITICAL",
            "status": "ACKNOWLEDGED",
            "snapshot_path": "snapshots/snap2.jpg",
            "timestamp": two_days_ago,
        },
        {
            "incident_id": "INC-20260901-000003",
            "camera_id": "CAM-001",
            "waste_type": "LIQUID",
            "category": "sewage_overflow",
            "confidence": 0.91,
            "severity": "HIGH",
            "status": "RESOLVED",
            "snapshot_path": "snapshots/snap3.jpg",
            "timestamp": five_days_ago,
        },
        {
            "incident_id": "INC-20260901-000004",
            "camera_id": "CAM-002",
            "waste_type": "SOLID",
            "category": "can",
            "confidence": 0.82,
            "severity": "LOW",
            "status": "DISMISSED",
            "snapshot_path": "snapshots/snap4.jpg",
            "timestamp": now,
        },
        {
            "incident_id": "INC-20260901-000005",
            "camera_id": "CAM-003",  # No coords
            "waste_type": "LIQUID",
            "category": "liquid_spill",
            "confidence": 0.89,
            "severity": "MEDIUM",
            "status": "NEW",
            "snapshot_path": "snapshots/snap5.jpg",
            "timestamp": now,
        },
    ]

    for inc in incidents:
        asyncio.run(inc_repo.create(inc))

    return {"cams": [cam1, cam2, cam3_no_coords], "incidents": incidents}


# ============================================================================
# 1-5: Map Cameras Tests
# ============================================================================

def test_1_map_cameras_endpoint_returns_cameras_with_coordinates(client, auth_headers, populated_dataset):
    """GET /api/v1/map/cameras returns cameras that have valid coordinates."""
    resp = client.get("/api/v1/map/cameras", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    cam_ids = [c["camera_id"] for c in items]
    assert "CAM-001" in cam_ids
    assert "CAM-002" in cam_ids


def test_2_map_cameras_excludes_zero_coordinates(client, auth_headers, populated_dataset):
    """Cameras with (0.0, 0.0) coordinates are excluded from GIS map projection."""
    resp = client.get("/api/v1/map/cameras", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    cam_ids = [c["camera_id"] for c in items]
    assert "CAM-003" not in cam_ids


def test_3_map_cameras_excludes_rtsp_credentials(client, auth_headers, populated_dataset):
    """Ensure no RTSP URL or plaintext password leaks through map camera payloads."""
    resp = client.get("/api/v1/map/cameras", headers=auth_headers)
    assert resp.status_code == 200
    text = resp.text
    assert "SecretPass123" not in text
    assert "CameraPass456" not in text
    assert "rtsp://" not in text


def test_4_map_cameras_requires_authentication(client, populated_dataset):
    """Unauthenticated requests to /map/cameras are rejected with 401."""
    resp = client.get("/api/v1/map/cameras")
    assert resp.status_code == 401


def test_5_map_cameras_filter_is_active(client, auth_headers, populated_dataset):
    """Filter map cameras by is_active query parameter."""
    resp = client.get("/api/v1/map/cameras?is_active=true", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    for item in items:
        assert item["is_active"] is True


# ============================================================================
# 6-11: Map Incidents Tests
# ============================================================================

def test_6_map_incidents_endpoint_returns_mapped_incidents(client, auth_headers, populated_dataset):
    """GET /api/v1/map/incidents returns incidents with coordinates from parent cameras."""
    resp = client.get("/api/v1/map/incidents", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    # 4 incidents belong to CAM-001 and CAM-002 (valid coords); 1 belongs to CAM-003 (no coords)
    assert len(items) == 4
    for itm in items:
        assert itm["latitude"] != 0.0
        assert itm["longitude"] != 0.0
        assert itm["camera_name"] != ""


def test_7_map_incidents_filter_by_waste_type(client, auth_headers, populated_dataset):
    """Filter map incidents by SOLID or LIQUID waste type."""
    resp_solid = client.get("/api/v1/map/incidents?waste_type=SOLID", headers=auth_headers)
    assert resp_solid.status_code == 200
    for itm in resp_solid.json():
        assert itm["waste_type"] == "SOLID"

    resp_liquid = client.get("/api/v1/map/incidents?waste_type=LIQUID", headers=auth_headers)
    assert resp_liquid.status_code == 200
    for itm in resp_liquid.json():
        assert itm["waste_type"] == "LIQUID"


def test_8_map_incidents_filter_by_severity(client, auth_headers, populated_dataset):
    """Filter map incidents by severity level."""
    resp = client.get("/api/v1/map/incidents?severity=CRITICAL", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["incident_id"] == "INC-20260901-000002"
    assert items[0]["severity"] == "CRITICAL"


def test_9_map_incidents_filter_by_status(client, auth_headers, populated_dataset):
    """Filter map incidents by lifecycle status."""
    resp = client.get("/api/v1/map/incidents?status=RESOLVED", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["incident_id"] == "INC-20260901-000003"
    assert items[0]["status"] == "RESOLVED"


def test_10_map_incidents_excludes_zero_coordinate_cameras(client, auth_headers, populated_dataset):
    """Incidents belonging to camera without coordinates (CAM-003) are omitted from map."""
    resp = client.get("/api/v1/map/incidents", headers=auth_headers)
    assert resp.status_code == 200
    ids = [i["incident_id"] for i in resp.json()]
    assert "INC-20260901-000005" not in ids


def test_11_map_incidents_requires_authentication(client, populated_dataset):
    """Unauthenticated requests to /map/incidents are rejected with 401."""
    resp = client.get("/api/v1/map/incidents")
    assert resp.status_code == 401


# ============================================================================
# 12-19: Analytics Summary Tests
# ============================================================================

def test_12_analytics_summary_total_and_active_counts(client, auth_headers, populated_dataset):
    """GET /api/v1/analytics/summary returns accurate total and active violation metrics."""
    resp = client.get("/api/v1/analytics/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_incidents"] == 5
    # Active = NEW (2) + ACKNOWLEDGED (1) = 3
    assert data["active_incidents"] == 3
    assert data["resolved_incidents"] == 1
    assert data["dismissed_incidents"] == 1


def test_13_analytics_summary_resolution_rate(client, auth_headers, populated_dataset):
    """Calculates resolution rate as percentage of resolved / total."""
    resp = client.get("/api/v1/analytics/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    # 1 resolved out of 5 total = 20.0%
    assert data["resolution_rate"] == 20.0


def test_14_analytics_summary_waste_type_breakdown(client, auth_headers, populated_dataset):
    """Accurately breaks down solid vs liquid incidents."""
    resp = client.get("/api/v1/analytics/summary", headers=auth_headers)
    assert resp.status_code == 200
    breakdown = resp.json()["waste_type_breakdown"]
    assert breakdown["SOLID"] == 3
    assert breakdown["LIQUID"] == 2


def test_15_analytics_summary_category_breakdown(client, auth_headers, populated_dataset):
    """Returns sorted category counts."""
    resp = client.get("/api/v1/analytics/summary", headers=auth_headers)
    assert resp.status_code == 200
    categories = resp.json()["category_breakdown"]
    assert len(categories) >= 4
    cat_names = [c["category"] for c in categories]
    assert "plastic_bottle" in cat_names
    assert "garbage_pile" in cat_names


def test_16_analytics_summary_camera_and_location_breakdown(client, auth_headers, populated_dataset):
    """Aggregates incidents per camera and per geographic zone."""
    resp = client.get("/api/v1/analytics/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    cams = data["camera_breakdown"]
    assert len(cams) >= 2
    # CAM-001 has 3 incidents
    cam1_stat = next(c for c in cams if c["camera_id"] == "CAM-001")
    assert cam1_stat["count"] == 3

    locs = data["location_breakdown"]
    assert len(locs) >= 2


def test_17_analytics_summary_date_filtering(client, auth_headers, populated_dataset):
    """Filters longitudinal metrics by start_date."""
    # Filter for only recent incidents (last 24 hours)
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = client.get("/api/v1/analytics/summary", params={"start_date": yesterday}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    # Only 3 incidents happened today/now
    assert data["total_incidents"] == 3


def test_18_analytics_summary_invalid_date_range_rejected(client, auth_headers, populated_dataset):
    """Rejects start_date > end_date with HTTP 400."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    past = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = client.get("/api/v1/analytics/summary", params={"start_date": now, "end_date": past}, headers=auth_headers)
    assert resp.status_code == 400
    assert "start_date cannot be after end_date" in resp.json()["detail"]


def test_19_analytics_summary_requires_authentication(client, populated_dataset):
    """Unauthenticated requests to /analytics/summary are rejected with 401."""
    resp = client.get("/api/v1/analytics/summary")
    assert resp.status_code == 401


# ============================================================================
# 20-25: Municipal CSV and PDF Reports Tests
# ============================================================================

def test_20_reports_csv_generation_valid_rfc4180(client, auth_headers, populated_dataset):
    """GET /api/v1/reports/incidents.csv generates RFC-4180 compliant CSV format."""
    resp = client.get("/api/v1/reports/incidents.csv", headers=auth_headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment; filename=" in resp.headers["content-disposition"]

    reader = csv.reader(io.StringIO(resp.text))
    rows = list(reader)
    header = rows[0]
    assert "Incident ID" in header
    assert "Camera Name" in header
    assert "Waste Type" in header
    assert len(rows) >= 6  # Header + 5 records


def test_21_reports_csv_audit_log_created(setup_mock_db, client, auth_headers, populated_dataset):
    """Generating CSV report records an audit log entry."""
    resp = client.get("/api/v1/reports/incidents.csv", headers=auth_headers)
    assert resp.status_code == 200

    audit_repo = AuditRepository(db=setup_mock_db)
    logs, total = asyncio.run(audit_repo.list(action="GENERATE_CSV_REPORT", limit=10))
    assert total >= 1
    assert logs[0]["action"] == "GENERATE_CSV_REPORT"
    assert logs[0]["resource_type"] == "report"


def test_22_reports_pdf_generation_valid_bytes(client, auth_headers, populated_dataset):
    """GET /api/v1/reports/incidents.pdf generates valid PDF document starting with %PDF-."""
    resp = client.get("/api/v1/reports/incidents.pdf", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment; filename=" in resp.headers["content-disposition"]
    # PDF magic bytes
    assert resp.content.startswith(b"%PDF-")
    assert len(resp.content) > 1000


def test_23_reports_pdf_audit_log_created(setup_mock_db, client, auth_headers, populated_dataset):
    """Generating PDF report records an audit log entry."""
    resp = client.get("/api/v1/reports/incidents.pdf", headers=auth_headers)
    assert resp.status_code == 200

    audit_repo = AuditRepository(db=setup_mock_db)
    logs, total = asyncio.run(audit_repo.list(action="GENERATE_PDF_REPORT", limit=10))
    assert total >= 1
    assert logs[0]["action"] == "GENERATE_PDF_REPORT"
    assert logs[0]["resource_type"] == "report"


def test_24_reports_date_validation_rejected(client, auth_headers, populated_dataset):
    """Exporting reports with start_date > end_date returns HTTP 400 for both CSV and PDF."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    past = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

    resp_csv = client.get("/api/v1/reports/incidents.csv", params={"start_date": now, "end_date": past}, headers=auth_headers)
    assert resp_csv.status_code == 400

    resp_pdf = client.get("/api/v1/reports/incidents.pdf", params={"start_date": now, "end_date": past}, headers=auth_headers)
    assert resp_pdf.status_code == 400


def test_25_reports_no_credential_leakage(client, auth_headers, populated_dataset):
    """Audit test verifying reports do NOT contain passwords, RTSP URLs, or auth secrets."""
    resp_csv = client.get("/api/v1/reports/incidents.csv", headers=auth_headers)
    assert resp_csv.status_code == 200
    csv_text = resp_csv.text

    assert "SecretPass123" not in csv_text
    assert "CameraPass456" not in csv_text
    assert "rtsp://" not in csv_text

    resp_pdf = client.get("/api/v1/reports/incidents.pdf", headers=auth_headers)
    assert resp_pdf.status_code == 200
    pdf_bytes = resp_pdf.content

    assert b"SecretPass123" not in pdf_bytes
    assert b"CameraPass456" not in pdf_bytes
    assert b"rtsp://" not in pdf_bytes
