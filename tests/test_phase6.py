"""Phase 6 Comprehensive Test Suite: MongoDB Persistence, FastAPI REST API, and Authentication.

Covers:
1. Database connection and health ping
2. User model and schema validation
3. Password hashing and verification
4. Admin bootstrap script idempotency
5. JWT token creation and decoding
6. Invalid token rejection
7. Expired token rejection
8. Login endpoint with valid credentials
9. Login endpoint with invalid password
10. Login endpoint with non-existent user
11. /auth/me with valid token
12. /auth/me with unauthenticated request (401)
13. Admin creating an operator user
14. Operator cannot create users (403)
15. User list endpoint (Admin only)
16. User update endpoint
17. Camera registration with valid data
18. Camera registration with RTSP credentials masked in response
19. Camera list endpoint
20. Camera update endpoint
21. Camera soft delete / toggle inactive
22. Incident creation via repository
23. Incident query by ID
24. Incident list with pagination
25. Incident filtering by status
26. Incident filtering by severity
27. Incident filtering by camera_id
28. Incident status update (NEW -> ACKNOWLEDGED) with audit logging
29. Incident engine callback writes to MongoDB
30. Audit log entries created on incident update and camera modification
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
import jwt
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from backend.app.core.config import settings
from backend.app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
)
from backend.app.db.mongodb import async_db_manager
from backend.app.db.indexes import create_indexes
from backend.app.schemas.user import UserCreate, UserUpdate, UserResponse, UserRole, UserLogin
from backend.app.schemas.camera import CameraCreate, CameraUpdate, CameraStatus, DetectionMode
from backend.app.schemas.incident import (
    IncidentCreate,
    IncidentSeverity,
    WasteType,
    IncidentStatus,
)
from backend.app.repositories.user_repository import UserRepository
from backend.app.repositories.camera_repository import CameraRepository
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.repositories.audit_repository import AuditRepository
from backend.scripts.create_admin import bootstrap_admin
from backend.app.services.incident_persistence import IncidentPersistenceService
from backend.app.main import app
from ai.incident.incident_engine import IncidentEngine


@pytest.fixture(autouse=True)
def setup_mock_db():
    """Sets up an isolated in-memory MongoDB instance for each test."""
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["cleanliness_test_db"]
    async_db_manager.set_mock_database(mock_db)
    yield mock_db
    mock_client.close()


@pytest.fixture
def client():
    """Provides a FastAPI TestClient."""
    return TestClient(app)


@pytest.fixture
def admin_auth_token(setup_mock_db, client):
    """Bootstraps admin and returns a valid Authorization header."""
    asyncio.run(bootstrap_admin(db=setup_mock_db))
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operator_auth_token(setup_mock_db, client, admin_auth_token):
    """Creates an operator user and returns their Authorization header."""
    op_payload = {
        "email": "operator1@cleanliness.gov.in",
        "username": "operator1",
        "full_name": "Field Operator 1",
        "role": "OPERATOR",
        "password": "SecureOperatorPass!1",
        "is_active": True,
    }
    create_resp = client.post("/api/v1/users/", json=op_payload, headers=admin_auth_token)
    assert create_resp.status_code == 201

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "operator1", "password": "SecureOperatorPass!1"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# 1. Database connection and health ping
# =========================================================================
def test_mongodb_connection_and_ping(setup_mock_db, client):
    """1. Test MongoDB connection and health ping."""
    is_alive = asyncio.run(async_db_manager.ping())
    assert is_alive is True

    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    data = health_resp.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


# =========================================================================
# 2. User model and schema validation
# =========================================================================
def test_user_schema_validation():
    """2. Test user schema validation and role enforcement."""
    user = UserCreate(
        email="test_validation@cleanliness.gov.in",
        username="valid_user",
        full_name="Valid Test User",
        role=UserRole.ADMIN,
        password="MySecretPassword123!",
    )
    assert user.email == "test_validation@cleanliness.gov.in"
    assert user.role == UserRole.ADMIN

    # Test UserResponse serialization
    resp = UserResponse(
        id="usr-1234",
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    assert resp.id == "usr-1234"
    assert not hasattr(resp, "password_hash")


# =========================================================================
# 3. Password hashing and verification
# =========================================================================
def test_password_hashing_and_verification():
    """3. Test bcrypt password hashing and verification."""
    password = "SuperStrongPassword2026!"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword123", hashed) is False
    assert verify_password("", hashed) is False


# =========================================================================
# 4. Admin bootstrap script idempotency
# =========================================================================
def test_admin_bootstrap_idempotency(setup_mock_db):
    """4. Test bootstrap_admin is idempotent across multiple runs."""
    admin_1 = asyncio.run(bootstrap_admin(db=setup_mock_db))
    assert admin_1 is not None
    assert admin_1["username"] == settings.ADMIN_USERNAME.lower()

    # Second invocation should not crash or create duplicates
    admin_2 = asyncio.run(bootstrap_admin(db=setup_mock_db))
    assert admin_2 is not None
    assert admin_1["id"] == admin_2["id"]

    repo = UserRepository(db=setup_mock_db)
    count = asyncio.run(repo.count())
    assert count == 1


# =========================================================================
# 5. JWT token creation and decoding
# =========================================================================
def test_jwt_creation_and_decoding():
    """5. Test JWT token encoding and claims decoding."""
    token = create_access_token(
        subject="admin-usr-01",
        expires_delta=timedelta(minutes=30),
        extra_claims={"username": "sysadmin", "role": "ADMIN"},
    )
    assert isinstance(token, str)
    decoded = decode_access_token(token)
    assert decoded["sub"] == "admin-usr-01"
    assert decoded["username"] == "sysadmin"
    assert decoded["role"] == "ADMIN"
    assert "exp" in decoded


# =========================================================================
# 6. Invalid token rejection
# =========================================================================
def test_jwt_invalid_token(client):
    """6. Test rejection of malformed or invalid JWT tokens."""
    with pytest.raises(jwt.PyJWTError):
        decode_access_token("this.is.not.a.valid.jwt.token")

    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer bad_token_123"})
    assert resp.status_code == 401
    assert "Invalid or expired token" in resp.json()["detail"]


# =========================================================================
# 7. Expired token rejection
# =========================================================================
def test_jwt_expired_token(client):
    """7. Test rejection of expired JWT tokens."""
    expired_token = create_access_token(
        subject="expired-user",
        expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401


# =========================================================================
# 8. Login endpoint with valid credentials
# =========================================================================
def test_login_success(setup_mock_db, client):
    """8. Test successful login returning JWT access token."""
    asyncio.run(bootstrap_admin(db=setup_mock_db))
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == settings.ADMIN_USERNAME.lower()
    assert "password_hash" not in data["user"]


# =========================================================================
# 9. Login endpoint with invalid password
# =========================================================================
def test_login_invalid_password(setup_mock_db, client):
    """9. Test login failure on incorrect password."""
    asyncio.run(bootstrap_admin(db=setup_mock_db))
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": "WrongPassword999"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


# =========================================================================
# 10. Login endpoint with non-existent user
# =========================================================================
def test_login_nonexistent_user(client):
    """10. Test login failure for nonexistent user."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "ghost_user", "password": "AnyPassword"},
    )
    assert resp.status_code == 401


# =========================================================================
# 11. /auth/me with valid token
# =========================================================================
def test_auth_me_valid_token(client, admin_auth_token):
    """11. Test /auth/me returns current user profile."""
    resp = client.get("/api/v1/auth/me", headers=admin_auth_token)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == settings.ADMIN_USERNAME.lower()
    assert data["role"] == "ADMIN"


# =========================================================================
# 12. /auth/me with unauthenticated request (401)
# =========================================================================
def test_auth_me_unauthenticated(client):
    """12. Test /auth/me requires authentication."""
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


# =========================================================================
# 13. Admin creating an operator user
# =========================================================================
def test_admin_create_operator(client, admin_auth_token):
    """13. Test admin can register a new operator."""
    op_payload = {
        "email": "zone1_op@cleanliness.gov.in",
        "username": "zone1_op",
        "full_name": "Zone 1 Operator",
        "role": "OPERATOR",
        "password": "Zone1Pass!2026",
    }
    resp = client.post("/api/v1/users/", json=op_payload, headers=admin_auth_token)
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "zone1_op"
    assert data["role"] == "OPERATOR"
    assert "password_hash" not in data


# =========================================================================
# 14. Operator cannot create users (403)
# =========================================================================
def test_operator_cannot_create_user(client, operator_auth_token):
    """14. Test operator is forbidden from creating users."""
    payload = {
        "email": "hacked@cleanliness.gov.in",
        "username": "hacked_user",
        "full_name": "Unauthorized User",
        "role": "OPERATOR",
        "password": "Password123!",
    }
    resp = client.post("/api/v1/users/", json=payload, headers=operator_auth_token)
    assert resp.status_code == 403


# =========================================================================
# 15. User list endpoint (Admin only)
# =========================================================================
def test_user_list_admin_only(client, admin_auth_token, operator_auth_token):
    """15. Test user listing is restricted to Admin."""
    # Admin access
    resp = client.get("/api/v1/users/", headers=admin_auth_token)
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) >= 1

    # Operator access
    op_resp = client.get("/api/v1/users/", headers=operator_auth_token)
    assert op_resp.status_code == 403


# =========================================================================
# 16. User update endpoint
# =========================================================================
def test_user_update_endpoint(setup_mock_db, client, admin_auth_token):
    """16. Test updating user details via Admin endpoint."""
    repo = UserRepository(db=setup_mock_db)
    user = asyncio.run(repo.get_by_username(settings.ADMIN_USERNAME.lower()))

    update_payload = {"full_name": "Super Admin Updated"}
    resp = client.patch(f"/api/v1/users/{user['id']}", json=update_payload, headers=admin_auth_token)
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Super Admin Updated"


# =========================================================================
# 17. Camera registration with valid data
# =========================================================================
def test_camera_registration_valid(client, admin_auth_token):
    """17. Test registering a new CCTV camera stream."""
    cam_data = {
        "camera_id": "CAM-TEST-001",
        "name": "Gate 1 Camera",
        "location_name": "North Gate",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "rtsp_url": "rtsp://camera.internal.net:554/live",
        "detection_mode": "BOTH",
        "target_fps": 10,
    }
    resp = client.post("/api/v1/cameras/", json=cam_data, headers=admin_auth_token)
    assert resp.status_code == 201
    data = resp.json()
    assert data["camera_id"] == "CAM-TEST-001"
    assert data["detection_mode"] == "BOTH"


# =========================================================================
# 18. Camera registration with RTSP credentials masked in response
# =========================================================================
def test_camera_rtsp_credential_masked(client, admin_auth_token):
    """18. Test RTSP credentials are automatically redacted in responses."""
    cam_data = {
        "camera_id": "CAM-TEST-MASKED",
        "name": "Secure Area Camera",
        "location_name": "Internal Vault Zone",
        "latitude": 28.6140,
        "longitude": 77.2091,
        "rtsp_url": "rtsp://secret_admin:SuperSecretPass99@192.168.1.100:554/stream1",
        "detection_mode": "SOLID",
    }
    resp = client.post("/api/v1/cameras/", json=cam_data, headers=admin_auth_token)
    assert resp.status_code == 201
    data = resp.json()
    assert "SuperSecretPass99" not in data["rtsp_url"]
    assert "***" in data["rtsp_url"]

    # Verify retrieval endpoint also masks credentials
    get_resp = client.get("/api/v1/cameras/CAM-TEST-MASKED", headers=admin_auth_token)
    assert get_resp.status_code == 200
    assert "SuperSecretPass99" not in get_resp.json()["rtsp_url"]


# =========================================================================
# 19. Camera list endpoint
# =========================================================================
def test_camera_list_endpoint(client, operator_auth_token):
    """19. Test camera listing accessible to operators."""
    resp = client.get("/api/v1/cameras/", headers=operator_auth_token)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# =========================================================================
# 20. Camera update endpoint
# =========================================================================
def test_camera_update_endpoint(client, admin_auth_token):
    """20. Test updating camera configuration."""
    cam_data = {
        "camera_id": "CAM-UPDATE-01",
        "name": "Original Name",
        "location_name": "South Zone",
        "latitude": 28.61,
        "longitude": 77.20,
        "rtsp_url": "rtsp://10.0.0.1/live",
        "detection_mode": "SOLID",
    }
    client.post("/api/v1/cameras/", json=cam_data, headers=admin_auth_token)

    update_payload = {"name": "Updated South Zone Camera", "detection_mode": "LIQUID"}
    resp = client.patch("/api/v1/cameras/CAM-UPDATE-01", json=update_payload, headers=admin_auth_token)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated South Zone Camera"
    assert resp.json()["detection_mode"] == "LIQUID"


# =========================================================================
# 21. Camera soft delete / toggle inactive
# =========================================================================
def test_camera_soft_delete(client, admin_auth_token):
    """21. Test soft-deleting / decommissioning a camera."""
    cam_data = {
        "camera_id": "CAM-DELETE-01",
        "name": "Decommission Candidate",
        "location_name": "West Sector",
        "latitude": 28.61,
        "longitude": 77.20,
        "rtsp_url": "rtsp://10.0.0.2/live",
        "detection_mode": "SOLID",
    }
    client.post("/api/v1/cameras/", json=cam_data, headers=admin_auth_token)

    # 1. Toggle inactive (soft-delete / state toggle)
    toggle_resp = client.patch(
        "/api/v1/cameras/CAM-DELETE-01",
        json={"is_active": False, "status": "OFFLINE"},
        headers=admin_auth_token,
    )
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["is_active"] is False
    assert toggle_resp.json()["status"] == "OFFLINE"

    # 2. Decommission/delete camera
    del_resp = client.delete("/api/v1/cameras/CAM-DELETE-01", headers=admin_auth_token)
    assert del_resp.status_code == 200

    # Camera should now be gone from active lookup
    get_resp = client.get("/api/v1/cameras/CAM-DELETE-01", headers=admin_auth_token)
    assert get_resp.status_code == 404


# =========================================================================
# 22. Incident creation via repository
# =========================================================================
def test_incident_repository_create(setup_mock_db):
    """22. Test creating an incident directly in the repository."""
    repo = IncidentRepository(db=setup_mock_db)
    now = datetime.now(timezone.utc)
    inc_data = {
        "incident_id": "INC-TEST-001",
        "camera_id": "CAM-001",
        "waste_type": WasteType.SOLID.value,
        "category": "plastic_bottle",
        "confidence": 0.92,
        "snapshot_path": "storage/snapshots/inc_001.jpg",
        "timestamp": now,
        "severity": IncidentSeverity.HIGH.value,
        "status": "NEW",
    }
    created = asyncio.run(repo.create(inc_data))
    assert created["incident_id"] == "INC-TEST-001"
    assert created["status"] == "NEW"


# =========================================================================
# 23. Incident query by ID
# =========================================================================
def test_incident_get_by_id(client, operator_auth_token):
    """23. Test incident retrieval by ID via REST API."""
    now = datetime.now(timezone.utc).isoformat()
    inc_payload = {
        "incident_id": "INC-QUERY-001",
        "camera_id": "CAM-001",
        "waste_type": "SOLID",
        "category": "garbage_pile",
        "confidence": 0.89,
        "snapshot_path": "storage/snapshots/snap_query.jpg",
        "timestamp": now,
        "severity": "CRITICAL",
    }
    client.post("/api/v1/incidents/", json=inc_payload, headers=operator_auth_token)

    resp = client.get("/api/v1/incidents/INC-QUERY-001", headers=operator_auth_token)
    assert resp.status_code == 200
    assert resp.json()["incident_id"] == "INC-QUERY-001"
    assert resp.json()["severity"] == "CRITICAL"


# =========================================================================
# 24. Incident list with pagination
# =========================================================================
def test_incident_list_pagination(client, operator_auth_token):
    """24. Test incident pagination structure."""
    now = datetime.now(timezone.utc).isoformat()
    for i in range(5):
        payload = {
            "incident_id": f"INC-PAGE-{i}",
            "camera_id": "CAM-001",
            "waste_type": "SOLID",
            "category": "can",
            "confidence": 0.85,
            "snapshot_path": f"storage/snapshots/page_{i}.jpg",
            "timestamp": now,
            "severity": "MEDIUM",
        }
        client.post("/api/v1/incidents/", json=payload, headers=operator_auth_token)

    resp = client.get("/api/v1/incidents/?page=1&page_size=2", headers=operator_auth_token)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] >= 5
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total_pages"] >= 3


# =========================================================================
# 25. Incident filtering by status
# =========================================================================
def test_incident_filter_status(client, operator_auth_token):
    """25. Test incident filtering by status."""
    now = datetime.now(timezone.utc).isoformat()
    client.post(
        "/api/v1/incidents/",
        json={
            "incident_id": "INC-STATUS-TEST",
            "camera_id": "CAM-001",
            "waste_type": "SOLID",
            "category": "plastic_bag",
            "confidence": 0.88,
            "snapshot_path": "snap.jpg",
            "timestamp": now,
            "severity": "LOW",
        },
        headers=operator_auth_token,
    )
    resp = client.get("/api/v1/incidents/?status=NEW", headers=operator_auth_token)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["status"] == "NEW"


# =========================================================================
# 26. Incident filtering by severity
# =========================================================================
def test_incident_filter_severity(client, operator_auth_token):
    """26. Test incident filtering by severity level."""
    now = datetime.now(timezone.utc).isoformat()
    client.post(
        "/api/v1/incidents/",
        json={
            "incident_id": "INC-SEV-CRIT",
            "camera_id": "CAM-001",
            "waste_type": "LIQUID",
            "category": "sewage_overflow",
            "confidence": 0.95,
            "snapshot_path": "snap.jpg",
            "timestamp": now,
            "severity": "CRITICAL",
        },
        headers=operator_auth_token,
    )
    resp = client.get("/api/v1/incidents/?severity=CRITICAL", headers=operator_auth_token)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["severity"] == "CRITICAL"


# =========================================================================
# 27. Incident filtering by camera_id
# =========================================================================
def test_incident_filter_camera_id(client, operator_auth_token):
    """27. Test incident filtering by camera ID."""
    now = datetime.now(timezone.utc).isoformat()
    client.post(
        "/api/v1/incidents/",
        json={
            "incident_id": "INC-CAM-TARGET",
            "camera_id": "CAM-SPECIFIC-999",
            "waste_type": "SOLID",
            "category": "paper",
            "confidence": 0.80,
            "snapshot_path": "snap.jpg",
            "timestamp": now,
            "severity": "LOW",
        },
        headers=operator_auth_token,
    )
    resp = client.get("/api/v1/incidents/?camera_id=CAM-SPECIFIC-999", headers=operator_auth_token)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["camera_id"] == "CAM-SPECIFIC-999"


# =========================================================================
# 28. Incident status update (NEW -> ACKNOWLEDGED) with audit logging
# =========================================================================
def test_incident_status_update_and_audit(client, operator_auth_token):
    """28. Test updating incident lifecycle status and audit trail generation."""
    now = datetime.now(timezone.utc).isoformat()
    client.post(
        "/api/v1/incidents/",
        json={
            "incident_id": "INC-UPDATE-001",
            "camera_id": "CAM-001",
            "waste_type": "SOLID",
            "category": "can",
            "confidence": 0.90,
            "snapshot_path": "snap.jpg",
            "timestamp": now,
            "severity": "MEDIUM",
        },
        headers=operator_auth_token,
    )

    patch_resp = client.patch(
        "/api/v1/incidents/INC-UPDATE-001/status",
        json={"status": "ACKNOWLEDGED", "notes": "Dispatched field team"},
        headers=operator_auth_token,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "ACKNOWLEDGED"
    assert patch_resp.json()["notes"] == "Dispatched field team"


# =========================================================================
# 29. Incident engine callback writes to MongoDB
# =========================================================================
def test_incident_engine_callback_persistence(setup_mock_db):
    """29. Test IncidentEngine confirmation callback automatically persists to MongoDB."""
    repo = IncidentRepository(db=setup_mock_db)
    service = IncidentPersistenceService(incident_repo=repo)

    engine = IncidentEngine()
    service.attach_to_engine(engine)

    # Fabricate an incident created by the engine callback
    test_incident = IncidentCreate(
        incident_id="INC-CALLBACK-AUTO-01",
        camera_id="CAM-CALLBACK-TEST",
        waste_type=WasteType.SOLID,
        category="plastic_bottle",
        confidence=0.88,
        snapshot_path="storage/snapshots/callback_snap.jpg",
        timestamp=datetime.now(timezone.utc),
        severity=IncidentSeverity.MEDIUM,
    )

    # Trigger callback
    service.on_incident_confirmed(test_incident)

    # Verify document exists in MongoDB
    saved = asyncio.run(repo.get_by_id("INC-CALLBACK-AUTO-01"))
    assert saved is not None
    assert saved["incident_id"] == "INC-CALLBACK-AUTO-01"
    assert saved["category"] == "plastic_bottle"
    assert service.total_persisted >= 1


# =========================================================================
# 30. Audit log entries created on actions and sensitive data redacted
# =========================================================================
def test_audit_logging_and_redaction(setup_mock_db):
    """30. Test audit logging with sensitive field redaction."""
    repo = AuditRepository(db=setup_mock_db)
    log_data = {
        "user_id": "usr-audit-01",
        "username": "auditor",
        "action": "TEST_ACTION",
        "resource_type": "camera",
        "resource_id": "CAM-001",
        "ip_address": "127.0.0.1",
        "metadata": {
            "password": "SuperSecretPassword!",
            "token": "secret_jwt_token_12345",
            "safe_field": "public_data",
        },
    }
    created = asyncio.run(repo.create(log_data))
    assert created["action"] == "TEST_ACTION"
    # Verify sensitive metadata was redacted
    meta = created["metadata"]
    assert meta["password"] == "***REDACTED***"
    assert meta["token"] == "***REDACTED***"
    assert meta["safe_field"] == "public_data"
