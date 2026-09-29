# Phase 2 Completion Report — Solid Waste Dataset & YOLO Detection Pipeline

## 1. Executive Summary
Phase 2 establishes the end-to-end computer-vision pipeline for **Solid Waste Detection**. The pipeline accepts YOLO-formatted dataset directories, validates coordinate integrity and image health, splits data without leakage using SHA-256 deduplication, executes CPU/GPU-adaptive YOLOv8/v11 training with CCTV-style augmentations, evaluates standard COCO metrics (Precision, Recall, F1, mAP@0.50, mAP@0.50:0.95), and exposes structured inference on single images, directories, and local video files.

---

## 2. Dataset Architecture & Organization
The solid waste dataset is organized under `datasets/solid/`:
```
datasets/
└── solid/
    ├── raw/                         # Raw images prior to labeling
    ├── images/
    │   ├── train/                   # 70% Training images
    │   ├── val/                     # 20% Validation images
    │   └── test/                    # 10% Testing images
    ├── labels/
    │   ├── train/                   # Training YOLO txt annotations
    │   ├── val/                     # Validation YOLO txt annotations
    │   └── test/                    # Testing YOLO txt annotations
    ├── metadata/
    │   └── split_manifest.json      # Audit trail & hash-group mapping
    └── dataset.yaml                 # YOLO dataset configuration
```

---

## 3. Class Definitions (Central Taxonomy)
All components consume class IDs strictly from `ai/configs/solid_classes.yaml`:
- **Class 0**: `plastic_bottle`
- **Class 1**: `plastic_bag`
- **Class 2**: `paper`
- **Class 3**: `can`
- **Class 4**: `food_waste`
- **Class 5**: `garbage_pile`

---

## 4. Annotation Format
Standard normalized YOLO bounding box format in `.txt` files with matching stem:
```
<class_id> <x_center> <y_center> <width> <height>
```
*Constraints enforced by validator:*
- Exactly 5 tokens per line.
- `class_id` in range `[0..5]`.
- All float coordinates bounded within `[0.0, 1.0]`.
- Non-zero, positive width and height.

---

## 5. Dataset Validation Utility
Run validator CLI:
```bash
python ai/datasets/validator.py
```
*Validates:*
- Missing image-label pairs.
- Malformed annotation lines.
- Coordinate range violations.
- Empty annotation files.
- Duplicate images via SHA-256 digests.
- Corrupted image bytes.
- When no dataset exists, outputs: `[NO (Dataset has not been supplied yet)]`.

---

## 6. Dataset Splitting Utility
```python
from ai.datasets.splitter import DatasetSplitter
from pathlib import Path

splitter = DatasetSplitter(
    dataset_root=Path("datasets/solid"),
    train_ratio=0.70,
    val_ratio=0.20,
    test_ratio=0.10,
    seed=42,
)
result = splitter.split_dataset(source_images_dir, source_labels_dir)
```
- Groups identical images by content hash to prevent data leakage between train and test.
- Writes full provenance log to `datasets/solid/metadata/split_manifest.json`.

---

## 7. Training Commands
### A. Smoke-Test (Lightweight Pipeline Verification)
```bash
python -m ai.training.train_solid --smoke-test --epochs 1 --batch 2 --imgsz 160 --device cpu
```
### B. Full Model Training (Production / GPU)
```bash
python -m ai.training.train_solid --model yolov8s.pt --epochs 60 --batch 16 --imgsz 640 --device auto
```

---

## 8. Evaluation Commands
```bash
python -m ai.training.evaluate_solid --model models/solid/best.pt --data datasets/solid/dataset.yaml --split val
```
Generates:
- `evaluation_report.json` with Precision, Recall, F1, mAP@0.50, and mAP@0.50:0.95.
- Per-class metrics breakdown for all 6 classes.
- Confusion matrix and PR curves saved in `models/solid/evaluation/eval/`.

---

## 9. Inference Usage

### A. Single Image Inference
```python
from ai.inference.solid_detector import SolidWasteDetector

detector = SolidWasteDetector(model_path="models/solid/best.pt", confidence_threshold=0.45)
result, annotated_image = detector.detect_image("path/to/test.jpg")
print(result.model_dump_json(indent=2))
```

### B. Video Stream Inference
```python
results = detector.detect_video(
    video_path="storage/test_videos/cctv_sample.mp4",
    output_path="storage/test_videos/annotated_output.mp4",
    sample_rate=2  # Process every 2nd frame
)
```

---

## 10. Structured Inference Output
```json
{
  "frame_index": 0,
  "timestamp": "2026-09-29T12:12:04.879220Z",
  "image_width": 640,
  "image_height": 720,
  "detections": [
    {
      "class_id": 0,
      "class_name": "plastic_bottle",
      "confidence": 0.9124,
      "bbox": {
        "x1": 140.0,
        "y1": 220.0,
        "x2": 195.0,
        "y2": 310.0
      },
      "normalized_bbox": {
        "x1": 0.2187,
        "y1": 0.3055,
        "x2": 0.3046,
        "y2": 0.4305
      }
    }
  ],
  "processing_time_ms": 14.2
}
```

---

## 11. Known Limitations
- The smoke test model was trained on 1 epoch of synthetic geometric samples for pipeline validation; real production weights must be trained on labeled municipal CCTV datasets.
- Single frame detections can still encounter momentary motion blur in low-light surveillance; multi-frame temporal validation is handled in Phase 5.

---

## 12. Scope Deferred to Later Phases
- **Phase 3**: Liquid waste dataset preparation and YOLO segmentation pipeline.
- **Phase 4**: Real RTSP stream ingestion, auto-reconnect, and multi-threaded video buffer.
- **Phase 5**: ByteTrack multi-object tracking, temporal persistence filters, and incident deduplication engine.
- **Phase 6+**: REST APIs, MongoDB CRUD, WebSockets, and React Dashboard.
