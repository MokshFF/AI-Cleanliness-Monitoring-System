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
