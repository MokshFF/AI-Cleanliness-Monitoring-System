# Phase 6 Report: MongoDB Persistence + FastAPI Backend + Authentication

## 1. Executive Summary
Phase 6 delivers the production-style database persistence, asynchronous repositories, FastAPI REST API, and role-based authentication layer for the **AI-Based National Cleanliness Monitoring System**. 

Building directly on Phase 5's tracking and incident detection engine, Phase 6 provides durable MongoDB storage for confirmed solid and liquid waste incidents, an authenticated management API with granular RBAC, camera stream configuration with strict credential masking, and non-repudiation audit logging.

All **84 automated tests** across Phases 1 through 6 pass with 100% reliability.

---

## 2. Architecture & Data Flow

```
+-------------------------------------------------------------+
|                     Phase 5 Incident Engine                 |
|  - ByteTrack tracking                                       |
|  - Temporal persistence (solid consecutive, liquid area)    |
|  - Severity scoring & 180s deduplication cooldown          |
|  - Annotated snapshot generation                            |
+------------------------------+------------------------------+
                               |
                   on_incident(callback)
                               |
                               v
+-------------------------------------------------------------+
|             IncidentPersistenceService                      |
|  - Thread-safe / async event loop dispatching               |
|  - Non-blocking execution (resilient failure isolation)     |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|               MongoDB Async Persistence (Motor)             |
|  - users        (indexed: username, email)                  |
|  - cameras      (indexed: camera_id, is_active)             |
|  - incidents    (indexed: incident_id, camera_id, time, etc)|
|  - audit_logs   (indexed: timestamp, user_id, action)       |
+------------------------------+------------------------------+
                               ^
                               |
+-------------------------------------------------------------+
|                    FastAPI REST API (v1)                    |
|  - /api/v1/auth       (POST /login, GET /me)                |
|  - /api/v1/users      (Admin-only CRUD, RBAC)               |
|  - /api/v1/cameras    (Admin/Operator CRUD, Cred Masking)   |
|  - /api/v1/incidents  (Paginated Filter, Status Lifecycle)  |
+-------------------------------------------------------------+
```

---

## 3. MongoDB Persistence Layer

### 3.1 Motor Asynchronous Connection Pool
- Managed via `backend/app/db/mongodb.py` (`AsyncDatabaseManager`).
- Configured with connection pooling (`minPoolSize=5`, `maxPoolSize=50`, `serverSelectionTimeoutMS=2000`).
- Provides clean isolation with mock database injection (`set_mock_database`) enabling instant unit testing without external daemon dependencies.
- Health check `ping()` exposed via `/health`.

### 3.2 Collection Indexes (`backend/app/db/indexes.py`)
Idempotent index creation executed on application lifespan startup:
- **`users`**:
  - `username` (unique, sparse)
  - `email` (unique)
- **`cameras`**:
  - `camera_id` (unique)
  - `is_active`
- **`incidents`**:
  - `incident_id` (unique)
  - `camera_id`
  - `timestamp` (descending)
  - `status`, `severity`, `waste_type`, `category`
  - Compound indexes: `(camera_id, timestamp)`, `(status, timestamp)`, `(severity, timestamp)`
- **`audit_logs`**:
  - `timestamp` (descending)
  - `user_id`, `action`

### 3.3 Repositories (`backend/app/repositories/`)
- **`UserRepository`**: Handles user creation, lookup by ID/username/email, profile updates, and last-login tracking.
- **`CameraRepository`**: Handles camera registration, configuration updates, active status toggling, and decommissioning.
- **`IncidentRepository`**: Handles persistence of incident records, single incident lookup, status transitions (`NEW`, `ACKNOWLEDGED`, `RESOLVED`, `DISMISSED`), resolution timestamp recording, and paginated multi-field filtering.
- **`AuditRepository`**: Records security and operational audit records with automatic sanitization of sensitive metadata.

---

## 4. Security, Authentication & RBAC

### 4.1 Password Security
- Passwords are encrypted using standard `bcrypt` with unique salts (`backend/app/core/security.py`).
- Inputs exceeding 72 bytes are safely truncated to conform to bcrypt boundaries without throwing.
- Plaintext passwords and `password_hash` fields are strictly excluded from API response schemas (`UserResponse`).

### 4.2 JWT Token Issuance & Verification
- Generates signed JWT tokens with claims (`sub`, `username`, `email`, `role`, `iat`, `exp`).
- Default token expiration configured via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default: 60 minutes).
- FastAPI dependency `get_current_user` validates Bearer authorization headers and extracts authenticated user identities.

### 4.3 Role-Based Access Control (RBAC)
- **`ADMIN`**:
  - Full user management (`POST /api/v1/users`, `GET /api/v1/users`, `PATCH /api/v1/users/{id}`).
  - Full camera stream management (`POST /api/v1/cameras`, `PATCH /api/v1/cameras/{id}`, `DELETE /api/v1/cameras/{id}`).
  - Full incident triage and audit trail visibility.
- **`OPERATOR`**:
  - Inspection of registered cameras (`GET /api/v1/cameras`, `GET /api/v1/cameras/{id}`).
  - Incident querying, filtering, and status updates (`GET /api/v1/incidents`, `PATCH /api/v1/incidents/{id}/status`).
  - Restricted from user administration (returns `HTTP 403 Forbidden`).
  - Restricted from camera creation/deletion (returns `HTTP 403 Forbidden`).

### 4.4 Credential Protection & Redaction
- **RTSP URLs**: Passwords embedded in RTSP URLs (e.g. `rtsp://user:password@host:port/stream`) are automatically redacted to `rtsp://user:***@host:port/stream` in `CameraResponse`.
- **Audit Logs**: Metadata keys containing sensitive keys (`password`, `token`, `secret`, `hash`) are automatically sanitized to `***REDACTED***`.

---

## 5. REST API Endpoints Summary

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Public | Authenticates credentials and returns JWT access token |
| `GET` | `/api/v1/auth/me` | Authenticated | Returns authenticated user profile |
| `POST` | `/api/v1/users/` | Admin | Registers a new Operator or Admin user |
| `GET` | `/api/v1/users/` | Admin | Lists registered users with pagination |
| `GET` | `/api/v1/users/{id}` | Admin | Retrieves specific user by ID |
| `PATCH` | `/api/v1/users/{id}` | Admin | Updates user name, email, status, or resets password |
| `POST` | `/api/v1/cameras/` | Admin | Registers a new CCTV camera stream |
| `GET` | `/api/v1/cameras/` | Operator / Admin | Lists cameras (credentials masked) |
| `GET` | `/api/v1/cameras/{id}` | Operator / Admin | Retrieves camera details (credentials masked) |
| `PATCH` | `/api/v1/cameras/{id}` | Admin | Updates camera parameters or active state |
| `DELETE` | `/api/v1/cameras/{id}` | Admin | Decommissions a camera stream |
| `POST` | `/api/v1/incidents/` | Operator / Admin | Ingests a cleanliness violation incident |
| `GET` | `/api/v1/incidents/` | Operator / Admin | Lists incidents with multi-field filtering & pagination |
| `GET` | `/api/v1/incidents/{id}` | Operator / Admin | Retrieves specific incident by ID |
| `PATCH` | `/api/v1/incidents/{id}/status` | Operator / Admin | Transitions incident status and creates audit log |
| `GET` | `/health` | Public | System and database health status |
| `GET` | `/api/v1/status` | Public | AI engine capability status |

---

## 6. Incident Engine Callback Bridge

The `IncidentPersistenceService` (`backend/app/services/incident_persistence.py`) bridges Phase 5's AI pipeline to MongoDB:
- Attaches to `IncidentEngine.on_incident(callback)`.
- When an incident is confirmed by temporal validation and deduplication, the service receives the `IncidentCreate` model.
- Dispatches asynchronous persistence using the event loop, or thread-safely via `asyncio.run_coroutine_threadsafe`.
- **Fault Tolerance**: Any database failure is logged and isolated, preventing worker thread interruptions or video frame drops.

---

## 7. Verification & Test Suite

### 7.1 Automated Pytest Results
All 84 automated tests pass cleanly across all 6 phases:
- **Phase 1 (Setup & Base Schemas)**: 6/6 passed
- **Phase 2 (Solid Detection)**: 8/8 passed
- **Phase 3 (Liquid Segmentation)**: 11/11 passed
- **Phase 4 (CCTV Ingestion & Routing)**: 9/9 passed
- **Phase 5 (Tracking & Incident Engine)**: 20/20 passed
- **Phase 6 (MongoDB Persistence & API)**: 30/30 passed
- **Total**: **84/84 tests passed** (100% pass rate)

### 7.2 Demonstration Scripts
1. **Admin Bootstrap (`backend/scripts/create_admin.py`)**:
   - Idempotently creates administrator account based on configuration settings.
2. **E2E Demonstration (`backend/scripts/e2e_phase6_demo.py`)**:
   - Verifies bootstrap, JWT login, operator registration, camera stream registration with credential masking, IncidentEngine callback persistence, REST API incident querying, status update with notes, and audit log generation.

---

## 8. Transition to Phase 7

With Phase 6 complete and verified:
- MongoDB collections and indexes are active.
- REST APIs are ready to serve dashboard data.
- Camera streams and incident lifecycles are fully queryable and mutable.
- Ready to proceed to **Phase 7: React Admin Web Dashboard**.
