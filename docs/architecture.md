# AI-Based National Cleanliness Monitoring System - System Architecture

## 1. Executive Overview
The **AI-Based National Cleanliness Monitoring System** is an automated surveillance and violation management platform. It ingests live video streams from IP/CCTV cameras across public and municipal locations, performs dual-stream AI detection for **Solid Waste** (litter, piles) and **Liquid Waste** (spills, overflows, waterlogging), validates persistence using temporal filtering, and creates actionable incidents dispatched in real-time to an authenticated web dashboard.

---

## 2. High-Level Data Flow

```
[ CCTV / IP Cameras (RTSP) ]
              │
              ▼
   [ video/stream_manager.py ]  ──▶ Auto-reconnect & Threaded Buffer
              │
              ▼
  [ Frame Sampling (1 of N) ]   ──▶ CPU/GPU Compute Optimizer
              │
       ┌──────┴──────────────────────────┐
       ▼                                 ▼
[ Solid Waste Detection ]     [ Liquid Waste Segmentation ]
  - YOLOv8/v11 Object Detect    - YOLOv8/v11 Instance Seg
  - 6 Initial Solid Classes     - 4 Initial Liquid Classes
  - Bounding Box & Conf         - Area & Mask Polygon
       │                                 │
       ▼                                 ▼
[ ByteTrack Object Tracker ]   [ Area & Temporal Persistence ]
  - Trajectory Confirmation     - Multi-frame Blob IoU / Area
       │                                 │
       └──────────────┬──────────────────┘
                      │
                      ▼
          [ Incident Engine ]
            - Temporal Filter (K consecutive frames)
            - Cooldown / Deduplication
            - Snapshot Evidence Generation
                      │
                      ▼
        [ FastAPI Backend Service ]
            - Pydantic Ingestion Validation
            - PyMongo / MongoDB Persistence
                      │
                      ▼
         [ WebSocket Broadcaster ]
                      │
                      ▼
       [ React Admin Web Dashboard ]
  (Live Audio/Visual Alert, Map Pin, Table Update)
```

---

## 3. Waste Class Taxonomies

### Solid Waste Classes (Object Detection)
1. `plastic_bottle` (Class 0)
2. `plastic_bag` (Class 1)
3. `paper` (Class 2)
4. `can` (Class 3)
5. `food_waste` (Class 4)
6. `garbage_pile` (Class 5)

### Liquid Waste Classes (Polygon Segmentation)
1. `liquid_spill` (Class 0)
2. `sewage_overflow` (Class 1)
3. `waterlogging` (Class 2)
4. `drain_overflow` (Class 3)

---

## 4. Solid Waste Computer Vision Pipeline (Phase 2)
```
[ Raw / Annotated Images ]
          │
          ▼
[ ai/datasets/validator.py ] ──▶ Integrity & coordinate bounds audit
          │
          ▼
[ ai/datasets/splitter.py ]  ──▶ 70% Train, 20% Val, 10% Test (SHA-256 deduplicated)
          │
          ▼
[ ai/configs/solid_dataset.yaml ]
          │
          ▼
[ ai/training/train_solid.py ] ──▶ CCTV Augmentations (hsv, scale, mosaic, perspective)
          │
          ├──▶ models/solid/best.pt & ai/models/weights/solid_waste_yolo.pt
          └──▶ models/solid/metadata.json
          │
          ▼
[ ai/training/evaluate_solid.py ] ──▶ mAP@0.50, mAP@0.50:0.95, Precision, Recall, F1
          │
          ▼
[ ai/inference/solid_detector.py ] ──▶ Single Image, Image Batch, Local Video
                                        Output: SolidFrameDetectionResult
```

---

## 5. Liquid Waste Segmentation Pipeline (Phase 3)
```
[ Raw / Annotated Images ]
          │
          ▼
[ ai/datasets/liquid_validator.py ] ──▶ Polygon vertex & coordinate bounds audit
          │
          ▼
[ ai/datasets/splitter.py ]  ──▶ 70% Train, 20% Val, 10% Test (SHA-256 deduplicated)
          │
          ▼
[ ai/configs/liquid_dataset.yaml ]
          │
          ▼
[ ai/training/train_liquid.py ] ──▶ CCTV Augmentations (hsv reflection, perspective, scale)
          │
          ├──▶ models/liquid/best.pt & ai/models/weights/liquid_waste_yolo_seg.pt
          └──▶ models/liquid/metadata.json
          │
          ▼
[ ai/training/evaluate_liquid.py ] ──▶ Mask/Box mAP@0.50, mAP@0.50:0.95, Precision, Recall
          │
          ▼
[ ai/inference/liquid_segmenter.py ] ──▶ Affected Area & ROI Calculation
                                         Output: LiquidFrameDetectionResult
```

### Affected-Area Calculation & Monitored Region of Interest (ROI)
Liquid hazard severity is determined by the percentage of a designated monitored zone covered:
$$\text{affected\_area\_percent} = \frac{\text{affected\_liquid\_pixels}}{\text{monitored\_region\_pixels}} \times 100$$
The system supports configurable ROIs (bounding boxes or arbitrary polygons). The binary mask of the segmented liquid is bitwise-ANDed with the ROI mask to compute only the relevant violation footprint.

---

## 6. CCTV-Specific Data Augmentation Strategy
- **Solid Waste**: HSV lighting variations, moderate rotation (10.0°), scaling (0.50), no vertical flips (`flipud: 0.0`), pedestrian occlusion erasing.
- **Liquid Waste**: Specular reflection & water saturation variations, oblique perspective (0.0008), curb/shadow occlusion, no vertical flips (`flipud: 0.0`).

---

## 7. Multi-Camera Video Ingestion & Stream Management (Phase 4)

```
[ Camera Sources ] ──▶ [ StreamCapture Thread ] ──▶ [ BoundedFrameBuffer ] ──▶ [ Processing Thread ] ──▶ [ AIRouter ]
 (RTSP, File, Webcam)     - Auto-reconnect              - Maxsize: 30              - Target FPS Sampling   - SOLID / LIQUID / BOTH
                           - Exponential backoff         - Oldest frame drop        - Timezone timestamps  - Evidence frame preserved
```

### 7.1 Architecture & Concurrency Isolation
- **CameraWorker Isolation**: Each camera runs an isolated worker consisting of two coordinated threads:
  1. `StreamCapture` thread: continuously drains frames from the network/device directly into memory to prevent network socket backpressure.
  2. Consumer/Processing thread: samples frames at the camera's configured `target_fps` (e.g., 3-5 FPS from 25-30 FPS stream) and routes to AI models.
- **Bounded Frame Buffer**: Fixed capacity (default 30 frames). When full, the oldest unconsumed frame is dropped, ensuring real-time latency is preserved and memory footprint is strictly bounded.
- **Auto-Reconnect & Backoff**: Automatically detects frame decode failures and socket loss, triggering exponential backoff reconnection without blocking or crashing other camera workers.
- **Credential Protection**: Redacts passwords from RTSP URLs (e.g. `rtsp://user:***@host:port/path`) in logs, telemetry, and error reports.
- **AI Routing**: The `AIRouter` dispatches frames according to camera capability:
  - `SOLID` ➔ `SolidWasteDetector` (YOLO detection)
  - `LIQUID` ➔ `LiquidWasteSegmenter` (YOLO polygon segmentation & ROI analysis)
  - `BOTH` ➔ Both models concurrently, merged into unified `CameraFrameAIResult`.
- **Evidence Frame Preservation**: Every `CameraFrameAIResult` bundles the raw NumPy frame, ready for Phase 5 object tracking and snapshot evidence storage.

---

## 8. Object Tracking, Temporal Persistence & Incident Engine (Phase 5)

```
[ CameraFrameAIResult ]
           │
           ├──────────────────────────────┬──────────────────────────────┐
           ▼                                                             ▼
 [ Solid Waste Pipeline ]                                      [ Liquid Waste Pipeline ]
   - ByteTrack 2-stage IoU Matching                              - Multi-frame Area Aggregator
   - State: ACTIVE, LOST, REMOVED                                - Area threshold: pixels / percent
   - Grace period: 10 frames                                     - Temporal persistence: 4 frames / 2.0s
   - Min persistence: 5 frames                                   - ROI zone isolation
           │                                                             │
           └──────────────────────────────┬──────────────────────────────┘
                                          │
                                          ▼
                             [ Severity Calculator ]
                               - Application-level triage
                               - LOW / MEDIUM / HIGH
                                          │
                                          ▼
                            [ Incident Deduplicator ]
                               - Cooldown: 180 seconds
                               - Keys: camera:waste_type:category:track_id/roi
                                          │
                                          ▼
                            [ Evidence Snapshot Mgr ]
                               - Partitioned storage: YYYY/MM/DD/INC-...jpg
                               - Visual annotations (boxes, masks, banners)
                                          │
                                          ▼
                             [ Cleanliness Incident ]
                               - Emitted via on_incident(callback)
```

### 8.1 Tracking & Persistence Strategy
- **Solid Waste**:
  - ByteTrack two-stage IoU matching links bounding boxes across frames.
  - Temporary track loss (e.g. pedestrian or vehicle occlusion) is tolerated for up to `SOLID_TRACK_GRACE_FRAMES` (10 frames) without re-identifying as a new object.
  - An incident is only triggered once an object persists for `SOLID_MIN_CONSECUTIVE_FRAMES` (5 frames).
- **Liquid Waste**:
  - Validates affected area against `LIQUID_MIN_AFFECTED_AREA_PIXELS` and `LIQUID_MIN_AFFECTED_AREA_PERCENT`.
  - Confirms accumulation when seen across `LIQUID_MIN_CONSECUTIVE_FRAMES` (4 frames) or persisting over `LIQUID_MIN_DURATION_SECONDS` (2.0s).
- **Deduplication Cooldown**:
  - Once confirmed, an incident enters a 180s cooldown window to suppress repeat alerts. Repeated violations after cooldown expiration generate distinct subsequent incidents.
- **Evidence Snapshots**:
  - Saved into date-partitioned storage (`storage/snapshots/YYYY/MM/DD/INC-...jpg`) with high-resolution bounding boxes, polygonal overlays, confidence tags, and metadata banners.

---

## 9. MongoDB Persistence, FastAPI REST API & Authentication (Phase 6)

```
[ IncidentEngine.on_incident(...) ]
                │
                ▼
[ IncidentPersistenceService ] ──▶ Resilient Async Persistence Task
                │
                ▼
      [ MongoDB Database ]
       ├── users (Indexed: username, email)
       ├── cameras (Indexed: camera_id, is_active)
       ├── incidents (Indexed: incident_id, camera_id, timestamp, status, severity)
       └── audit_logs (Indexed: timestamp, user_id, action)
                │
                ▲
                │ (CRUD + Aggregation + Auditing)
                │
     [ FastAPI REST API (v1) ]
       ├── /api/v1/auth: POST /login, GET /me (JWT Bearer Token)
       ├── /api/v1/users: Admin-only CRUD + RBAC
       ├── /api/v1/cameras: Stream Registry, Credential Masking
       └── /api/v1/incidents: Paginated Search, Multi-Filter, Status Updates
```

### 9.1 Database Persistence Architecture
- **Motor Asynchronous Driver**: Non-blocking async I/O using `motor.motor_asyncio.AsyncIOMotorClient` with connection pooling (`minPoolSize=5`, `maxPoolSize=50`).
- **Resilient Engine Bridge**: `IncidentPersistenceService` attaches directly to Phase 5 `IncidentEngine.on_incident` callbacks. Persists incidents to MongoDB across thread/async boundaries without ever stalling camera worker threads on network or database failures.
- **Indexes**: Idempotent startup index creation covering primary keys, search attributes, temporal orderings (`timestamp: -1`), and composite filter combinations (`camera_id + timestamp`, `status + timestamp`, `severity + timestamp`).

### 9.2 Security & RBAC Enforcement
- **Password Security**: Passwords hashed using `bcrypt` with unique salts. Password hashes are strictly omitted from schema serialization (`UserResponse`).
- **JWT Authentication**: HS256 signed access tokens with configurable expiration (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`).
- **Role-Based Access Control (RBAC)**:
  - `ADMIN`: Full access to user management, camera registration/modification/deletion, incident lifecycle management, and audit logs.
  - `OPERATOR`: Access to camera inspection, incident querying, and status progression (`NEW` ➔ `ACKNOWLEDGED` ➔ `RESOLVED` / `DISMISSED`). Restricted from user administration and camera modification.
- **RTSP Credential Protection**: Passwords in RTSP URLs are automatically masked across all API responses (`rtsp://user:***@host:port/path`) using schema-level validators and repository sanitation.
- **Audit Logging**: All sensitive mutations (user creation, camera modification, incident acknowledgement) record user, timestamp, client IP, action, and redacted metadata in `audit_logs`.

---

## 10. React Admin Web Dashboard (Phase 7)

```
[ Operator / Supervisor / Administrator Browser ]
                     │
                     ▼
         [ Vite SPA React Client ]
  ┌────────────────────────────────────────────────────────┐
  │  React Router v6                                       │
  │    ├── /login (Unauthenticated)                        │
  │    └── ProtectedRoute (Auth & RBAC Guards)             │
  │          ├── AppLayout (Sidebar, Header, Profile)       │
  │          ├── /dashboard (KPIs, Charts, Recent Feed)     │
  │          ├── /incidents (Search, Filters, Pagination)   │
  │          ├── /incidents/:id (Telemetry, Snapshot Modal) │
  │          ├── /cameras (Stream Health & Registration)    │
  │          ├── /cameras/:id (Settings, Masked RTSP URI)   │
  │          ├── /users (Admin-Only Personnel Management)   │
  │          └── /settings (Diagnostic Taxonomies & Specs)  │
  └──────────────────────────┬─────────────────────────────┘
                             │
                             ▼
     [ Axios API Client (`src/api/client.ts`) ]
       ├── Request Interceptor: Injects Authorization Bearer Token
       └── Response Interceptor: 401 Redirects & Error Extraction
                             │
                             ▼ (Reverse Proxy / Direct REST)
      [ FastAPI Backend Endpoints (`/api/v1/*`) ]
                             │
             ┌───────────────┴───────────────┐
             ▼                               ▼
     [ MongoDB Database ]          [ Snapshot Storage ]
  (Users, Cameras, Incidents)     (`GET /incidents/{id}/snapshot`)
```

### 10.1 Frontend Architecture & Component Hierarchy
- **Single Page Application (SPA)**: Built with React 18, TypeScript, Vite 5, and Tailwind CSS.
- **State Management**:
  - `AuthContext`: Centralized authentication store managing current `user`, JWT `token`, local storage persistence, login/logout workflows, and role helpers (`isAdmin`, `isSupervisor`, `isOperator`).
  - Page-level local state with clean optimistic and error-safe patterns.
- **Secure Visual Evidence Streaming**:
  - Browser image tags cannot natively attach `Authorization: Bearer <token>` headers without security risks.
  - Implemented `incidentApi.fetchSnapshotBlob()` which queries `GET /api/v1/incidents/{incident_id}/snapshot` with JWT authentication and renders an in-memory `URL.createObjectURL(blob)`, safely revoked upon component unmount.
- **Safety & Credential Protection**:
  - RTSP credentials remain masked across all table views and camera detail views (`rtsp://***:***@...`).
  - Role-based route guards (`ProtectedRoute`) prevent unauthorized access (e.g. operators navigating to `/users` are bounced to `/dashboard`).
- **Telemetry & Visualization**:
  - Recharts powering dynamic incident distribution by severity and waste taxonomy breakdown.
  - Live filter engine supporting composite filtering (camera, status, severity, waste type, date range) with client-side debounce and server-side pagination.

---

## 11. WebSocket Real-Time Alerting Architecture (Phase 8)

```
[ Phase 5 IncidentEngine ]
            │
            ▼ on_incident(callback)
[ IncidentEventService ] ──▶ Coordinates Atomic Persistence & Notification
            │
            ├──▶ 1. Persist to MongoDB (`IncidentRepository.create`)
            │       │
            │       ▼ (If and only if persistence succeeds)
            └──▶ 2. Dispatch to WebSocket Manager
                        │
                        ▼ (Threadsafe Event Loop Dispatch)
            [ ConnectionManager (`backend/app/websocket/manager.py`) ]
                        │
       ┌────────────────┴────────────────┬────────────────┐
       ▼                                 ▼                ▼
[ Browser Client 1 ]              [ Browser Client 2 ]  [ Dead Client ]
  - JWT Query Auth: /ws/alerts      - JWT Query Auth      - Auto-pruned
  - Handshake: CONNECTED            - Handshake: CONNECTED
  - Events: INCIDENT_CREATED        - Events: INCIDENT_CREATED
            INCIDENT_UPDATED                  INCIDENT_UPDATED
            PING / PONG (Heartbeat)           PING / PONG
       │                                 │
       ▼                                 ▼
[ React Admin Dashboard ]        [ React Admin Dashboard ]
  - Visual Alert Toast Banner       - Visual Alert Toast Banner
  - Non-Intrusive Audio Chime       - Non-Intrusive Audio Chime
  - Real-Time KPI Counter Increment - Real-Time KPI Counter Increment
  - Live Table Prepending           - Live Table Prepending
```

### 11.1 Persistence-First Broadcasting Policy
The system guarantees that an alert is never broadcasted to dashboard clients unless the underlying incident has been durably committed to MongoDB:
1. `IncidentEngine` confirms an incident through tracking and temporal validation.
2. `IncidentEventService` attempts MongoDB write.
3. If persistence fails: logs failure, increments error counters, suppresses WebSocket broadcast, and protects the CCTV capture thread from crashing.
4. If persistence succeeds: dispatches `INCIDENT_CREATED` event to `ConnectionManager`.

### 11.2 Thread-Safe Background Worker Dispatch
Camera capture workers and the `IncidentEngine` operate in background OS threads. FastAPI WebSockets run on the asynchronous event loop. `ConnectionManager.broadcast_threadsafe()` safely submits coroutines to the primary event loop using `asyncio.run_coroutine_threadsafe()`, guaranteeing non-blocking operation for camera pipelines.

### 11.3 Security & Lifecycle Management
- **Query Parameter JWT Handshake**: Uses standard browser WebSocket query string (`/ws/alerts?token=<JWT>`), validating user existence, active status, and RBAC permissions. Query tokens are stripped from server logs and excluded from all event payloads.
- **Heartbeat & Dead Connection Cleanup**: Periodic 30-second ping/pong cycle cleans up dead client sockets without resource leakage.
- **Client Exponential Backoff**: Frontend client reconnects automatically upon transient network failures (1s, 2s, 4s, 8s, 16s, max 30s) and resets upon connection success. Halts reconnection on HTTP 401/1008 policy violation.
- **Client Deduplication**: Bounded in-memory event set (max 200 items) filters duplicate events by `incident_id` preventing alert and audio spam.

---

## 12. GIS Map, Longitudinal Analytics & Municipal Reporting Architecture (Phase 9)

```
[ MongoDB Incident & Camera Fleet Records ]
                    │
      ┌─────────────┼─────────────┐
      ▼             ▼             ▼
[ GIS Map API ] [ Analytics API ] [ Reporting API ]
- /map/cameras   - /analytics/    - /reports/incidents.csv
- /map/incidents    summary       - /reports/incidents.pdf
      │             │             │
      │             │             ├─▶ [ Audit Log ] (GENERATE_CSV/PDF_REPORT)
      │             │             └─▶ [ ReportLab Engine / RFC 4180 CSV ]
      ▼             ▼             ▼
[ Leaflet Map ] [ Recharts Hub ] [ Browser Direct Download ]
- Custom SVG    - Trend Area     - Formatted CSV spreadsheet
  Markers         Chart          - Styled Municipal PDF Document
- Popups with   - Severity Donut
  Links         - Category Bars
- Filter Bar    - Zone Breakdown
```

### 12.1 Geospatial Surveillance Map
- **Projection Schemas**: `CameraMapItem` and `IncidentMapItem` project surveillance nodes and confirmed incidents into coordinates. Plaintext RTSP URLs, passwords, and tokens are omitted.
- **Strict Coordinate Validation**: Cameras with `(0.0, 0.0)` or null coordinates are excluded from GIS rendering to prevent coordinate fabrication.
- **Interactive UI**: OpenStreetMap/Leaflet integration via `react-leaflet` with custom status-colored camera icons and severity-pulsing incident pins.

### 12.2 Longitudinal Aggregation Engine
- **MongoDB Aggregation Pipelines**: `AnalyticsService` executes server-side `$match`, `$group`, `$sort`, and `$dateToString` pipelines to aggregate total incidents, active counts, resolution rate, category counts, camera hotspots, and zone compliance without loading bulk collections into RAM.
- **Multi-Field Filtering**: Supports date-windowing, camera selection, waste type (`SOLID` / `LIQUID`), category, severity, and lifecycle status.
- **Date Boundary Validation**: Rejects invalid date intervals (`start_date > end_date`) with HTTP 400.

### 12.3 Municipal CSV & PDF Reporting
- **RFC-4180 CSV Export**: Streams structured, quoted tabular data with incident IDs, timestamps, camera identifiers, waste types, confidence scores, duration, and affected area percentages.
- **Official Styled PDF Reports**: ReportLab integration generates structured municipal compliance audit documents containing executive summary tables, categorical distributions, top camera fleet nodes, and detailed incident logs.
- **Audit Logging**: Every report download triggers a non-repudiable audit log record (`GENERATE_CSV_REPORT`, `GENERATE_PDF_REPORT`) logging user ID, username, timestamp, and query filters.

