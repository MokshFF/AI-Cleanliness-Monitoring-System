# AI-Based National Cleanliness Monitoring System

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.4+-EE4C2C.svg?logo=pytorch)](https://pytorch.org)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0+-47A248.svg?logo=mongodb)](https://www.mongodb.com)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg?logo=docker)](https://www.docker.com)

A production-style AI surveillance platform for continuous monitoring of CCTV/IP cameras to automatically detect **solid waste** (litter, plastic, garbage piles) and **liquid waste** (spills, sewage, waterlogging, drain overflows).

---

## Key Highlights

- **Dual-Stream Detection**:
  - **Solid Waste**: YOLO object detection + ByteTrack object tracking.
  - **Liquid Waste**: YOLO instance segmentation + area & temporal persistence filtering.
- **False-Positive Prevention**: Spatial-temporal persistence validation prevents one-frame transient glitches from generating false alarms.
- **Real-Time Dashboards**: Incidents trigger instant notifications via WebSockets to an authenticated React admin interface.
- **Multi-Camera Architecture**: Supports simultaneous streams with configurable detection modes (`SOLID`, `LIQUID`, `BOTH`).
- **Security First**: Camera RTSP credentials and stream endpoints are strictly isolated from the frontend web clients.

---

## Directory Layout

```
├── .env.example              # Template environment configuration
├── requirements.txt          # Python dependencies
├── pyproject.toml            # Project packaging & pytest configuration
│
├── ai/                       # AI/ML Detection, Segmentation & Tracking
│   ├── configs/              # Solid and liquid class definitions (YAML)
│   ├── datasets/             # Data ingestion and format converters
│   ├── models/               # Model weights and checkpoint management
│   ├── training/             # Training pipelines (YOLO detect & seg)
│   ├── inference/            # Model inference pipelines
│   └── postprocessing/       # Tracking, temporal filters & deduplication
│
├── video/                    # Video Capture & RTSP Stream Management
│   └── stream_manager.py     # Resilient multi-camera ingestion
│
├── backend/                  # FastAPI Application
│   └── app/
│       ├── core/             # Configuration, logging & security
│       ├── db/               # MongoDB client & session management
│       ├── schemas/          # Pydantic validation schemas
│       ├── api/              # REST API endpoints
│       └── websockets/       # Real-time WebSocket broadcasting
│
├── frontend/                 # React + TypeScript Dashboard (Phase 7)
├── storage/                  # Gitignored snapshots, test videos, and logs
├── docker/                   # Dockerfiles & docker-compose.yml
└── docs/                     # Architecture & Phase documentation
```

---

## Getting Started

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Git
- MongoDB (or run via Docker)

### 2. Environment Setup
```bash
# Clone the repository
git clone <repo-url>
cd "AI Based Cleanliness Monitoring System"

# Copy environment variables
copy .env.example .env

# Install dependencies
pip install -r requirements.txt
```

### 3. Verify Phase 1 Setup
Run the automated verification suite:
```bash
python verify_phase1.py
# Or using pytest:
pytest tests/test_phase1.py
```

### 4. Running Backend Development Server
```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```
- API Docs: `http://localhost:8000/api/v1/docs`
- Health check: `http://localhost:8000/health`
