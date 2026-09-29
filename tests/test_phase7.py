"""Phase 7 Test Suite: React Admin Dashboard Frontend API & Integration Contracts.

Verifies:
1. Login page contract & JWT response
2. Successful authentication and /auth/me resolution
3. Invalid login handling and error response
4. Protected route enforcement (401 without Bearer token)
5. Logout token clearance contract
6. Dashboard KPIs and aggregation data contracts
7. Incident list rendering contract
8. Incident filtering combinations (Camera, Status, Severity, Waste Type, Category)
9. Incident pagination boundary checks
10. Incident details data schema (Solid tracking & Liquid area telemetry)
11. Incident status update workflow (NEW -> ACKNOWLEDGED -> RESOLVED)
12. Camera list contract
13. Camera registration modal payload handling
14. Camera credential masking safety in responses
15. Admin-only user management page contract
16. Operator restricted from user management (403)
17. Standardized API error handling for frontend ErrorAlert
18. Empty states data handling
19. Secure snapshot streaming endpoint (GET /incidents/{id}/snapshot)
20. Frontend production build artifacts verification
"""
import os
import pytest
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from backend.app.core.config import settings
from backend.app.db.mongodb import async_db_manager
from backend.app.main import app
from backend.scripts.create_admin import bootstrap_admin
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.repositories.camera_repository import CameraRepository


@pytest.fixture(autouse=True)
def setup_mock_db():
    """Sets up an isolated in-memory MongoDB instance for each test."""
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["frontend_test_db"]
    async_db_manager.set_mock_database(mock_db)
    yield mock_db
    mock_client.close()


@pytest.fixture
def client():
    """Provides a FastAPI TestClient."""
    return TestClient(app)


@pytest.fixture
def admin_token(setup_mock_db, client):
    """Bootstraps admin and returns auth token header."""
    asyncio.run(bootstrap_admin(db=setup_mock_db))
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operator_token(setup_mock_db, client, admin_token):
    """Creates operator and returns auth token header."""
    op_payload = {
        "email": "frontend_op@cleanliness.gov.in",
        "username": "frontend_op",
        "full_name": "Frontend Operator",
        "role": "OPERATOR",
        "password": "SecurePassword!2026",
    }
    client.post("/api/v1/users/", json=op_payload, headers=admin_token)
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "frontend_op", "password": "SecurePassword!2026"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# 1. Login page contract & JWT response
def test_login_page_contract(setup_mock_db, client):
    asyncio.run(bootstrap_admin(db=setup_mock_db))
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data
    assert data["user"]["username"] == settings.ADMIN_USERNAME.lower()


# 2. Successful authentication and /auth/me resolution
def test_successful_authentication(client, admin_token):
    resp = client.get("/api/v1/auth/me", headers=admin_token)
    assert resp.status_code == 200
    user = resp.json()
    assert user["role"] == "ADMIN"
    assert "password_hash" not in user


# 3. Invalid login handling and error response
def test_invalid_login_handling(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "non_existent_user", "password": "BadPassword"},
    )
    assert resp.status_code == 401
    assert "Invalid credentials" in resp.json()["detail"]


# 4. Protected route enforcement (401 without Bearer token)
def test_protected_route_unauthenticated(client):
    resp = client.get("/api/v1/incidents/")
    assert resp.status_code == 401


# 5. Logout token clearance contract
def test_logout_token_contract(client):
    # Simulated invalid token after client removes from localStorage
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalidated_token"})
    assert resp.status_code == 401


# 6. Dashboard KPIs and aggregation data contracts
def test_dashboard_kpis_data_contracts(client, operator_token):
    cam_resp = client.get("/api/v1/cameras/", headers=operator_token)
    assert cam_resp.status_code == 200
    assert isinstance(cam_resp.json(), list)

    inc_resp = client.get("/api/v1/incidents/", headers=operator_token)
    assert inc_resp.status_code == 200
    inc_data = inc_resp.json()
    assert "items" in inc_data
    assert "total" in inc_data


# 7. Incident list rendering contract
def test_incident_list_rendering_contract(setup_mock_db, client, operator_token):
    repo = IncidentRepository(db=setup_mock_db)
    asyncio.run(
        repo.create({
            "incident_id": "INC-FE-001",
            "camera_id": "CAM-01",
            "waste_type": "SOLID",
            "category": "plastic_bottle",
            "confidence": 0.92,
            "snapshot_path": "storage/snapshots/test.jpg",
            "timestamp": datetime.now(timezone.utc),
            "severity": "HIGH",
            "status": "NEW",
        })
    )
    resp = client.get("/api/v1/incidents/", headers=operator_token)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) >= 1
    item = data["items"][0]
    assert item["incident_id"] == "INC-FE-001"
    assert item["category"] == "plastic_bottle"


# 8. Incident filtering combinations
def test_incident_filtering_combinations(setup_mock_db, client, operator_token):
    repo = IncidentRepository(db=setup_mock_db)
    asyncio.run(
        repo.create({
            "incident_id": "INC-FILTER-1",
            "camera_id": "CAM-NORTH",
            "waste_type": "SOLID",
            "category": "paper",
            "confidence": 0.85,
            "snapshot_path": "snap1.jpg",
            "timestamp": datetime.now(timezone.utc),
            "severity": "LOW",
            "status": "NEW",
        })
    )
    asyncio.run(
        repo.create({
            "incident_id": "INC-FILTER-2",
            "camera_id": "CAM-SOUTH",
            "waste_type": "LIQUID",
            "category": "sewage_overflow",
            "confidence": 0.95,
            "snapshot_path": "snap2.jpg",
            "timestamp": datetime.now(timezone.utc),
            "severity": "CRITICAL",
            "status": "RESOLVED",
        })
    )

    # Filter by waste_type
    resp = client.get("/api/v1/incidents/?waste_type=LIQUID", headers=operator_token)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["waste_type"] == "LIQUID"

    # Filter by severity
    resp_sev = client.get("/api/v1/incidents/?severity=CRITICAL", headers=operator_token)
    assert resp_sev.status_code == 200
    assert resp_sev.json()["items"][0]["severity"] == "CRITICAL"


# 9. Incident pagination boundary checks
def test_incident_pagination_boundary(setup_mock_db, client, operator_token):
    repo = IncidentRepository(db=setup_mock_db)
    for i in range(7):
        asyncio.run(
            repo.create({
                "incident_id": f"INC-PAGINATE-{i}",
                "camera_id": "CAM-01",
                "waste_type": "SOLID",
                "category": "can",
                "confidence": 0.80,
                "snapshot_path": "snap.jpg",
                "timestamp": datetime.now(timezone.utc),
                "severity": "MEDIUM",
            })
        )
    resp = client.get("/api/v1/incidents/?page=1&page_size=3", headers=operator_token)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 3
    assert data["total"] >= 7
    assert data["total_pages"] >= 3


# 10. Incident details data schema
def test_incident_details_schema(setup_mock_db, client, operator_token):
    repo = IncidentRepository(db=setup_mock_db)
    asyncio.run(
        repo.create({
            "incident_id": "INC-DETAILS-TEST",
            "camera_id": "CAM-01",
            "waste_type": "SOLID",
            "category": "plastic_bag",
            "confidence": 0.88,
            "snapshot_path": "storage/snapshots/test.jpg",
            "timestamp": datetime.now(timezone.utc),
            "severity": "HIGH",
            "bounding_box": [100, 150, 200, 250],
            "track_id": 42,
        })
    )
    resp = client.get("/api/v1/incidents/INC-DETAILS-TEST", headers=operator_token)
    assert resp.status_code == 200
    data = resp.json()
    assert data["track_id"] == 42
    assert data["bounding_box"] == [100, 150, 200, 250]


# 11. Incident status update workflow
def test_incident_status_update_workflow(setup_mock_db, client, operator_token):
    repo = IncidentRepository(db=setup_mock_db)
    asyncio.run(
        repo.create({
            "incident_id": "INC-STATUS-FLOW",
            "camera_id": "CAM-01",
            "waste_type": "SOLID",
            "category": "food_waste",
            "confidence": 0.82,
            "snapshot_path": "snap.jpg",
            "timestamp": datetime.now(timezone.utc),
            "severity": "MEDIUM",
            "status": "NEW",
        })
    )

    # Transition to ACKNOWLEDGED
    resp1 = client.patch(
        "/api/v1/incidents/INC-STATUS-FLOW/status",
        json={"status": "ACKNOWLEDGED", "notes": "Dispatched sanitization"},
        headers=operator_token,
    )
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "ACKNOWLEDGED"

    # Transition to RESOLVED
    resp2 = client.patch(
        "/api/v1/incidents/INC-STATUS-FLOW/status",
        json={"status": "RESOLVED", "notes": "Area cleaned and verified"},
        headers=operator_token,
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "RESOLVED"
    assert resp2.json()["resolved_at"] is not None


# 12. Camera list contract
def test_camera_list_contract(client, operator_token):
    resp = client.get("/api/v1/cameras/", headers=operator_token)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# 13. Camera registration modal payload handling
def test_camera_registration_modal_payload(client, admin_token):
    payload = {
        "camera_id": "CAM-FE-REG-01",
        "name": "Frontend Register Test",
        "location_name": "Gate 4",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "rtsp_url": "rtsp://camera_admin:MySecretPass@192.168.1.100:554/live",
        "detection_mode": "BOTH",
        "target_fps": 5.0,
    }
    resp = client.post("/api/v1/cameras/", json=payload, headers=admin_token)
    assert resp.status_code == 201
    assert resp.json()["camera_id"] == "CAM-FE-REG-01"


# 14. Camera credential masking safety in responses
def test_camera_credential_masking_frontend_safety(client, admin_token, operator_token):
    payload = {
        "camera_id": "CAM-MASK-CHECK",
        "name": "Mask Check Camera",
        "location_name": "South Zone",
        "latitude": 28.61,
        "longitude": 77.20,
        "rtsp_url": "rtsp://operator_user:SensitivePassword123@10.0.0.1:554/stream",
        "detection_mode": "SOLID",
    }
    client.post("/api/v1/cameras/", json=payload, headers=admin_token)

    # Retrieval via operator
    get_resp = client.get("/api/v1/cameras/CAM-MASK-CHECK", headers=operator_token)
    assert get_resp.status_code == 200
    masked_url = get_resp.json()["rtsp_url"]
    assert "SensitivePassword123" not in masked_url
    assert "***" in masked_url


# 15. Admin-only user management page contract
def test_admin_only_user_page(client, admin_token):
    resp = client.get("/api/v1/users/", headers=admin_token)
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    assert len(users) >= 1


# 16. Operator restricted from user management
def test_operator_restricted_from_users(client, operator_token):
    resp = client.get("/api/v1/users/", headers=operator_token)
    assert resp.status_code == 403


# 17. Standardized API error handling
def test_standardized_api_error_handling(client, operator_token):
    resp = client.get("/api/v1/incidents/NON_EXISTENT_ID_9999", headers=operator_token)
    assert resp.status_code == 404
    assert "detail" in resp.json()


# 18. Empty states data handling
def test_empty_states_data_handling(client, operator_token):
    resp = client.get("/api/v1/incidents/?category=unheard_of_category_xyz", headers=operator_token)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


# 19. Secure snapshot streaming endpoint
def test_snapshot_streaming_endpoint(setup_mock_db, client, operator_token, tmp_path):
    repo = IncidentRepository(db=setup_mock_db)

    # Create dummy snapshot image in storage/snapshots
    snap_dir = settings.SNAPSHOT_STORAGE_DIR
    snap_dir.mkdir(parents=True, exist_ok=True)
    test_img = (snap_dir / "test_snapshot_fe.jpg").resolve()
    test_img.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB")

    rel_path = str(test_img.relative_to(settings.BASE_DIR.resolve()))

    asyncio.run(
        repo.create({
            "incident_id": "INC-SNAP-STREAM-01",
            "camera_id": "CAM-01",
            "waste_type": "SOLID",
            "category": "paper",
            "confidence": 0.90,
            "snapshot_path": rel_path,
            "timestamp": datetime.now(timezone.utc),
            "severity": "LOW",
        })
    )

    # Request snapshot via authenticated API
    snap_resp = client.get("/api/v1/incidents/INC-SNAP-STREAM-01/snapshot", headers=operator_token)
    assert snap_resp.status_code == 200
    assert snap_resp.headers["content-type"].startswith("image/")
    assert len(snap_resp.content) > 0


# 20. Frontend production build artifacts verification
def test_frontend_production_build_artifacts():
    dist_dir = Path(settings.BASE_DIR) / "frontend" / "dist"
    index_html = dist_dir / "index.html"
    assets_dir = dist_dir / "assets"

    assert dist_dir.is_dir(), "Frontend dist directory missing"
    assert index_html.is_file(), "Frontend dist/index.html missing"
    assert assets_dir.is_dir(), "Frontend dist/assets directory missing"

    content = index_html.read_text(encoding="utf-8")
    assert '<div id="root"></div>' in content
    assert "Cleanliness Monitoring" in content
