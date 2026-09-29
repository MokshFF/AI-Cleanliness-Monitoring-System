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

### Structured Inference Output Schema
Inference emits typed JSON adhering to `ai.inference.schemas.SolidFrameDetectionResult`:
```json
{
  "frame_index": 12,
  "timestamp": "2026-09-29T12:12:04.879220Z",
  "image_width": 1280,
  "image_height": 720,
  "detections": [
    {
      "class_id": 0,
      "class_name": "plastic_bottle",
      "confidence": 0.8924,
      "bbox": {
        "x1": 340.5,
        "y1": 512.0,
        "x2": 412.0,
        "y2": 628.5
      },
      "normalized_bbox": {
        "x1": 0.2660,
        "y1": 0.7111,
        "x2": 0.3218,
        "y2": 0.8729
      }
    }
  ],
  "processing_time_ms": 14.82
}
```

---

## 5. CCTV-Specific Data Augmentation Strategy
To mirror actual surveillance conditions without destroying the semantic meaning of litter classes:
- **Color & Lighting Variation**: HSV hue (0.015), saturation (0.7), and value/brightness (0.4) simulate direct noon sun, twilight, rain, and nighttime sodium/LED lighting.
- **Perspective & Spatial Jitter**: Subtle rotation (10.0 deg) and translation (0.10) capture pole oscillation and diagonal viewing angles.
- **Scale Jitter (0.50)**: Objects appear small in the far-field (20m away) and larger near the camera.
- **No Inversion**: Vertical flip is disabled (`flipud: 0.0`) because litter rests gravitationally on horizontal surfaces.
- **Occlusion Resistance**: Random erasing and mixup (0.10) model partial occlusions by walking pedestrians.

---

## 6. Multi-Camera Scalability & Concurrency
- **Stream Ingestion**: Lightweight worker threads drain camera RTSP streams into bounded ring buffers (`FRAME_BUFFER_MAXSIZE = 30`).
- **Dynamic Modes**: Per-camera detection mode: `SOLID`, `LIQUID`, or `BOTH`.
- **RTSP Isolation**: Raw RTSP credentials never reach web clients.
