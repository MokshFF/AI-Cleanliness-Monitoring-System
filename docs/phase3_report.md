# Phase 3 Completion Report — Liquid Waste Dataset & YOLO Segmentation Pipeline

## 1. Executive Summary
Phase 3 establishes the computer-vision pipeline for **Liquid Waste Instance Segmentation and Affected-Area Analysis**. The pipeline processes irregular liquid regions (spills, sewage, waterlogging, drain overflows) as polygonal masks, audits polygon coordinate topologies, splits data deterministically with SHA-256 deduplication, executes CPU/GPU YOLOv8/v11 segmentation training with CCTV-style lighting/perspective augmentations, evaluates standard COCO segmentation metrics (Mask/Box Precision, Recall, mAP@0.50, mAP@0.50:0.95), and computes exact affected-area metrics (pixels and percentage) relative to configurable Monitored Regions of Interest (ROI).

---

## 2. Liquid Waste Classes (Central Taxonomy)
Sourced directly from `ai/configs/liquid_classes.yaml`:
- **Class 0**: `liquid_spill` (oily/chemical spills, hazardous industrial leakage)
- **Class 1**: `sewage_overflow` (dark sludge, blackwater discharge)
- **Class 2**: `waterlogging` (puddles, ponding, localized rainwater inundation)
- **Class 3**: `drain_overflow` (blocked sewer channels, stormwater channel surging)

---

## 3. Dataset Architecture & Organization
```
datasets/
└── liquid/
    ├── raw/                         # Raw CCTV captures
    ├── images/
    │   ├── train/                   # 70% Training images
    │   ├── val/                     # 20% Validation images
    │   └── test/                    # 10% Testing images
    ├── labels/
    │   ├── train/                   # Training YOLO segmentation annotations
    │   ├── val/                     # Validation YOLO segmentation annotations
    │   └── test/                    # Testing YOLO segmentation annotations
    ├── metadata/                    # Split manifests & hash audit
    └── dataset.yaml                 # YOLO dataset configuration
```

---

## 4. Segmentation Annotation Format
YOLO normalized polygon format in matching `.txt` files:
```
<class_id> <x1> <y1> <x2> <y2> <x3> <y3> ... <xn> <yn>
```
*Enforced validation rules:*
- `class_id` in range `[0..3]`.
- Minimum 3 vertices (at least 6 coordinates, total tokens >= 7).
- Token count must be odd: `1 + 2*N`.
- All float coordinates normalized within `[0.0, 1.0]`.
- Non-degenerate polygon area calculated via the Shoelace formula (`area > 0`).

---

## 5. Dataset Validation Utility
Run validator CLI:
```bash
python ai/datasets/liquid_validator.py
```
*Audits:*
- Missing image-label pairs.
- Malformed polygon lines and vertex counts.
- Degenerate/zero-area polygons.
- Coordinate range violations.
- Empty annotation files.
- Duplicate images via SHA-256 digests.
- Corrupted image bytes.
- When unpopulated, reports: `[NO (Dataset has not been supplied yet)]`.

---

## 6. Training Pipeline
### A. Smoke-Test (Lightweight Verification)
```bash
python -m ai.training.train_liquid --data datasets/liquid/dataset.yaml --smoke-test --epochs 1 --batch 2 --imgsz 160 --device cpu
```
### B. Full Model Training (Production / GPU)
```bash
python -m ai.training.train_liquid --model yolov8s-seg.pt --epochs 60 --batch 16 --imgsz 640 --device auto
```

---

## 7. Model Evaluation
```bash
python -m ai.training.evaluate_liquid --model models/liquid/best.pt --data datasets/liquid/dataset.yaml --split val
```
Generates:
- `models/liquid/evaluation/eval/evaluation_report.json` with Mask Precision, Recall, F1, mAP@0.50, and mAP@0.50:0.95.
- Box Precision, Recall, and mAP metrics.
- Per-class metric breakdown for all 4 liquid categories.
- Confusion matrix and PR curves.

---

## 8. Affected-Area Calculation & Configurable ROI
Liquid severity is determined by the percentage of a monitored zone contaminated:
$$\text{affected\_area\_percent} = \frac{\text{affected\_liquid\_pixels}}{\text{monitored\_region\_pixels}} \times 100$$

### Monitored Region of Interest (ROI) Concept
CCTV cameras often monitor broad areas (e.g. roads, walkways, drainage grates). The system allows defining an ROI (bounding box or polygon) representing the actual vulnerable drainage or pedestrian zone. If liquid pools outside the monitored zone, it does not trigger false alerts.

```python
from ai.inference.schemas import RegionOfInterest, BoundingBox

# Define specific monitored drainage zone
drain_roi = RegionOfInterest(
    name="main_drain_grate",
    bbox=BoundingBox(x1=100, y1=150, x2=500, y2=450)
)
```

---

## 9. Structured Inference Output
```json
{
  "frame_index": 15,
  "timestamp": "2026-09-29T17:36:24.052956Z",
  "image_width": 640,
  "image_height": 480,
  "monitored_region_name": "drain_zone_1",
  "monitored_region_pixels": 122500,
  "total_affected_liquid_pixels": 22450,
  "total_affected_area_percent": 18.326,
  "detections": [
    {
      "class_id": 2,
      "class_name": "waterlogging",
      "confidence": 0.8842,
      "bbox": {
        "x1": 120.0,
        "y1": 160.0,
        "x2": 380.0,
        "y2": 420.0
      },
      "affected_area_pixels": 22450,
      "affected_area_percent": 18.326,
      "monitored_region_pixels": 122500,
      "polygon": [[120.0, 160.0], [380.0, 165.0], [375.0, 420.0], [125.0, 415.0]]
    }
  ],
  "processing_time_ms": 14.8
}
```

---

## 10. Temporal Readiness for Phase 5
Each segmentation output packages frame index, timestamp, confidence, class, exact pixel count, and area percentage. Phase 5 uses this structured stream to evaluate:
- Is $\text{affected\_area\_pixels} \ge \text{LIQUID\_MIN\_AFFECTED\_AREA\_PIXELS}$ (default 1200 px)?
- Has the condition persisted for $\ge K$ consecutive processed frames?
- Has the incident cooldown expired?

---

## 11. Known Limitations
- Model weights were trained on 1-epoch synthetic smoke data for pipeline verification; production weights require training on real-world municipal waterlogging/drainage datasets.
- Liquid reflection artifacts under heavy rain can trigger single-frame noise; Phase 5 temporal persistence resolves this.

---

## 12. Scope Deferred to Later Phases
- **Phase 4**: RTSP stream manager, frame ring buffers, and video ingestion pipeline.
- **Phase 5**: Solid tracking (ByteTrack) + liquid temporal persistence & incident deduplication engine.
- **Phase 6+**: REST APIs, MongoDB CRUD, WebSockets, and React Dashboard.
