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
- [x] **Phase 3: Liquid Waste Dataset & Segmentation Pipeline**
- [x] **Phase 4: Real CCTV / RTSP Video Ingestion + Multi-Camera Pipeline**
- [ ] **Phase 5: Tracking + Temporal Persistence + Incident Engine**
- [ ] **Phase 6: FastAPI + MongoDB Backend**
- [ ] **Phase 7: React Admin Web Dashboard**
- [ ] **Phase 8: WebSocket Real-Time Alerts**
- [ ] **Phase 9: Camera Management, Maps & Analytics**
- [ ] **Phase 10: Multi-Camera Optimization & Docker Orchestration**

---

## Computer Vision & Video Ingestion Pipelines

### 1. Solid Waste Detection (Phase 2)
- **Classes**: `plastic_bottle`, `plastic_bag`, `paper`, `can`, `food_waste`, `garbage_pile`
- **Validation**: `python ai/datasets/validator.py`
- **Training**: `python -m ai.training.train_solid --smoke-test --epochs 1 --batch 2 --imgsz 160 --device cpu`
- **Evaluation**: `python -m ai.training.evaluate_solid --model models/solid/best.pt --data datasets/solid/dataset.yaml --split val`

### 2. Liquid Waste Segmentation & Affected-Area Analysis (Phase 3)
- **Classes**: `liquid_spill`, `sewage_overflow`, `waterlogging`, `drain_overflow`
- **Validation**: `python ai/datasets/liquid_validator.py`
- **Training**: `python -m ai.training.train_liquid --data datasets/liquid/dataset.yaml --smoke-test --epochs 1 --batch 2 --imgsz 160 --device cpu`
- **Evaluation**: `python -m ai.training.evaluate_liquid --model models/liquid/best.pt --data datasets/liquid/dataset.yaml --split val`

### 3. Real CCTV / RTSP Video Ingestion & AI Routing (Phase 4)
- **Bounded Frame Buffer**: Oldest-frame drop policy avoids latency buildup and OOM.
- **Auto-Reconnect & Backoff**: Automatic recovery for unstable RTSP connections.
- **Target FPS Sampling**: Conserves compute while maintaining detection cadence.
- **AI Router**: Dispatches frames based on camera capability (`SOLID`, `LIQUID`, or `BOTH`).
- **End-to-End Multi-Camera Demonstration**:
  ```bash
  python video/e2e_pipeline.py
  ```

---

## Running Automated Tests

Run all 34 unit & integration tests across Phases 1 through 4:
```bash
python -m pytest tests/ -v
```

Run Phase 1 audit:
```bash
python verify_phase1.py
```
