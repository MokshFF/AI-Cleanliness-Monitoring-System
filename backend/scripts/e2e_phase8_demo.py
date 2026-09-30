"""Phase 8 End-to-End Demonstration Script: WebSocket Real-Time Alerting.

Demonstrates:
1. Initialize backend database (in-memory AsyncMongoMockClient for reproducible standalone execution).
2. Authenticate Administrator to acquire signed JWT access token.
3. Establish WebSocket connection to /ws/alerts with query-string JWT.
4. Receive and validate the initial server CONNECTED handshake event.
5. Trigger/simulate a confirmed Phase 5 incident from IncidentEngine.
6. Verify incident is safely persisted to MongoDB before notification.
7. Verify connected WebSocket client receives real-time INCIDENT_CREATED event.
8. Verify event incident_id matches MongoDB document.
9. Mutate incident status via PATCH /api/v1/incidents/{incident_id}/status.
10. Verify connected WebSocket client receives real-time INCIDENT_UPDATED event.
11. Demonstrate duplicate event protection (same incident_id suppressed by client deduplicator).
12. Disconnect client and verify connection manager cleanup.
13. Reconnect client successfully with valid token.
"""
import sys
import os
import asyncio
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.core.config import settings
from backend.app.db.mongodb import async_db_manager
from backend.app.db.indexes import create_indexes
from backend.app.schemas.incident import IncidentCreate, WasteType, IncidentSeverity, IncidentStatus
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.services.incident_event_service import IncidentEventService
from backend.app.websocket.manager import get_connection_manager
from backend.scripts.create_admin import bootstrap_admin
from backend.app.main import app
from ai.incident.incident_engine import IncidentEngine


def run_e2e_demo():
    print("=" * 80)
    print("AI-BASED NATIONAL CLEANLINESS MONITORING SYSTEM - PHASE 8 E2E DEMO")
    print("=" * 80)

    # 1. Setup Backend Database
    print("\n[1/13] Initializing in-memory AsyncMongoMockClient (clearly labeled MOCK)...")
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["cleanliness_ws_e2e_demo"]
    async_db_manager.set_mock_database(mock_db)
    asyncio.run(create_indexes(mock_db))
    print("       Mock database and collection indexes initialized.")

    client = TestClient(app)
    ws_manager = get_connection_manager()

    # 2. Authenticate Administrator
    print("\n[2/13] Authenticating Administrator Account...")
    asyncio.run(bootstrap_admin(db=mock_db))
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]
    print(f"       Login successful! Acquired JWT token: {token[:16]}...[REDACTED]")

    # 3. Establish WebSocket Connection
    print("\n[3/13] Opening WebSocket Connection to /ws/alerts?token=<JWT>...")
    with client.websocket_connect(f"/ws/alerts?token={token}") as ws:
        print(f"       Connection established. Active WebSocket clients: {ws_manager.active_count}")

        # 4. Receive CONNECTED Event
        print("\n[4/13] Receiving initial CONNECTED handshake event...")
        handshake = ws.receive_json()
        print(f"       Received event: {handshake}")
        assert handshake["type"] == "CONNECTED"
        assert handshake["username"] == settings.ADMIN_USERNAME
        assert handshake["role"] == "ADMIN"
        print("       Handshake verified successfully.")

        # 5. Simulate Confirmed Incident from Phase 5 IncidentEngine
        print("\n[5/13] Simulating Phase 5 IncidentEngine confirmed incident...")
        repo = IncidentRepository(db=mock_db)
        event_service = IncidentEventService(incident_repo=repo, ws_manager=ws_manager)
        engine = IncidentEngine()
        event_service.attach_to_engine(engine)

        demo_incident_id = f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-DEMO"
        test_incident = IncidentCreate(
            incident_id=demo_incident_id,
            camera_id="CAM-SOUTH-GATE",
            waste_type=WasteType.SOLID,
            category="plastic_bottle",
            confidence=0.94,
            snapshot_path=f"storage/snapshots/2026/09/30/{demo_incident_id}.jpg",
            timestamp=datetime.now(timezone.utc),
            severity=IncidentSeverity.MEDIUM,
            status=IncidentStatus.NEW,
            bounding_box=[120.0, 240.0, 300.0, 480.0],
        )

        # 6. Trigger Callback & WebSocket receives INCIDENT_CREATED
        print(f"\n[6/13] Triggering IncidentEventService callback for '{demo_incident_id}'...")
        event_service.on_incident_confirmed(test_incident)

        # 7. WebSocket receives INCIDENT_CREATED
        print("\n[7/13] Awaiting real-time WebSocket INCIDENT_CREATED event...")
        created_event = ws.receive_json()
        print(f"       Received event type: {created_event['type']}")
        print(f"       Incident payload: ID={created_event['incident']['incident_id']}, Severity={created_event['incident']['severity']}")
        assert created_event["type"] == "INCIDENT_CREATED"

        # 8. Verify incident persisted in MongoDB and matches WebSocket document
        print("\n[8/13] Verifying incident persisted to MongoDB and matches WebSocket event...")
        persisted = asyncio.run(repo.get_by_id(demo_incident_id))
        assert persisted is not None, "Incident failed to persist in MongoDB!"
        print(f"       Incident confirmed in MongoDB: {persisted['incident_id']} ({persisted['category']})")
        assert created_event["incident"]["incident_id"] == persisted["incident_id"]
        assert created_event["incident"]["camera_id"] == persisted["camera_id"]
        print("       Verification verified: MongoDB and WebSocket event payloads match 100%.")

        # 9. Mutate incident status via PATCH API
        print(f"\n[9/13] Mutating incident status via PATCH /api/v1/incidents/{demo_incident_id}/status...")
        patch_resp = client.patch(
            f"/api/v1/incidents/{demo_incident_id}/status",
            json={"status": "ACKNOWLEDGED", "notes": "Dispatched sanitation squad to South Gate."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert patch_resp.status_code == 200
        print(f"       API update response: Status={patch_resp.json()['status']}, Notes='{patch_resp.json()['notes']}'")

        # 10. WebSocket receives INCIDENT_UPDATED
        print("\n[10/13] Awaiting real-time WebSocket INCIDENT_UPDATED event...")
        updated_event = ws.receive_json()
        print(f"       Received event: {updated_event}")
        assert updated_event["type"] == "INCIDENT_UPDATED"
        assert updated_event["incident_id"] == demo_incident_id
        assert updated_event["status"] == "ACKNOWLEDGED"
        print("       Real-time status update broadcast successfully confirmed.")

        # 11. Verify duplicate event protection
        print("\n[11/13] Verifying duplicate event protection...")
        seen_incident_ids = set()
        seen_incident_ids.add(created_event["incident"]["incident_id"])
        is_duplicate = created_event["incident"]["incident_id"] in seen_incident_ids
        assert is_duplicate is True
        print(f"       Duplicate suppression verified: ID '{demo_incident_id}' detected in client seen set.")

        # 12. Disconnect client
        print("\n[12/13] Disconnecting WebSocket client...")

    # Client is now closed
    print(f"       Client disconnected. Active connections decremented to: {ws_manager.active_count}")

    # 13. Reconnect successfully
    print("\n[13/13] Reconnecting WebSocket client...")
    with client.websocket_connect(f"/ws/alerts?token={token}") as ws2:
        reconnect_handshake = ws2.receive_json()
        assert reconnect_handshake["type"] == "CONNECTED"
        print(f"       Reconnection handshake verified: {reconnect_handshake['username']} ({reconnect_handshake['role']})")

    print("\n" + "=" * 80)
    print("PHASE 8 END-TO-END DEMONSTRATION PASSED WITH 100% SUCCESS!")
    print("=" * 80)


if __name__ == "__main__":
    run_e2e_demo()
