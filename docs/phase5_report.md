# Phase 5 Completion Report — Object Tracking, Temporal Validation & Incident Engine

## 1. Executive Summary
Phase 5 implements the core intelligence pipeline that transforms raw, frame-level AI detections from Phase 2 (Solid Detection), Phase 3 (Liquid Segmentation), and Phase 4 (Video Ingestion) into validated, high-confidence **Cleanliness Incident Events**.

By combining a ByteTrack-inspired two-stage multi-object tracker, strict temporal persistence verification, area threshold audits, application-level triage severity scoring, duplicate suppression via configurable cooldown windows, and annotated evidence snapshot storage, Phase 5 eliminates false positives caused by transient noise and alert flooding from persistent violations.

---

## 2. Tracking Architecture
Implemented in [`ai/incident/tracker.py`](file:///c:/Users/avars/Downloads/AI%20Based%20Cleanliness%20Monitoring%20System/ai/incident/tracker.py):
- **Algorithm**: ByteTrack-style two-stage IoU association.
  1. *Stage 1*: Associates existing active tracks with high-confidence detections (`conf >= SOLID_MIN_CONFIDENCE`).
  2. *Stage 2*: Associates unmatched tracks with secondary low-confidence detections (`0.20 <= conf < SOLID_MIN_CONFIDENCE`) to preserve identity during motion blur or partial occlusion.
- **Track Lifecycle**:
  - `ACTIVE`: Actively observed in the current frame; increments `consecutive_frames` and `total_frames_seen`.
  - `LOST`: Unmatched in current frame; preserves track state and increments `lost_frames`.
  - `REMOVED`: Exceeded `SOLID_TRACK_GRACE_FRAMES`; evicted from in-memory tracking tables.
- **Track State Attributes**:
  - `track_id` (monotonic unique integer)
  - `class_id` and `class_name`
  - `confidence`
  - `bbox` and centroid `last_position`
  - `first_seen` and `last_seen` timestamps (UTC)
  - `consecutive_frames` and `total_frames_seen`
  - `duration_seconds`

---

## 3. Solid Waste Temporal Validation
Implemented in [`ai/incident/temporal_validator.py`](file:///c:/Users/avars/Downloads/AI%20Based%20Cleanliness%20Monitoring%20System/ai/incident/temporal_validator.py) with `SolidTemporalValidator`:
- A solid waste violation is only confirmed when:
  1. Detection confidence $\ge$ `SOLID_MIN_CONFIDENCE` (default: `0.45`).
  2. Track consecutive frame count reaches `SOLID_MIN_CONSECUTIVE_FRAMES` (default: `5` frames).
- Track loss grace period (`SOLID_TRACK_GRACE_FRAMES = 10`): If an object is momentarily occluded by pedestrians or vehicle movement, the track is held in `LOST` state. If the object reappears within 10 frames, it retains its original track identity, preventing duplicate incident creation.

---

## 4. Liquid Waste Temporal Validation & Area Thresholds
Implemented in [`ai/incident/temporal_validator.py`](file:///c:/Users/avars/Downloads/AI%20Based%20Cleanliness%20Monitoring%20System/ai/incident/temporal_validator.py) with `LiquidTemporalValidator`:
- Liquid waste lacks discrete bounding box trajectories, so tracking is performed per `(category, roi_name)` pair.
- **Area Threshold Audit**:
  - `LIQUID_MIN_AFFECTED_AREA_PIXELS`: default `1200` px.
  - `LIQUID_MIN_AFFECTED_AREA_PERCENT`: default `1.0%`.
  - `LIQUID_AREA_CHECK_MODE`: Configurable modes (`OR`, `AND`, `PIXELS`, `PERCENT`). Default `OR` ensures violations meeting either criteria trigger validation.
- **Persistence Verification**:
  - Requires `consecutive_frames >= LIQUID_MIN_CONSECUTIVE_FRAMES` (default: `4` frames) OR `duration_seconds >= LIQUID_MIN_DURATION_SECONDS` (default: `2.0`s) using wall-clock UTC timestamps.

---

## 5. Incident Severity Strategy
Implemented in [`ai/incident/severity.py`](file:///c:/Users/avars/Downloads/AI%20Based%20Cleanliness%20Monitoring%20System/ai/incident/severity.py) with `SeverityCalculator`:

> [!NOTE]
> These severity classifications are application-level operational triage rules for municipal operators and do NOT represent official statutory standards.

### Solid Waste Rules
- **HIGH**:
  - Category is `garbage_pile` (large accumulated debris / pedestrian obstruction).
  - Cluster count $\ge 3$ tracked objects in the same camera view.
  - Prolonged duration $\ge 60$s with confidence $\ge 0.75$.
- **MEDIUM**:
  - Sanitation / plastic waste (`plastic_bottle`, `plastic_bag`, `can`, `food_waste`) with confidence $\ge 0.60$ or duration $\ge 15$s.
  - Cluster of 2 items.
- **LOW**:
  - Isolated paper litter or small items with duration $< 15$s and confidence $< 0.60$.

### Liquid Waste Rules
- **HIGH**:
  - Biohazard / infrastructure overflow (`sewage_overflow`, `drain_overflow`).
  - Heavy inundation: `affected_area_percent >= 15.0%` or `affected_area_pixels >= 10000`.
  - Persistent overflow: `duration >= 30s` with area $\ge 10.0\%$.
- **MEDIUM**:
  - Moderate spills or waterlogging: area $\ge 5.0\%$, area $\ge 3000$ px, or duration $\ge 10$s.
- **LOW**:
  - Localized puddle or small spill: area $< 5.0\%$ and duration $< 10$s.

---

## 6. Deduplication & Cooldown Strategy
Implemented in [`ai/incident/deduplicator.py`](file:///c:/Users/avars/Downloads/AI%20Based%20Cleanliness%20Monitoring%20System/ai/incident/deduplicator.py) with `IncidentDeduplicator`:
- **Cooldown Window**: `INCIDENT_COOLDOWN_SECONDS` (default: `180` seconds).
- **Deduplication Keys**:
  - Solid: `{camera_id}:SOLID:{category}:{track_id}`
  - Liquid: `{camera_id}:LIQUID:{category}:{roi_name}`
- **Repeated Violation Handling**:
  - During the cooldown window, identical violations are suppressed and recorded in `duplicates_suppressed` telemetry.
  - Once the cooldown expires, if the violation remains present in the camera stream, a new incident can be generated.
  - Expired records are periodically pruned to keep memory bounded.

---

## 7. Evidence Snapshot Generation
Implemented in [`ai/incident/evidence.py`](file:///c:/Users/avars/Downloads/AI%20Based%20Cleanliness%20Monitoring%20System/ai/incident/evidence.py) with `EvidenceManager`:
- **Unique Incident IDs**: `INC-YYYYMMDD-XXXXXX` (e.g. `INC-20260929-000001`). Generated via thread-safe atomic sequence counters.
- **Partitioned File Storage**: `storage/snapshots/YYYY/MM/DD/{incident_id}.jpg`.
- **Annotations**:
  - *Solid Evidence*: Bounding box with severity color coding, item label banner, and top metadata bar with camera ID, timestamp, and severity.
  - *Liquid Evidence*: Alpha-blended polygon overlay (`cv2.fillPoly` + `cv2.addWeighted`), polyline contour, bounding box label, and top metadata bar.
- **Filesystem Safety**: Incident IDs are sanitized against regex `^[A-Za-z0-9_-]+$` to prevent directory traversal attacks.

---

## 8. Incident Schema
Pydantic v2 model [`IncidentCreate`](file:///c:/Users/avars/Downloads/AI%20Based%20Cleanliness%20Monitoring%20System/backend/app/schemas/incident.py):
```json
{
  "incident_id": "INC-20260929-000001",
  "camera_id": "CAM-SOLID-001",
  "waste_type": "SOLID",
  "category": "plastic_bottle",
  "confidence": 0.89,
  "severity": "MEDIUM",
  "snapshot_path": "storage/snapshots/2026/09/29/INC-20260929-000001.jpg",
  "timestamp": "2026-09-29T18:05:52.123456Z",
  "track_id": 1,
  "first_seen": "2026-09-29T18:05:51.123456Z",
  "last_seen": "2026-09-29T18:05:52.123456Z",
  "duration_seconds": 1.0,
  "status": "NEW",
  "metadata": {
    "frame_index": 5,
    "bounding_box": {"x1": 150.0, "y1": 200.0, "x2": 210.0, "y2": 310.0},
    "cluster_count": 1
  }
}
```

---

## 9. Configuration Parameters
Added to [`backend/app/core/config.py`](file:///c:/Users/avars/Downloads/AI%20Based%20Cleanliness%20Monitoring%20System/backend/app/core/config.py):

| Parameter | Type | Default | Description |
| :--- | :---: | :---: | :--- |
| `SOLID_MIN_CONFIDENCE` | float | 0.45 | Minimum confidence for solid detection tracking |
| `SOLID_MIN_CONSECUTIVE_FRAMES` | int | 5 | Consecutive frames required to confirm solid incident |
| `SOLID_TRACK_GRACE_FRAMES` | int | 10 | Max missing frames before closing solid track |
| `SOLID_TRACK_IOU_THRESHOLD` | float | 0.30 | Minimum IoU overlap for ByteTrack association |
| `LIQUID_MIN_CONFIDENCE` | float | 0.40 | Minimum confidence for liquid instance segmentation |
| `LIQUID_MIN_AFFECTED_AREA_PIXELS` | int | 1200 | Minimum pixel footprint required for liquid violation |
| `LIQUID_MIN_AFFECTED_AREA_PERCENT` | float | 1.0 | Minimum percentage of ROI covered |
| `LIQUID_AREA_CHECK_MODE` | str | "OR" | Area condition evaluation: `OR`, `AND`, `PIXELS`, `PERCENT` |
| `LIQUID_MIN_CONSECUTIVE_FRAMES` | int | 4 | Consecutive frames required to confirm liquid incident |
| `LIQUID_MIN_DURATION_SECONDS` | float | 2.0 | Minimum wall-clock persistence duration in seconds |
| `INCIDENT_COOLDOWN_SECONDS` | int | 180 | Deduplication cooldown window in seconds |

---

## 10. Automated Test Results
Run command:
```bash
python -m pytest tests/ -v
```
Results:
- **Phase 1 Tests**: 6 passed
- **Phase 2 Tests**: 8 passed
- **Phase 3 Tests**: 11 passed
- **Phase 4 Tests**: 9 passed
- **Phase 5 Tests**: 20 passed
- **Total**: **54 passed, 0 failed in 9.99s (100% pass rate)**.

---

## 11. End-to-End Live Demonstration Output
Executed [`ai/incident/e2e_incident_demo.py`](file:///c:/Users/avars/Downloads/AI%20Based%20Cleanliness%20Monitoring%20System/ai/incident/e2e_incident_demo.py):
- **Solid Waste**: `plastic_bottle` tracked over 5 frames $\to$ Confirmed $\to$ Incident `INC-20260929-000002` created $\to$ Severity `MEDIUM` $\to$ Snapshot saved.
- **Liquid Waste**: `sewage_overflow` tracked over 4 frames $\to$ Confirmed $\to$ Incident `INC-20260929-000001` created $\to$ Severity `HIGH` $\to$ Snapshot saved.
- **Duplicate Prevention**: Over 28 subsequent frame detections, alerts were suppressed via the active 180s cooldown.

---

## 12. Scope Deferred to Phase 6
The following components are decoupled and intentionally deferred to Phase 6:
- MongoDB / Motor asynchronous persistence.
- FastAPI REST endpoints (`POST /api/v1/incidents/`, `GET /api/v1/incidents/`).
- Operator authentication & JWT security integration.
- Real-time WebSocket incident dispatch to the admin web dashboard.
