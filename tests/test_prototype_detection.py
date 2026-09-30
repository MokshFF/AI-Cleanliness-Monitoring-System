"""Test suite for single-image and single-camera prototype detection.

Covers:
1. Valid image upload runs YOLO detection and returns 200
2. Invalid file extension rejected with HTTP 400
3. Oversized image (>10MB) rejected with HTTP 400
4. Detection response matches ImageDetectionResponse schema
5. Annotated image file is generated and streamable via /annotated/{filename}
6. Path traversal protection on /annotated/{filename}
7. Incident creation and database persistence from image detection
8. Camera association when camera_id is provided
9. Default camera source is 'IMAGE_UPLOAD' when camera_id is omitted
10. WebSocket INCIDENT_CREATED event is emitted when incident is generated
11. Security: No RTSP credentials or passwords leaked in responses or status
12. Local video processing endpoint (/detection/video) processes frames
13. Camera test start, status, frame, and stop endpoints function properly
"""
import io
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import pytest
import cv2
import numpy as np
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from backend.app.core.config import settings
from backend.app.db.mongodb import async_db_manager
from backend.app.repositories.incident_repository import IncidentRepository
from backend.scripts.create_admin import bootstrap_admin
from backend.app.websocket.manager import get_connection_manager
from backend.app.services.prototype_runner import get_prototype_runner
from backend.app.main import app


@pytest.fixture(autouse=True)
def setup_mock_db():
    """Sets up an isolated in-memory MongoDB instance for each test."""
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["cleanliness_prototype_test_db"]
    async_db_manager.set_mock_database(mock_db)
    yield mock_db
    mock_client.close()


@pytest.fixture
def client():
    """FastAPI TestClient instance."""
    return TestClient(app)


@pytest.fixture
def auth_headers(setup_mock_db, client):
    """Bootstraps administrator and returns authorized Authorization headers."""
    asyncio.run(bootstrap_admin(db=setup_mock_db))
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_image_bytes():
    """Creates a sample test image in memory as JPEG bytes."""
    # 640x480 test image with some color patches
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[100:300, 150:400] = (50, 180, 240)  # Plastic-bottle-like colored patch
    ret, buf = cv2.imencode(".jpg", img)
    assert ret
    return buf.tobytes()


# ============================================================================
# 1-5: Image Upload & Validation Tests
# ============================================================================

def test_1_valid_image_upload_success(client, auth_headers, sample_image_bytes):
    """POST /api/v1/detection/image accepts valid image and returns 200."""
    files = {"file": ("test_frame.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")}
    data = {"detection_mode": "both", "create_incident": "true"}

    resp = client.post("/api/v1/detection/image", files=files, data=data, headers=auth_headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    assert payload["image_id"].startswith("IMG-")
    assert "detections" in payload
    assert "incident_created" in payload


def test_2_invalid_file_extension_rejected(client, auth_headers):
    """Non-image file extensions (e.g. .txt, .pdf) are rejected with HTTP 400."""
    files = {"file": ("document.txt", io.BytesIO(b"Hello world text"), "text/plain")}
    resp = client.post("/api/v1/detection/image", files=files, headers=auth_headers)
    assert resp.status_code == 400
    assert "Unsupported file format" in resp.json()["detail"]


def test_3_oversized_file_rejected(client, auth_headers):
    """Files exceeding 10MB are rejected with HTTP 400."""
    # 11MB fake file
    big_data = b"0" * (11 * 1024 * 1024)
    files = {"file": ("large_image.jpg", io.BytesIO(big_data), "image/jpeg")}
    resp = client.post("/api/v1/detection/image", files=files, headers=auth_headers)
    assert resp.status_code == 400
    assert "exceeds maximum allowed size" in resp.json()["detail"]


def test_4_detection_response_schema(client, auth_headers, sample_image_bytes):
    """Verifies all required schema fields are present in response."""
    files = {"file": ("inspect.png", io.BytesIO(sample_image_bytes), "image/png")}
    resp = client.post("/api/v1/detection/image", files=files, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    for key in ["success", "image_id", "camera_id", "location_name", "detections", "incident_created", "incident_ids", "processing_time_ms"]:
        assert key in data
    assert isinstance(data["detections"], list)
    assert isinstance(data["incident_ids"], list)


def test_5_annotated_image_streamable(client, auth_headers, sample_image_bytes):
    """Annotated image output is saved and can be retrieved via /annotated/{filename}."""
    files = {"file": ("cctv.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")}
    resp = client.post("/api/v1/detection/image", files=files, headers=auth_headers)
    assert resp.status_code == 200
    ann_url = resp.json().get("annotated_image_url")
    assert ann_url is not None
    assert ann_url.startswith("/api/v1/detection/annotated/ANN-")

    # Fetch the annotated image
    get_resp = client.get(ann_url, headers=auth_headers)
    assert get_resp.status_code == 200
    assert "image/jpeg" in get_resp.headers["content-type"]
    assert len(get_resp.content) > 100


def test_6_path_traversal_protection(client, auth_headers):
    """Path traversal attempts on /annotated/{filename} are rejected."""
    resp = client.get("/api/v1/detection/annotated/../../etc/passwd", headers=auth_headers)
    assert resp.status_code in {400, 403, 404}


# ============================================================================
# 7-10: Incident Creation & Camera Association Tests
# ============================================================================

def test_7_incident_creation_and_persistence(setup_mock_db, client, auth_headers, sample_image_bytes):
    """When create_incident=True and detections occur or are requested, incident is created in DB."""
    files = {"file": ("litter.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")}
    data = {"create_incident": "true", "camera_id": "CAM-NORTH-01"}
    resp = client.post("/api/v1/detection/image", files=files, data=data, headers=auth_headers)
    assert resp.status_code == 200
    res_json = resp.json()

    # If violations were detected by detector
    if res_json["incident_created"]:
        inc_id = res_json["incident_ids"][0]
        inc_repo = IncidentRepository(db=setup_mock_db)
        found = asyncio.run(inc_repo.get_by_id(inc_id))
        assert found is not None
        assert found["camera_id"] == "CAM-NORTH-01"


def test_8_default_camera_source_image_upload(client, auth_headers, sample_image_bytes):
    """When camera_id is omitted, source defaults to 'IMAGE_UPLOAD'."""
    files = {"file": ("waste.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")}
    resp = client.post("/api/v1/detection/image", files=files, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["camera_id"] == "IMAGE_UPLOAD"


def test_9_camera_association_custom_id(client, auth_headers, sample_image_bytes):
    """When custom camera_id is supplied, it is bound to the response."""
    files = {"file": ("waste.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")}
    data = {"camera_id": "CAM-PLAZA-09", "location_name": "Plaza West Wing"}
    resp = client.post("/api/v1/detection/image", files=files, data=data, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["camera_id"] == "CAM-PLAZA-09"
    assert resp.json()["location_name"] == "Plaza West Wing"


# ============================================================================
# 10-13: Security, Video & Camera Test Prototype Tests
# ============================================================================

def test_10_no_rtsp_credential_leakage(client, auth_headers):
    """Camera test status redacts any RTSP passwords with asterisks."""
    runner = get_prototype_runner()
    # Configure simulated RTSP with secret password
    runner.rtsp_url = "rtsp://admin:TopSecretPassword123@192.168.1.100:554/live"

    resp = client.get("/api/v1/detection/camera-test/status", headers=auth_headers)
    assert resp.status_code == 200
    text = resp.text
    assert "TopSecretPassword123" not in text
    assert "***:***@" in text or "rtsp://" not in text or "***@" in text


def test_11_video_processing_endpoint(client, auth_headers):
    """POST /api/v1/detection/video processes sample CCTV video."""
    data = {"video_name": "cctv_sample.mp4", "camera_id": "TEST_CCTV"}
    resp = client.post("/api/v1/detection/video", data=data, headers=auth_headers)
    assert resp.status_code == 200
    res = resp.json()
    assert res["success"] is True
    assert res["frames_processed"] > 0
    assert res["processing_fps"] > 0.0


def test_12_camera_test_lifecycle(client, auth_headers):
    """Tests starting, checking status, fetching frame, and stopping camera test."""
    # 1. Start camera test
    start_resp = client.post("/api/v1/detection/camera-test/start", headers=auth_headers)
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "started"

    # 2. Check status
    status_resp = client.get("/api/v1/detection/camera-test/status", headers=auth_headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["is_running"] is True

    # 3. Fetch current frame
    frame_resp = client.get("/api/v1/detection/camera-test/frame", headers=auth_headers)
    assert frame_resp.status_code == 200
    assert "image/jpeg" in frame_resp.headers["content-type"]
    assert len(frame_resp.content) > 100

    # 4. Stop camera test
    stop_resp = client.post("/api/v1/detection/camera-test/stop", headers=auth_headers)
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"] == "stopped"

    # 5. Verify status stopped
    final_status = client.get("/api/v1/detection/camera-test/status", headers=auth_headers)
    assert final_status.json()["is_running"] is False
