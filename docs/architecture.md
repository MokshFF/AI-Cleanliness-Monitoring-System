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
1. `plastic_bottle`
2. `plastic_bag`
3. `paper`
4. `can`
5. `food_waste`
6. `garbage_pile`

### Liquid Waste Classes (Polygon Segmentation)
1. `liquid_spill`
2. `sewage_overflow`
3. `waterlogging`
4. `drain_overflow`

---

## 4. Multi-Camera Scalability & Concurrency
- **Stream Ingestion**: Each registered camera stream is assigned a lightweight reading thread that drains RTSP frames into a ring buffer (`FRAME_BUFFER_MAXSIZE = 30`). Slow downstream processing drops stale frames rather than buffering lag.
- **Dynamic Modes**: Each camera record has a `detection_mode` enum:
  - `SOLID`: Runs only solid waste detection.
  - `LIQUID`: Runs only liquid waste segmentation.
  - `BOTH`: Runs dual-pipeline inference on sampled frames.
- **RTSP Security**: Raw camera RTSP URLs (which may include camera auth tokens or credentials) are strictly kept on the backend/AI worker and are **never** exposed to client browser applications.

---

## 5. False Positive Elimination Strategy
1. **Confidence Thresholding**: Detections below calibrated confidence cutoffs (default `0.45` solid, `0.40` liquid) are discarded immediately.
2. **Temporal Persistence**:
   - Solid waste candidates must be tracked with stable spatial overlap for at least `N` consecutive sampled frames before qualifying as an incident.
   - Liquid spills must maintain minimal affected area (`> 1200` px) across `M` consecutive frames to prevent brief lighting changes or transient reflections from triggering alerts.
3. **Incident Cooldown**: When an incident is confirmed for a specific camera and zone, duplicate alerts for the same continuous event are suppressed for `INCIDENT_DEDUPLICATION_COOLDOWN_SECONDS` (default 180s).
