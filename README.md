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
- [x] **Phase 5: Object Tracking + Temporal Persistence + Incident Engine**
- [x] **Phase 6: MongoDB Persistence + FastAPI REST API + Authentication**
- [x] **Phase 7: React Admin Web Dashboard**
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

### 4. Object Tracking & Incident Engine (Phase 5)
- **ByteTrack Multi-Object Tracking**: Two-stage IoU association with occlusion grace periods.
- **Solid & Liquid Temporal Persistence**: Multi-frame confirmation filters out false positives.
- **Deduplication Cooldown**: Suppresses alert spam for persistent violations (default: 180s).
- **Annotated Evidence Snapshots**: Saved to date-partitioned storage (`storage/snapshots/YYYY/MM/DD/INC-*.jpg`).
- **End-to-End Incident Pipeline Demonstration**:
  ```bash
  python ai/incident/e2e_incident_demo.py
  ```

---

## Backend Persistence & REST API (Phase 6)

### 1. Features
- **Async Motor MongoDB Persistence**: Repositories for Users, Cameras, Incidents, and Audit Logs.
- **FastAPI REST API (v1)**:
  - `/api/v1/auth/login`, `/api/v1/auth/me`: JWT Bearer authentication.
  - `/api/v1/users`: Admin-only user management with RBAC enforcement.
  - `/api/v1/cameras`: CCTV camera stream registry with automatic RTSP credential masking (`rtsp://***:***@...`).
  - `/api/v1/incidents`: Multi-field filtering (camera, status, severity, waste type, date range), pagination, and status updates (`NEW`, `ACKNOWLEDGED`, `RESOLVED`, `DISMISSED`).
- **Incident Persistence Bridge**: `IncidentPersistenceService` connects Phase 5 `IncidentEngine.on_incident` directly to MongoDB without blocking camera capture threads.
- **Audit Trails**: Non-repudiation audit logging for incident triage and camera modifications with sensitive token/password redaction.

### 2. Admin Bootstrap Script
Idempotently initializes the default administrator user:
```bash
python backend/scripts/create_admin.py
```

### 3. End-to-End Demonstration Script
Runs a full end-to-end integration demo of admin login, operator creation, camera registration, incident engine callback persistence, incident querying, and status updates:
```bash
python backend/scripts/e2e_phase6_demo.py
```

---

## Frontend Admin Dashboard (Phase 7)

A municipal command-center single-page application built with React 18, TypeScript, Vite, Tailwind CSS, and Recharts.

### 1. Key Capabilities
- **Role-Based Command Center**: Responsive layout with sidebar navigation, active session indicators, and role-based route guards (`Admin`, `Supervisor`, `Operator`).
- **Dashboard Telemetry**: Real-time KPI summary cards, Recharts incident severity distributions, waste category breakdowns, camera health status, and recent incident feed.
- **Incident Management**: Paginated table with debounced text search and multi-criteria filtering (camera, status, severity, waste type, date range).
- **Incident Detail & Evidence**: Visual inspection modal displaying authenticated snapshot evidence via secure blob streaming (`GET /api/v1/incidents/{id}/snapshot`), bounding box/mask telemetry, and workflow transition modal (`NEW` ➔ `ACKNOWLEDGED` ➔ `RESOLVED` / `DISMISSED`).
- **Camera Stream Registry**: Stream health status, operational mode badges (`SOLID`, `LIQUID`, `BOTH`), camera registration modal, and safe masked RTSP display (`rtsp://***:***@...`).
- **Personnel Administration**: Admin-exclusive user creation, role assignment, and account activation/deactivation controls.
- **System Settings & Diagnostics**: Live display of active YOLO taxonomies, API connection health, and security controls.

### 2. Running Frontend Locally
```bash
cd frontend
npm install
npm run dev
```
The Vite development server runs at `http://localhost:5173` and proxies `/api/v1` requests directly to FastAPI at `http://127.0.0.1:8000`.

### 3. Building for Production
```bash
cd frontend
npm run build
```
Production assets are compiled and type-checked into `frontend/dist/`.

---

## Running Automated Tests

Run all 104 unit, integration, and UI contract tests across Phases 1 through 7:
```bash
python -m pytest tests/ -v
```

Run Phase 1 audit:
```bash
python verify_phase1.py
```

