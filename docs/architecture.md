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

## 7. Multi-Camera Scalability & Concurrency
- **Stream Ingestion**: Lightweight worker threads drain camera RTSP streams into bounded ring buffers (`FRAME_BUFFER_MAXSIZE = 30`).
- **Dynamic Modes**: Per-camera detection mode: `SOLID`, `LIQUID`, or `BOTH`.
- **RTSP Isolation**: Raw RTSP credentials never reach web clients.
