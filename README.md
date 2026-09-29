# AI-Based National Cleanliness Monitoring System

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.4+-EE4C2C.svg?logo=pytorch)](https://pytorch.org)
[![Ultralytics](https://img.shields.io/badge/Ultralytics-YOLOv8%2Fv11-00FFFF.svg)](https://docs.ultralytics.com)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0+-47A248.svg?logo=mongodb)](https://www.mongodb.com)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg?logo=docker)](https://www.docker.com)

A production-style AI surveillance platform for continuous monitoring of CCTV/IP cameras to automatically detect **solid waste** (litter, plastic, garbage piles) and **liquid waste** (spills, sewage, waterlogging, drain overflows).

---

## Architecture & Progress

- [x] **Phase 1: Project Architecture & Repository Setup**
- [x] **Phase 2: Solid Waste Dataset & YOLO Detection Pipeline**
- [ ] **Phase 3: Liquid Waste Dataset & Segmentation Pipeline**
- [ ] **Phase 4: Video Processing & RTSP Camera Integration**
- [ ] **Phase 5: Tracking + Temporal Persistence + Incident Engine**
- [ ] **Phase 6: FastAPI + MongoDB Backend**
- [ ] **Phase 7: React Admin Web Dashboard**
- [ ] **Phase 8: WebSocket Real-Time Alerts**
- [ ] **Phase 9: Camera Management, Maps & Analytics**
- [ ] **Phase 10: Multi-Camera Optimization & Docker Orchestration**

---

## Solid Waste Computer Vision Pipeline (Phase 2)

### 1. Solid Waste Taxonomy (6 Classes)
1. `plastic_bottle`
2. `plastic_bag`
3. `paper`
4. `can`
5. `food_waste`
6. `garbage_pile`

### 2. Dataset Validation
Audits YOLO annotation syntax, missing pairs, coordinate boundaries, empty files, and duplicates:
```bash
python ai/datasets/validator.py
```

### 3. Training Pipeline
Run a 1-epoch smoke-test on CPU/GPU:
```bash
python -m ai.training.train_solid --smoke-test --epochs 1 --batch 2 --imgsz 160 --device cpu
```
Full production training with CCTV-style augmentations:
```bash
python -m ai.training.train_solid --model yolov8s.pt --epochs 60 --batch 16 --imgsz 640 --device auto
```

### 4. Model Evaluation
Computes Precision, Recall, F1, mAP@0.50, and mAP@0.50:0.95:
```bash
python -m ai.training.evaluate_solid --model models/solid/best.pt --data datasets/solid/dataset.yaml --split val
```

### 5. Structured Inference

**Single Image:**
```python
from ai.inference.solid_detector import SolidWasteDetector

detector = SolidWasteDetector(model_path="models/solid/best.pt", confidence_threshold=0.45)
result, annotated_img = detector.detect_image("path/to/image.jpg")
print(result.model_dump_json(indent=2))
```

**Video Stream:**
```python
results = detector.detect_video(
    video_path="storage/test_videos/cctv_sample.mp4",
    output_path="storage/test_videos/annotated_sample.mp4",
    sample_rate=2
)
```

---

## Running Automated Tests

Run all unit & integration tests across completed phases:
```bash
python -m pytest tests/ -v
```

Run Phase 1 audit:
```bash
python verify_phase1.py
```
