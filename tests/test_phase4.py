"""Phase 4 Video Ingestion, Multi-Camera Stream Management, and AI Routing Tests."""
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock
import cv2
import numpy as np
import pytest

from video.camera_config import (
    CameraConfig,
    CameraConnectionStatus,
    StreamType,
    mask_credentials,
)
from video.frame_buffer import BoundedFrameBuffer
from video.stream_capture import StreamCapture
from video.ai_router import AIRouter, CameraFrameAIResult
from video.camera_manager import CameraWorker, CameraManager
from video.simulator import create_simulated_camera_config
from ai.datasets.synthetic_smoke_data import generate_sample_video

ROOT_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def sample_test_video(tmp_path_factory) -> Path:
    """Fixture providing a synthetic local video file."""
    temp_dir = tmp_path_factory.mktemp("video_test")
    vid_path = temp_dir / "test_stream.mp4"
    generate_sample_video(vid_path, num_frames=20, fps=15)
    return vid_path


def test_camera_config_validation():
    """Verify CameraConfig validation, defaults, and detection_mode parsing."""
    cfg = CameraConfig(
        camera_id="CAM-001",
        name="Main Entrance Gate",
        location_name="North Perimeter",
        rtsp_url="rtsp://admin:SecretPass123@192.168.1.100:554/stream1",
        detection_mode="solid",
        target_fps=5.0,
    )
    assert cfg.camera_id == "CAM-001"
    assert cfg.detection_mode == "SOLID"
    assert cfg.stream_type == StreamType.RTSP
    assert "SecretPass123" not in cfg.safe_url
    assert "admin:***@" in cfg.safe_url

    # Invalid mode
    with pytest.raises(ValueError):
        CameraConfig(
            camera_id="CAM-002",
            name="Invalid",
            location_name="Zone",
            rtsp_url="rtsp://localhost/live",
            detection_mode="INVALID_MODE",
        )


def test_credential_masking():
    """Verify password masking in RTSP and HTTP URLs."""
    raw = "rtsp://user:SuperP@ssw0rd!@10.0.0.1:554/h264"
    masked = mask_credentials(raw)
    assert masked == "rtsp://user:***@10.0.0.1:554/h264"

    raw_clean = "rtsp://10.0.0.1:554/live"
    assert mask_credentials(raw_clean) == raw_clean


def test_bounded_frame_buffer_limits_and_dropping():
    """Verify buffer enforces maxsize and drops oldest frames when full."""
    buffer = BoundedFrameBuffer(maxsize=3)
    assert buffer.size == 0
    assert buffer.is_empty is True

    frame1 = np.zeros((10, 10, 3), dtype=np.uint8)
    frame2 = np.ones((10, 10, 3), dtype=np.uint8)
    frame3 = np.full((10, 10, 3), 2, dtype=np.uint8)
    frame4 = np.full((10, 10, 3), 3, dtype=np.uint8)

    # Put 3 frames (capacity reached)
    assert buffer.put(frame1, 1) is True
    assert buffer.put(frame2, 2) is True
    assert buffer.put(frame3, 3) is True
    assert buffer.is_full is True
    assert buffer.total_dropped == 0

    # Put 4th frame -> oldest (frame 1) should be dropped
    assert buffer.put(frame4, 4) is False
    assert buffer.size == 3
    assert buffer.total_dropped == 1

    # Dequeue oldest remaining item (should be frame 2)
    item = buffer.get(timeout=0.1)
    assert item is not None
    idx, ts, f = item
    assert idx == 2
    assert buffer.total_dequeued == 1


def test_stream_capture_local_video(sample_test_video: Path):
    """Verify StreamCapture ingests frames from local video file and reaches CONNECTED state."""
    cfg = CameraConfig(
        camera_id="CAM-TEST-FILE",
        name="Test Local File Camera",
        location_name="Lab",
        rtsp_url=str(sample_test_video),
        detection_mode="BOTH",
        buffer_size=10,
    )
    buf = BoundedFrameBuffer(maxsize=10)
    capture = StreamCapture(config=cfg, buffer=buf, loop_file=False)

    capture.start()
    time.sleep(0.5)

    assert capture.status in {CameraConnectionStatus.CONNECTED, CameraConnectionStatus.DISCONNECTED}
    assert capture.total_captured_frames > 0
    assert buf.size > 0

    capture.stop()
    assert capture.status == CameraConnectionStatus.STOPPED


def test_stream_capture_reconnect_logic():
    """Verify StreamCapture detects failure and exhausts backoff reconnection on unreachable URL."""
    cfg = CameraConfig(
        camera_id="CAM-UNREACHABLE",
        name="Dead Camera",
        location_name="Offline",
        rtsp_url="rtsp://127.0.0.1:9999/nonexistent",
        reconnect_attempts=2,
        reconnect_delay=0.05,
        backoff_factor=1.0,
    )
    mock_failing_cap = MagicMock()
    mock_failing_cap.isOpened.return_value = False

    capture = StreamCapture(config=cfg, capture_factory=lambda url: mock_failing_cap)
    capture.start()

    # Wait for the 2 retries to exhaust
    time.sleep(0.3)

    assert capture.status == CameraConnectionStatus.ERROR
    assert capture.reconnect_count >= 2
    assert capture.last_error is not None
    capture.stop()


def test_ai_router_routing_modes():
    """Verify AIRouter correctly routes based on SOLID, LIQUID, and BOTH detection modes."""
    mock_solid = MagicMock()
    mock_liquid = MagicMock()

    mock_solid.predict_frame.return_value = MagicMock(has_violations=True, count=2)
    mock_liquid.predict_frame.return_value = (MagicMock(has_violations=False, count=0), np.zeros((10, 10)))

    router = AIRouter(solid_detector=mock_solid, liquid_segmenter=mock_liquid)
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Mode SOLID
    res_solid = router.process_frame("CAM-001", dummy_frame, frame_index=1, detection_mode="SOLID")
    assert res_solid.solid_result is not None
    assert res_solid.liquid_result is None
    assert mock_solid.predict_frame.call_count == 1
    assert mock_liquid.predict_frame.call_count == 0

    # Mode LIQUID
    res_liquid = router.process_frame("CAM-002", dummy_frame, frame_index=2, detection_mode="LIQUID")
    assert res_liquid.solid_result is None
    assert res_liquid.liquid_result is not None
    assert mock_liquid.predict_frame.call_count == 1

    # Mode BOTH
    res_both = router.process_frame("CAM-003", dummy_frame, frame_index=3, detection_mode="BOTH")
    assert res_both.solid_result is not None
    assert res_both.liquid_result is not None


def test_camera_worker_sampling_and_lifecycle(sample_test_video: Path):
    """Verify CameraWorker samples frames at target FPS and outputs structured results."""
    cfg = CameraConfig(
        camera_id="CAM-WORKER-TEST",
        name="Worker Test",
        location_name="Zone A",
        rtsp_url=str(sample_test_video),
        detection_mode="SOLID",
        target_fps=2.0,  # 2 FPS out of 15 FPS video
        buffer_size=15,
    )

    collected_results = []
    worker = CameraWorker(
        config=cfg,
        on_result=lambda res: collected_results.append(res),
        loop_file=True,
    )

    worker.start()
    time.sleep(1.2)
    worker.stop()

    metrics = worker.get_health_metrics()
    assert metrics["camera_id"] == "CAM-WORKER-TEST"
    assert metrics["frames_received"] > 0
    assert metrics["frames_processed"] > 0
    assert len(collected_results) > 0

    first_res = collected_results[0]
    assert isinstance(first_res, CameraFrameAIResult)
    assert first_res.camera_id == "CAM-WORKER-TEST"
    assert first_res.timestamp.tzinfo is not None  # Timezone-aware
    assert first_res.frame is not None  # Evidence frame preserved


def test_multi_camera_manager_and_error_isolation(sample_test_video: Path):
    """Verify CameraManager coordinates multiple cameras and isolates errors."""
    mock_router = MagicMock()
    mock_router.process_frame.return_value = MagicMock()
    manager = CameraManager(router=mock_router)

    # Camera 1: Valid simulated local video
    cfg1 = CameraConfig(
        camera_id="CAM-001",
        name="Main Entrance",
        location_name="Gate 1",
        rtsp_url=str(sample_test_video),
        detection_mode="SOLID",
        target_fps=5.0,
    )

    # Camera 2: Unreachable camera (fails without crashing CAM-001)
    cfg2 = CameraConfig(
        camera_id="CAM-002",
        name="Faulty Camera",
        location_name="Drain Area",
        rtsp_url="rtsp://127.0.0.1:9999/fail",
        detection_mode="LIQUID",
        reconnect_attempts=1,
        reconnect_delay=0.05,
    )
    mock_failing_cap = MagicMock()
    mock_failing_cap.isOpened.return_value = False

    w1 = manager.add_camera(cfg1)
    w2 = manager.add_camera(cfg2, capture_factory=lambda url: mock_failing_cap)
    assert manager.camera_count == 2

    # Duplicate ID check
    with pytest.raises(ValueError):
        manager.add_camera(cfg1)

    manager.start_all()
    time.sleep(0.5)

    stat1 = manager.get_camera_status("CAM-001")
    stat2 = manager.get_camera_status("CAM-002")

    assert stat1 is not None
    assert stat2 is not None

    # CAM-001 should be actively capturing/connected
    assert stat1["frames_received"] > 0
    # CAM-002 should have encountered an error without crashing CAM-001
    assert stat2["status"] in {CameraConnectionStatus.ERROR, CameraConnectionStatus.RECONNECTING}

    all_stats = manager.get_all_statuses()
    assert len(all_stats) == 2

    manager.stop_all()


def test_graceful_shutdown(sample_test_video: Path):
    """Verify all worker threads terminate cleanly on stop."""
    cfg = CameraConfig(
        camera_id="CAM-SHUTDOWN",
        name="Shutdown Test",
        location_name="Zone B",
        rtsp_url=str(sample_test_video),
        detection_mode="BOTH",
    )
    mock_router = MagicMock()
    mock_router.process_frame.return_value = MagicMock()
    worker = CameraWorker(config=cfg, router=mock_router)
    worker.start()
    time.sleep(0.3)
    worker.stop(timeout=2.0)

    assert worker.capture.status == CameraConnectionStatus.STOPPED
    assert not worker._proc_thread.is_alive()
    assert not worker.capture._thread.is_alive()
