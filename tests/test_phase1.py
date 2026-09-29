"""Phase 1 verification test suite."""
from datetime import datetime, timezone
import pytest
from pathlib import Path

from backend.app.core.config import settings
from backend.app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
)
from backend.app.schemas import (
    CameraCreate,
    CameraStatus,
    DetectionMode,
    IncidentCreate,
    IncidentSeverity,
    WasteType,
    UserCreate,
    UserRole,
)
from ai.configs import get_solid_classes, get_liquid_classes

ROOT_DIR = Path(__file__).resolve().parent.parent

def test_directory_structure():
    """Verify all required top-level and subdirectories exist."""
    required_dirs = [
        ROOT_DIR / "ai",
        ROOT_DIR / "ai" / "configs",
        ROOT_DIR / "ai" / "datasets",
        ROOT_DIR / "ai" / "models" / "weights",
        ROOT_DIR / "ai" / "training",
        ROOT_DIR / "ai" / "inference",
        ROOT_DIR / "ai" / "postprocessing",
        ROOT_DIR / "video",
        ROOT_DIR / "backend",
        ROOT_DIR / "backend" / "app",
        ROOT_DIR / "backend" / "app" / "core",
        ROOT_DIR / "backend" / "app" / "db",
        ROOT_DIR / "backend" / "app" / "schemas",
        ROOT_DIR / "backend" / "app" / "api",
        ROOT_DIR / "backend" / "app" / "websockets",
        ROOT_DIR / "storage",
        ROOT_DIR / "storage" / "snapshots",
        ROOT_DIR / "storage" / "test_videos",
        ROOT_DIR / "storage" / "logs",
        ROOT_DIR / "docker",
        ROOT_DIR / "docs",
        ROOT_DIR / "tests",
    ]
    for d in required_dirs:
        assert d.is_dir(), f"Required directory missing: {d}"

def test_class_definitions():
    """Verify solid and liquid class configurations contain required classes."""
    solid_classes = get_solid_classes()
    liquid_classes = get_liquid_classes()

    expected_solid = [
        "plastic_bottle",
        "plastic_bag",
        "paper",
        "can",
        "food_waste",
        "garbage_pile",
    ]
    expected_liquid = [
        "liquid_spill",
        "sewage_overflow",
        "waterlogging",
        "drain_overflow",
    ]

    assert solid_classes == expected_solid, f"Unexpected solid classes: {solid_classes}"
    assert liquid_classes == expected_liquid, f"Unexpected liquid classes: {liquid_classes}"

def test_settings_loading():
    """Verify settings are successfully loaded with correct defaults."""
    assert settings.PROJECT_NAME == "AI-Based National Cleanliness Monitoring System"
    assert settings.PROCESS_EVERY_N_FRAMES == 3
    assert settings.SOLID_CONFIDENCE_THRESHOLD == 0.45
    assert settings.LIQUID_CONFIDENCE_THRESHOLD == 0.40
    assert len(settings.CORS_ORIGINS) >= 2

def test_security_helpers():
    """Verify password hashing and JWT token lifecycle."""
    plain_pw = "SecureTestPassword@123"
    hashed_pw = get_password_hash(plain_pw)
    assert verify_password(plain_pw, hashed_pw) is True
    assert verify_password("WrongPassword", hashed_pw) is False

    token = create_access_token(subject="user_123", extra_claims={"role": "ADMIN"})
    decoded = decode_access_token(token)
    assert decoded["sub"] == "user_123"
    assert decoded["role"] == "ADMIN"
    assert "exp" in decoded

def test_pydantic_schemas():
    """Verify validation of Camera, Incident, and User models."""
    camera = CameraCreate(
        camera_id="CAM-001",
        name="Main Entrance Gate",
        location_name="North Zone Gate 1",
        latitude=28.6139,
        longitude=77.2090,
        rtsp_url="rtsp://admin:pass@192.168.1.100:554/stream1",
        detection_mode=DetectionMode.BOTH,
    )
    assert camera.camera_id == "CAM-001"
    assert camera.detection_mode == DetectionMode.BOTH

    incident = IncidentCreate(
        incident_id="INC-2026-001",
        camera_id="CAM-001",
        waste_type=WasteType.SOLID,
        category="plastic_bottle",
        confidence=0.88,
        snapshot_path="storage/snapshots/snap_001.jpg",
        timestamp=datetime.now(timezone.utc),
        severity=IncidentSeverity.LOW,
    )
    assert incident.category == "plastic_bottle"
    assert incident.confidence == 0.88

    user = UserCreate(
        email="test@cleanliness.gov.in",
        full_name="Test Operator",
        role=UserRole.OPERATOR,
        password="SecureOperatorPass123",
    )
    assert user.role == UserRole.OPERATOR

def test_fastapi_health_endpoint():
    """Verify the FastAPI health check endpoint returns 200."""
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

    status_resp = client.get(f"{settings.API_V1_PREFIX}/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert "solid" in status_data["supported_waste_types"]
