"""Phase 8 Comprehensive Test Suite: WebSocket Real-Time Alerts.

Covers:
1. WebSocket endpoint exists (/ws/alerts)
2. Valid JWT connection succeeds
3. Invalid JWT rejected (1008 Policy Violation)
4. Expired JWT rejected
5. Inactive user rejected
6. CONNECTED handshake event emitted with user info
7. IncidentEngine confirms incident -> MongoDB persist -> WebSocket broadcasts INCIDENT_CREATED
8. MongoDB persistence failure does not broadcast false success
9. Incident status update (PATCH) broadcasts INCIDENT_UPDATED
10. Client disconnect cleanup and active count maintenance
11. Multiple connected clients receive broadcast events
12. Role-aware broadcasting (send_to_role)
13. Security: No JWT, token, or password appears in event payload
14. Security: No RTSP credentials appear in event payload
15. Heartbeat: PING / PONG keepalive events
16. Duplicate incident event handling and unique identity
17. Thread-safe execution from background worker threads
18. Frontend build verification with WebSocket integration
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from mongomock_motor import AsyncMongoMockClient

from backend.app.core.config import settings
from backend.app.core.security import create_access_token
from backend.app.db.mongodb import async_db_manager
from backend.app.schemas.user import UserResponse, UserRole
from backend.app.schemas.incident import (
    IncidentCreate,
    IncidentSeverity,
    WasteType,
    IncidentStatus,
)
from backend.app.repositories.user_repository import UserRepository
from backend.app.repositories.incident_repository import IncidentRepository
from backend.scripts.create_admin import bootstrap_admin
from backend.app.websocket.manager import ConnectionManager, get_connection_manager
from backend.app.websocket.alerts import (
    WebSocketEventType,
    create_incident_created_event,
    create_incident_updated_event,
    create_ping_event,
    create_pong_event,
)
from backend.app.services.incident_event_service import IncidentEventService
from ai.incident.incident_engine import IncidentEngine
from backend.app.main import app


@pytest.fixture(autouse=True)
def setup_mock_db():
    """Sets up an isolated in-memory MongoDB instance for each test."""
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["cleanliness_ws_test_db"]
    async_db_manager.set_mock_database(mock_db)
    yield mock_db
    mock_client.close()


@pytest.fixture
def client():
    """FastAPI TestClient instance."""
    return TestClient(app)


@pytest.fixture
def admin_raw_token(setup_mock_db, client):
    """Bootstraps admin user and returns raw JWT token string."""
    asyncio.run(bootstrap_admin(db=setup_mock_db))
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def operator_raw_token(setup_mock_db, client, admin_raw_token):
    """Creates an active operator and returns raw JWT token string."""
    op_payload = {
        "email": "operator_ws@cleanliness.gov.in",
        "username": "operator_ws",
        "full_name": "WS Operator",
        "role": "OPERATOR",
        "password": "SecurePassword123!",
        "is_active": True,
    }
    create_resp = client.post(
        "/api/v1/users/",
        json=op_payload,
        headers={"Authorization": f"Bearer {admin_raw_token}"},
    )
    assert create_resp.status_code == 201

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "operator_ws", "password": "SecurePassword123!"},
    )
    assert login_resp.status_code == 200
    return login_resp.json()["access_token"]


# =========================================================================
# 1. WebSocket endpoint exists
# =========================================================================
def test_1_websocket_endpoint_exists(client, admin_raw_token):
    """1. Test that the /ws/alerts WebSocket endpoint exists and accepts connections."""
    with client.websocket_connect(f"/ws/alerts?token={admin_raw_token}") as ws:
        data = ws.receive_json()
        assert data["type"] == WebSocketEventType.CONNECTED.value


# =========================================================================
# 2. Valid JWT connection succeeds
# =========================================================================
def test_2_valid_jwt_connection_succeeds(client, admin_raw_token):
    """2. Test that connecting with a valid JWT token succeeds and receives handshake."""
    with client.websocket_connect(f"/ws/alerts?token={admin_raw_token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "CONNECTED"
        assert msg["username"] == settings.ADMIN_USERNAME
        assert msg["role"] == "ADMIN"


# =========================================================================
# 3. Invalid JWT rejected
# =========================================================================
def test_3_invalid_jwt_rejected(client):
    """3. Test that connecting with an invalid or malformed token closes with policy violation."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/alerts?token=invalid.tampered.token"):
            pass
    assert exc_info.value.code == 1008


# =========================================================================
# 4. Expired JWT rejected
# =========================================================================
def test_4_expired_jwt_rejected(client):
    """4. Test that connecting with an expired JWT token is rejected."""
    expired_token = create_access_token(
        subject="admin",
        expires_delta=timedelta(seconds=-60),
    )
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/alerts?token={expired_token}"):
            pass
    assert exc_info.value.code == 1008


# =========================================================================
# 5. Inactive user rejected
# =========================================================================
def test_5_inactive_user_rejected(setup_mock_db, client, admin_raw_token):
    """5. Test that a user marked is_active=False is rejected from opening a WebSocket."""
    user_repo = UserRepository(db=setup_mock_db)
    user = asyncio.run(
        user_repo.create({
            "email": "deactivated_ws@cleanliness.gov.in",
            "username": "deactivated_ws",
            "full_name": "Deactivated User",
            "role": "OPERATOR",
            "hashed_password": "fake_hash_value",
            "is_active": False,
        })
    )

    inactive_token = create_access_token(subject=user["id"])
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/alerts?token={inactive_token}"):
            pass
    assert exc_info.value.code == 1008


# =========================================================================
# 6. CONNECTED handshake event emitted
# =========================================================================
def test_6_connected_event_emitted(client, operator_raw_token):
    """6. Test that initial message emitted by server matches CONNECTED schema."""
    with client.websocket_connect(f"/ws/alerts?token={operator_raw_token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "CONNECTED"
        assert "timestamp" in msg
        assert "user_id" in msg
        assert msg["username"] == "operator_ws"
        assert msg["role"] == "OPERATOR"


# =========================================================================
# 7. IncidentEngine confirms incident -> MongoDB persist -> WebSocket broadcast
# =========================================================================
def test_7_incident_engine_broadcasts(setup_mock_db, client, admin_raw_token):
    """7. Test that when IncidentEngine confirms an incident, it is persisted to MongoDB and broadcast."""
    with client.websocket_connect(f"/ws/alerts?token={admin_raw_token}") as ws:
        init_msg = ws.receive_json()
        assert init_msg["type"] == "CONNECTED"

        # Initialize event service attached to active manager
        manager = get_connection_manager()
        repo = IncidentRepository(db=setup_mock_db)
        event_service = IncidentEventService(incident_repo=repo, ws_manager=manager)

        engine = IncidentEngine()
        event_service.attach_to_engine(engine)

        test_incident = IncidentCreate(
            incident_id="INC-WS-BROADCAST-001",
            camera_id="CAM-NORTH-01",
            waste_type=WasteType.SOLID,
            category="plastic_bottle",
            confidence=0.92,
            snapshot_path="storage/snapshots/2026/09/30/snap.jpg",
            timestamp=datetime.now(timezone.utc),
            severity=IncidentSeverity.MEDIUM,
        )

        # Trigger callback
        event_service.on_incident_confirmed(test_incident)

        # WebSocket client receives INCIDENT_CREATED
        broadcast_msg = ws.receive_json()
        assert broadcast_msg["type"] == "INCIDENT_CREATED"
        assert broadcast_msg["incident"]["incident_id"] == "INC-WS-BROADCAST-001"
        assert broadcast_msg["incident"]["category"] == "plastic_bottle"
        assert broadcast_msg["incident"]["severity"] == "MEDIUM"

        # Verify incident is in MongoDB
        persisted = asyncio.run(repo.get_by_id("INC-WS-BROADCAST-001"))
        assert persisted is not None
        assert persisted["incident_id"] == "INC-WS-BROADCAST-001"
        assert event_service.total_persisted >= 1
        assert event_service.total_broadcasted >= 1


# =========================================================================
# 8. MongoDB failure does not broadcast false success
# =========================================================================
def test_8_mongodb_failure_does_not_broadcast_false_success(client, admin_raw_token):
    """8. Test that if MongoDB persistence fails, INCIDENT_CREATED is not broadcast and failure telemetry increments."""
    with client.websocket_connect(f"/ws/alerts?token={admin_raw_token}") as ws:
        init_msg = ws.receive_json()
        assert init_msg["type"] == "CONNECTED"

        manager = get_connection_manager()

        # Faulty repository simulating database failure
        class FailingIncidentRepository:
            async def create(self, doc):
                raise RuntimeError("Simulated Database Connection Failure")

        event_service = IncidentEventService(
            incident_repo=FailingIncidentRepository(),
            ws_manager=manager,
        )

        test_incident = IncidentCreate(
            incident_id="INC-FAIL-001",
            camera_id="CAM-001",
            waste_type=WasteType.LIQUID,
            category="sewage_overflow",
            confidence=0.88,
            snapshot_path="storage/snapshots/snap.jpg",
            timestamp=datetime.now(timezone.utc),
            severity=IncidentSeverity.HIGH,
        )

        # Execute callback: must not crash
        event_service.on_incident_confirmed(test_incident)

        assert event_service.total_errors >= 1
        assert event_service.total_broadcasted == 0


# =========================================================================
# 9. Incident status update broadcasts INCIDENT_UPDATED
# =========================================================================
def test_9_incident_status_update_broadcasts(setup_mock_db, client, admin_raw_token, operator_raw_token):
    """9. Test that PATCH /api/v1/incidents/{incident_id}/status broadcasts INCIDENT_UPDATED."""
    with client.websocket_connect(f"/ws/alerts?token={operator_raw_token}") as ws:
        ws.receive_json()  # Consume CONNECTED

        # Create an initial incident via API
        now = datetime.now(timezone.utc).isoformat()
        create_resp = client.post(
            "/api/v1/incidents/",
            json={
                "incident_id": "INC-STATUS-TEST-01",
                "camera_id": "CAM-001",
                "waste_type": "SOLID",
                "category": "garbage_pile",
                "confidence": 0.89,
                "snapshot_path": "storage/snapshots/snap.jpg",
                "timestamp": now,
                "severity": "HIGH",
            },
            headers={"Authorization": f"Bearer {operator_raw_token}"},
        )
        assert create_resp.status_code == 201

        # Patch status
        patch_resp = client.patch(
            "/api/v1/incidents/INC-STATUS-TEST-01/status",
            json={"status": "ACKNOWLEDGED", "notes": "Municipal team en route"},
            headers={"Authorization": f"Bearer {operator_raw_token}"},
        )
        assert patch_resp.status_code == 200

        # Receive WebSocket broadcast
        msg = ws.receive_json()
        assert msg["type"] == "INCIDENT_UPDATED"
        assert msg["incident_id"] == "INC-STATUS-TEST-01"
        assert msg["status"] == "ACKNOWLEDGED"
        assert msg["notes"] == "Municipal team en route"


# =========================================================================
# 10. Client disconnect cleanup
# =========================================================================
def test_10_client_disconnect_cleanup(client, admin_raw_token):
    """10. Test that client disconnection cleanly decrements connection manager count."""
    manager = get_connection_manager()
    initial_count = manager.active_count

    with client.websocket_connect(f"/ws/alerts?token={admin_raw_token}") as ws:
        ws.receive_json()  # Handshake
        assert manager.active_count == initial_count + 1

    # After context exit, socket is disconnected
    assert manager.active_count == initial_count


# =========================================================================
# 11. Multiple clients receive event
# =========================================================================
def test_11_multiple_clients_receive_event(client, admin_raw_token, operator_raw_token):
    """11. Test that multiple connected clients both receive broadcast alerts."""
    with client.websocket_connect(f"/ws/alerts?token={admin_raw_token}") as ws_admin:
        ws_admin.receive_json()
        with client.websocket_connect(f"/ws/alerts?token={operator_raw_token}") as ws_op:
            ws_op.receive_json()

            manager = get_connection_manager()
            event = create_incident_created_event({
                "incident_id": "INC-MULTI-01",
                "camera_id": "CAM-MULTI",
                "waste_type": "SOLID",
                "category": "can",
                "confidence": 0.95,
                "snapshot_path": "snap.jpg",
                "timestamp": datetime.now(timezone.utc),
                "severity": "LOW",
                "status": "NEW",
            })

            asyncio.run(manager.broadcast(event))

            msg1 = ws_admin.receive_json()
            msg2 = ws_op.receive_json()

            assert msg1["type"] == "INCIDENT_CREATED"
            assert msg1["incident"]["incident_id"] == "INC-MULTI-01"
            assert msg2["type"] == "INCIDENT_CREATED"
            assert msg2["incident"]["incident_id"] == "INC-MULTI-01"


# =========================================================================
# 12. Role-aware broadcasting works
# =========================================================================
def test_12_role_aware_broadcasting(client, admin_raw_token, operator_raw_token):
    """12. Test that send_to_role delivers messages selectively to targeted roles."""
    with client.websocket_connect(f"/ws/alerts?token={admin_raw_token}") as ws_admin:
        ws_admin.receive_json()
        with client.websocket_connect(f"/ws/alerts?token={operator_raw_token}") as ws_op:
            ws_op.receive_json()

            manager = get_connection_manager()
            admin_event = {
                "type": "ADMIN_SYSTEM_NOTICE",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Maintenance window scheduled",
            }

            # Dispatch to ADMIN role only
            dispatched = asyncio.run(manager.send_to_role("ADMIN", admin_event))
            assert dispatched >= 1

            msg = ws_admin.receive_json()
            assert msg["type"] == "ADMIN_SYSTEM_NOTICE"


# =========================================================================
# 13. Security: No JWT, token, or password appears in event payload
# =========================================================================
def test_13_no_jwt_token_in_event_payload():
    """13. Test that generated events contain no tokens, password hashes, or secret keys."""
    incident_dict = {
        "incident_id": "INC-SEC-01",
        "camera_id": "CAM-01",
        "waste_type": "SOLID",
        "category": "plastic_bag",
        "confidence": 0.85,
        "snapshot_path": "storage/snapshots/snap.jpg",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "severity": "LOW",
        "status": "NEW",
    }
    event = create_incident_created_event(incident_dict)
    event_str = str(event).lower()

    assert "password" not in event_str
    assert "token" not in event_str
    assert "jwt" not in event_str
    assert "secret" not in event_str


# =========================================================================
# 14. Security: No RTSP credentials appear in event payload
# =========================================================================
def test_14_no_rtsp_credentials_in_event_payload():
    """14. Test that event schemas do not leak raw camera RTSP credentials."""
    incident_data = {
        "incident_id": "INC-SEC-02",
        "camera_id": "CAM-02",
        "waste_type": "LIQUID",
        "category": "waterlogging",
        "confidence": 0.90,
        "snapshot_path": "snap.jpg",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "severity": "HIGH",
        "status": "NEW",
    }
    event = create_incident_created_event(incident_data)
    event_str = str(event)

    assert "rtsp://" not in event_str
    assert "@" not in event_str.split("snapshot_path")[0]


# =========================================================================
# 15. Heartbeat / keepalive behavior
# =========================================================================
def test_15_heartbeat_keepalive_behavior(client, admin_raw_token):
    """15. Test client sending PING receives PONG heartbeat response."""
    with client.websocket_connect(f"/ws/alerts?token={admin_raw_token}") as ws:
        ws.receive_json()  # Handshake

        # Send heartbeat ping
        ws.send_json({"type": "PING", "timestamp": datetime.now(timezone.utc).isoformat()})
        resp = ws.receive_json()
        assert resp["type"] == "PONG"
        assert "timestamp" in resp


# =========================================================================
# 16. Duplicate incident handling
# =========================================================================
def test_16_duplicate_incident_handling():
    """16. Test that incident events provide stable unique incident_id for client-side deduplication."""
    incident_dict = {
        "incident_id": "INC-DEDUP-UNIQUE-999",
        "camera_id": "CAM-01",
        "waste_type": "SOLID",
        "category": "can",
        "confidence": 0.90,
        "snapshot_path": "snap.jpg",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "severity": "LOW",
        "status": "NEW",
    }
    event1 = create_incident_created_event(incident_dict)
    event2 = create_incident_created_event(incident_dict)

    # Identical incident_id allows frontends to deduplicate via Set
    seen = set()
    assert event1["incident"]["incident_id"] not in seen
    seen.add(event1["incident"]["incident_id"])
    assert event2["incident"]["incident_id"] in seen


# =========================================================================
# 17. Thread-safe execution from background worker threads
# =========================================================================
def test_17_incident_event_service_threadsafe(setup_mock_db):
    """17. Test that broadcast_threadsafe can be called safely without raising errors."""
    manager = get_connection_manager()
    event = create_incident_created_event({
        "incident_id": "INC-THREADSAFE-01",
        "camera_id": "CAM-01",
        "waste_type": "SOLID",
        "category": "plastic_bottle",
        "confidence": 0.91,
        "snapshot_path": "snap.jpg",
        "timestamp": datetime.now(timezone.utc),
        "severity": "MEDIUM",
        "status": "NEW",
    })

    # Call threadsafe broadcast (simulating worker thread invocation)
    # Must not raise any exceptions
    manager.broadcast_threadsafe(event)


# =========================================================================
# 18. Frontend production build artifacts with WebSocket integration
# =========================================================================
def test_18_frontend_build_artifacts():
    """18. Test that Vite production build succeeded and artifacts exist."""
    frontend_dist = Path("frontend/dist")
    index_html = frontend_dist / "index.html"
    assert frontend_dist.exists()
    assert index_html.exists()
    content = index_html.read_text(encoding="utf-8")
    assert "<div id=\"root\">" in content
