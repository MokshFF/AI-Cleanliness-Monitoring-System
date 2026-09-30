# Phase 8 Report: WebSocket Real-Time Alerts

## 1. Executive Summary
Phase 8 delivers full-duplex **Real-Time Surveillance Alerting** for the **AI-Based National Cleanliness Monitoring System**, establishing an instantaneous event distribution bridge from the computer vision incident engine to authenticated municipal dashboard operators.

Through a centralized FastAPI WebSocket endpoint (`GET /ws/alerts`), validated against the project's existing JWT infrastructure, the system immediately pushes confirmed solid and liquid waste incidents as well as lifecycle status updates directly to connected browser clients without requiring dashboard page refreshes.

All **122 automated tests** across Phases 1 through 8 pass with 100% reliability, the standalone end-to-end demonstration script completes with 100% success, and the frontend production bundle compiles with zero TypeScript errors.

---

## 2. Architecture & Data Flow

```
[ Real CCTV / RTSP Camera Stream ]
                │
                ▼
      [ AI Detection Pipelines ]
  (Solid YOLOv8/11 + Liquid YOLOv8/11-Seg)
                │
                ▼
  [ Tracking & Temporal Validation ]
  (ByteTrack Association & Temporal Filter)
                │
                ▼
      [ Phase 5 IncidentEngine ]
                │
                ▼ on_incident(callback)
     [ IncidentEventService ] ──▶ Persistence & Dispatch Coordinator
                │
                ├──▶ 1. Persist to MongoDB (`IncidentRepository.create`)
                │       │
                │       ▼ (If and only if persistence succeeds)
                └──▶ 2. Transmit to WebSocket Manager
                            │
                            ▼ (Thread-Safe Event Loop Dispatch)
            [ ConnectionManager (`backend/app/websocket/manager.py`) ]
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
    [ Connected Operator 1 ]        [ Connected Admin 2 ]
    - Browser WebSocket Client      - Browser WebSocket Client
    - Handshake: CONNECTED          - Handshake: CONNECTED
    - Events: INCIDENT_CREATED      - Events: INCIDENT_CREATED
              INCIDENT_UPDATED                INCIDENT_UPDATED
              PING / PONG                     PING / PONG
            │                               │
            ▼                               ▼
    [ React Admin Dashboard ]       [ React Admin Dashboard ]
    - Floating Alert Toast          - Floating Alert Toast
    - Web Audio Alert Chime         - Web Audio Alert Chime
    - Live KPI Metric Increments    - Live KPI Metric Increments
    - Instant Table Prepending      - Instant Table Prepending
```

---

## 3. WebSocket Endpoint & Authentication

### 3.1 Endpoint Specification
- **Path**: `GET /ws/alerts?token=<JWT>` (and aliased at `/api/v1/ws/alerts`)
- **Transport**: Standard WebSocket (`ws://` / `wss://`)
- **Protocol Handshake**: Evaluates query parameter `token` using `backend/app/websocket/auth.py`.

### 3.2 Security Tradeoff Documentation
The browser's native JavaScript `new WebSocket(url)` constructor does not support sending custom HTTP headers (such as `Authorization: Bearer <token>`). Query parameter tokens are therefore the standard cross-browser solution for WebSocket handshakes.
To eliminate potential token exposure risks:
1. **Server Log Redaction**: Raw query strings and tokens are stripped from server access and application logs.
2. **Strict Expiry & State Checks**: Tokens are verified using HS256 signature, expiry timestamp, user active status (`is_active == True`), and allowed municipal roles (`ADMIN`, `OPERATOR`, `SUPERVISOR`).
3. **Payload Sanitization**: The token is never echoed back in WebSocket event payloads.
4. **Transport Layer Encryption**: In production, TLS/WSS encrypts the full URL path and query string during transit.

---

## 4. Connection Manager & Thread Safety

### 4.1 Centralized Connection Manager (`backend/app/websocket/manager.py`)
Maintains an in-memory mapping of active WebSocket connections to authenticated `UserResponse` profiles:
- `connect(websocket, user)`: Accepts socket and transmits initial `CONNECTED` handshake event.
- `disconnect(websocket)`: Cleans up connection and decrements active telemetry.
- `broadcast(event)`: Iterates active connections and dispatches JSON payload, automatically purging stale or broken sockets.
- `send_to_user(user_id, event)`: Dispatches events targeted to a specific user.
- `send_to_role(role, event)`: Dispatches events targeted to specific municipal roles (e.g. `ADMIN` notices).

### 4.2 Thread-Safe Background Worker Dispatch
Phase 4 camera ingestion workers and Phase 5 `IncidentEngine` callbacks execute inside background OS threads, whereas FastAPI WebSockets run on the asynchronous event loop:
- `broadcast_threadsafe(event, loop)` resolves the primary event loop and submits the broadcast coroutine via `asyncio.run_coroutine_threadsafe()`.
- Broadcast execution is strictly non-blocking; network or client socket delays never stall the video processing pipeline.

### 4.3 Heartbeat & Keepalive Protocol
- Background heartbeat loop runs every 30 seconds (`WEBSOCKET_HEARTBEAT_SECONDS=30`), emitting `{"type": "PING", "timestamp": "..."}`.
- Clients respond with `{"type": "PONG", "timestamp": "..."}`.
- Silent or disconnected sockets are cleanly pruned without resource leaks.

---

## 5. Event Schemas & Persistence Ordering

### 5.1 Persistence-First Broadcasting Policy
In compliance with strict data integrity requirements:
```text
IncidentEngine confirms incident
        ↓
Persist incident to MongoDB
        ↓
If persistence succeeds
        ↓
Broadcast INCIDENT_CREATED WebSocket event
```
If MongoDB persistence fails:
- Database failure is logged with details.
- Error telemetry (`total_errors`) is incremented.
- `INCIDENT_CREATED` event is **not broadcasted** to dashboard clients.
- Video processing continues without crashing camera workers.

### 5.2 Event Types & Schemas

#### 1. Handshake Event (`CONNECTED`)
```json
{
  "type": "CONNECTED",
  "timestamp": "2026-09-30T06:01:30.275530+00:00",
  "user_id": "84f68e1e-8694-4ec7-8a43-2963af12b7d4",
  "username": "admin",
  "role": "ADMIN"
}
```

#### 2. Confirmed Incident Event (`INCIDENT_CREATED`)
```json
{
  "type": "INCIDENT_CREATED",
  "timestamp": "2026-09-30T06:01:30.283100+00:00",
  "incident": {
    "incident_id": "INC-20260930060130-DEMO",
    "camera_id": "CAM-SOUTH-GATE",
    "waste_type": "SOLID",
    "category": "plastic_bottle",
    "confidence": 0.94,
    "severity": "MEDIUM",
    "status": "NEW",
    "snapshot_path": "storage/snapshots/2026/09/30/INC-20260930060130-DEMO.jpg",
    "timestamp": "2026-09-30T06:01:30.280000+00:00",
    "bounding_box": [120.0, 240.0, 300.0, 480.0]
  }
}
```

#### 3. Status Lifecycle Update Event (`INCIDENT_UPDATED`)
Triggered when an incident status transitions via `PATCH /api/v1/incidents/{incident_id}/status`:
```json
{
  "type": "INCIDENT_UPDATED",
  "timestamp": "2026-09-30T06:01:30.303028+00:00",
  "incident_id": "INC-20260930060130-DEMO",
  "status": "ACKNOWLEDGED",
  "notes": "Dispatched sanitation squad to South Gate.",
  "updated_at": "2026-09-30T06:01:30.301000",
  "updated_by": "admin"
}
```

---

## 6. Frontend WebSocket Architecture

### 6.1 WebSocket Provider & Hook (`frontend/src/websocket/WebSocketProvider.tsx`)
- Centralized context provider mounted in `main.tsx` wrapping the application.
- Exposes `connectionStatus`, `activeAlerts`, `dismissAlert`, `audioEnabled`, `toggleAudio`, and subscription listeners.
- **Exponential Reconnection Backoff**: Reconnects on unexpected disconnect with intervals: 1s, 2s, 4s, 8s, 16s, max 30s. Automatically resets backoff on connection success.
- **Authentication Safety**: Stops reconnection attempts if closed with code 1008 (policy violation/expired token) or upon user logout.
- **Client Duplicate Protection**: Maintains a bounded in-memory set (max 200 items) of recent `incident_id`s, suppressing duplicate alert toasts and sounds.

### 6.2 Visual Alert Toast (`frontend/src/components/alerts/IncidentAlertToast.tsx`)
- Floating notification container mounted in `AppLayout.tsx`.
- Displays camera ID, location, waste category, classification badge, confidence % or affected area %, and severity indicator.
- Includes a direct `[View Incident]` action navigating to `/incidents/{id}` and an auto-dismiss timer (8 seconds).

### 6.3 Synthesized Audio Chime
- Uses HTML5 Web Audio API to synthesize a non-intrusive dual-tone surveillance chime (D5 587Hz -> A5 880Hz) without external audio asset dependencies.
- Handles browser autoplay restrictions gracefully without impacting visual alert delivery.
- User-controllable audio toggle button in the application header, persisted in `localStorage`.

### 6.4 Real-Time Dashboard & Table Updates
- **Executive Dashboard (`src/pages/Dashboard.tsx`)**:
  - Increments active incident counters, today's count, and severity distributions dynamically.
  - Prepends newly detected incidents to the recent activity feed.
  - Updates incident status in-place upon `INCIDENT_UPDATED`.
  - Displays real-time connection status pill (`● LIVE`, `● RECONNECTING`, `● OFFLINE`).
- **Incident Table (`src/pages/Incidents.tsx`)**:
  - Inserts new incidents at the top if compatible with active filter criteria.
  - Displays a dynamic alert banner (`"{N} new incidents detected. Click to update table view"`) if filters or pagination differ.
  - Updates table rows in-place upon status changes.

---

## 7. Production Security Refinements
- **Removed Hard-Coded Credentials**: Replaced bootstrap password hints in `Login.tsx` with an authorized access surveillance notice.
- **Payload Data Scrubbing**: Verified that event payloads do not contain sensitive tokens, user password hashes, or RTSP camera credentials.

---

## 8. Verification & Testing Results

### 8.1 Automated Unit & Integration Tests (`tests/test_phase8.py`)
18 automated tests validating the full WebSocket lifecycle:
1. `test_1_websocket_endpoint_exists`: Endpoint accepts WebSocket connections.
2. `test_2_valid_jwt_connection_succeeds`: Valid JWT connects and receives handshake.
3. `test_3_invalid_jwt_rejected`: Invalid token closes with 1008 Policy Violation.
4. `test_4_expired_jwt_rejected`: Expired token rejected.
5. `test_5_inactive_user_rejected`: Inactive user rejected.
6. `test_6_connected_event_emitted`: Handshake event matches schema.
7. `test_7_incident_engine_broadcasts`: Confirmed incident persists to DB and broadcasts `INCIDENT_CREATED`.
8. `test_8_mongodb_failure_does_not_broadcast_false_success`: DB error suppresses broadcast and logs error.
9. `test_9_incident_status_update_broadcasts`: PATCH status broadcasts `INCIDENT_UPDATED`.
10. `test_10_client_disconnect_cleanup`: Client disconnect decrements active count.
11. `test_11_multiple_clients_receive_event`: Multi-client fan-out verified.
12. `test_12_role_aware_broadcasting`: Role-targeted broadcasting verified.
13. `test_13_no_jwt_token_in_event_payload`: Payload contains no tokens or secrets.
14. `test_14_no_rtsp_credentials_in_event_payload`: Camera RTSP passwords sanitized.
15. `test_15_heartbeat_keepalive_behavior`: PING/PONG keepalive cycle verified.
16. `test_16_duplicate_incident_handling`: Client deduplication verified.
17. `test_17_incident_event_service_threadsafe`: Threadsafe dispatch executes without blocking.
18. `test_18_frontend_build_artifacts`: Production bundle compiles cleanly.

### 8.2 Comprehensive Test Suite Results
```bash
python -m pytest tests/ -v
```
```text
================= 122 passed, 1 warning in 132.42s (0:02:12) ==================
```
- **Phase 1**: 4 tests passed
- **Phase 2**: 10 tests passed
- **Phase 3**: 11 tests passed
- **Phase 4**: 9 tests passed
- **Phase 5**: 20 tests passed
- **Phase 6**: 30 tests passed
- **Phase 7**: 20 tests passed
- **Phase 8**: 18 tests passed
- **Total**: 122/122 passed (100% pass rate).

### 8.3 End-to-End Demonstration Script
```bash
python backend/scripts/e2e_phase8_demo.py
```
```text
================================================================================
PHASE 8 END-TO-END DEMONSTRATION PASSED WITH 100% SUCCESS!
================================================================================
```
All 13 demonstration steps executed and verified cleanly.

---

## 9. Limitations & Scope Boundaries
In adherence to project boundary rules:
- Live browser CCTV streaming (WebRTC, HLS, RTSP-to-browser proxy) is deferred to future video streaming phases.
- GIS map visualization and longitudinal trend reports remain placeholder views scheduled for Phase 9.
- Email, SMS, Telegram, and WhatsApp alert bridges are omitted; the authenticated admin dashboard is the sole primary alert destination.
