#!/usr/bin/env python3
"""
Phase 1 Verification Script
Run this script to verify that the environment, folder structure,
configurations, security modules, and FastAPI endpoints are operational.
"""
import sys
from pathlib import Path

def print_status(message: str, success: bool = True):
    tag = "[OK]" if success else "[FAIL]"
    print(f"{tag:7} {message}")

def run_checks() -> bool:
    print("=" * 70)
    print("AI-BASED NATIONAL CLEANLINESS MONITORING SYSTEM - PHASE 1 AUDIT")
    print("=" * 70)
    all_passed = True

    # 1. Directory Structure Check
    root_dir = Path(__file__).resolve().parent
    required_dirs = [
        "ai/configs",
        "ai/datasets",
        "ai/models/weights",
        "ai/training",
        "ai/inference",
        "ai/postprocessing",
        "video",
        "backend/app/core",
        "backend/app/db",
        "backend/app/schemas",
        "backend/app/api",
        "backend/app/websockets",
        "storage/snapshots",
        "storage/test_videos",
        "storage/logs",
        "docker",
        "docs",
        "tests",
    ]
    dirs_ok = True
    for d in required_dirs:
        p = root_dir / d
        if not p.is_dir():
            print_status(f"Missing directory: {d}", False)
            dirs_ok = False
            all_passed = False
    if dirs_ok:
        print_status(f"All {len(required_dirs)} modular directories verified.")

    # 2. Config & Class Map Check
    try:
        from ai.configs import get_solid_classes, get_liquid_classes
        solid = get_solid_classes()
        liquid = get_liquid_classes()
        assert len(solid) == 6, f"Expected 6 solid classes, got {len(solid)}"
        assert len(liquid) == 4, f"Expected 4 liquid classes, got {len(liquid)}"
        print_status(f"Solid waste classes loaded: {', '.join(solid)}")
        print_status(f"Liquid waste classes loaded: {', '.join(liquid)}")
    except Exception as e:
        print_status(f"Class configuration loading failed: {e}", False)
        all_passed = False

    # 3. Settings Check
    try:
        from backend.app.core.config import settings
        assert settings.PROJECT_NAME
        print_status(f"Configuration loaded: {settings.PROJECT_NAME} (env: {settings.ENVIRONMENT})")
    except Exception as e:
        print_status(f"Settings loading failed: {e}", False)
        all_passed = False

    # 4. Security Check (JWT + Password hashing)
    try:
        from backend.app.core.security import get_password_hash, verify_password, create_access_token, decode_access_token
        h = get_password_hash("TestPass123")
        assert verify_password("TestPass123", h)
        token = create_access_token("test-user-id", extra_claims={"role": "ADMIN"})
        payload = decode_access_token(token)
        assert payload["sub"] == "test-user-id"
        print_status("Security module verified: bcrypt hashing and JWT token lifecycle OK.")
    except Exception as e:
        print_status(f"Security module failed: {e}", False)
        all_passed = False

    # 5. Pydantic Schemas Check
    try:
        from datetime import datetime, timezone
        from backend.app.schemas import CameraCreate, IncidentCreate, DetectionMode, WasteType
        cam = CameraCreate(
            camera_id="CAM-001",
            name="Main Gate",
            location_name="North Entrance",
            latitude=28.61,
            longitude=77.20,
            rtsp_url="rtsp://localhost:554/live",
            detection_mode=DetectionMode.BOTH,
        )
        inc = IncidentCreate(
            incident_id="INC-001",
            camera_id="CAM-001",
            waste_type=WasteType.LIQUID,
            category="sewage_overflow",
            confidence=0.92,
            snapshot_path="storage/snapshots/snap1.jpg",
            timestamp=datetime.now(timezone.utc),
        )
        print_status("Pydantic schema validation for Camera and Incident models OK.")
    except Exception as e:
        print_status(f"Pydantic schemas validation failed: {e}", False)
        all_passed = False

    # 6. FastAPI App & Health Check
    try:
        from fastapi.testclient import TestClient
        from backend.app.main import app
        client = TestClient(app)
        res = client.get("/health")
        assert res.status_code == 200 and res.json()["status"] == "healthy"
        status_res = client.get(f"{settings.API_V1_PREFIX}/status")
        assert status_res.status_code == 200
        print_status("FastAPI endpoints verified: /health and /api/v1/status OK.")
    except Exception as e:
        print_status(f"FastAPI check failed: {e}", False)
        all_passed = False

    print("=" * 70)
    if all_passed:
        print("\033[92mPHASE 1 VERIFICATION COMPLETED SUCCESSFULLY!\033[0m")
    else:
        print("\033[91mPHASE 1 VERIFICATION ENCOUNTERED ERRORS.\033[0m")
    print("=" * 70)
    return all_passed

if __name__ == "__main__":
    success = run_checks()
    sys.exit(0 if success else 1)
