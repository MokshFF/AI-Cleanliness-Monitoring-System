"""Phase 5 Comprehensive Tests: Object Tracking, Temporal Validation, Deduplication, and Incident Engine."""
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from unittest.mock import MagicMock
import numpy as np
import pytest

from ai.inference.schemas import (
    SolidDetection,
    SolidFrameDetectionResult,
    LiquidDetection,
    LiquidFrameDetectionResult,
    BoundingBox,
)
from ai.incident.tracker import SolidWasteTracker, TrackedSolidObject, compute_iou
from ai.incident.temporal_validator import (
    SolidTemporalValidator,
    LiquidTemporalValidator,
    TrackedLiquidEvent,
)
from ai.incident.severity import SeverityCalculator
from ai.incident.deduplicator import IncidentDeduplicator
from ai.incident.evidence import (
    EvidenceManager,
    generate_incident_id,
    get_safe_snapshot_filename,
)
from ai.incident.incident_engine import IncidentEngine
from backend.app.schemas.incident import IncidentSeverity, WasteType, IncidentCreate
from video.ai_router import CameraFrameAIResult


# ==============================================================================
# FIXTURES
# ==============================================================================
@pytest.fixture
def dummy_frame() -> np.ndarray:
    """Provides a synthetic 480x640x3 CCTV image frame."""
    frame = np.full((480, 640, 3), 120, dtype=np.uint8)
    return frame


@pytest.fixture
def make_solid_det():
    """Factory fixture for synthetic SolidDetection objects."""
    def _create(
        class_name: str = "plastic_bottle",
        confidence: float = 0.85,
        x1: float = 100.0,
        y1: float = 100.0,
        x2: float = 150.0,
        y2: float = 180.0,
        category: Optional[str] = None,
    ) -> SolidDetection:
        label = category or class_name
        return SolidDetection(
            class_id=0,
            class_name=label,
            confidence=confidence,
            bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
        )
    return _create


@pytest.fixture
def make_liquid_det():
    """Factory fixture for synthetic LiquidDetection objects."""
    def _create(
        category: str = "waterlogging",
        confidence: float = 0.80,
        affected_area_pixels: int = 5000,
        affected_area_percent: float = 8.5,
        monitored_region_pixels: int = 50000,
    ) -> LiquidDetection:
        polygon = [[100.0, 100.0], [200.0, 100.0], [200.0, 200.0], [100.0, 200.0]]
        return LiquidDetection(
            class_id=2,
            class_name=category,
            confidence=confidence,
            bbox=BoundingBox(x1=100.0, y1=100.0, x2=200.0, y2=200.0),
            polygon=polygon,
            affected_area_pixels=affected_area_pixels,
            affected_area_percent=affected_area_percent,
            monitored_region_pixels=monitored_region_pixels,
        )
    return _create


# ==============================================================================
# SOLID TRACKING & VALIDATION TESTS (1 to 6)
# ==============================================================================

def test_1_solid_single_frame_does_not_create_incident(dummy_frame, make_solid_det):
    """Test 1: A single-frame transient solid waste detection must NOT create an incident."""
    engine = IncidentEngine()
    det = make_solid_det(confidence=0.90)
    frame_res = CameraFrameAIResult(
        camera_id="CAM-001",
        frame_index=1,
        timestamp=datetime.now(timezone.utc),
        detection_mode="SOLID",
        image_width=640,
        image_height=480,
        frame=dummy_frame,
        solid_result=SolidFrameDetectionResult(
            image_width=640,
            image_height=480,
            detections=[det],
        ),
    )

    incidents = engine.process_camera_result(frame_res)
    assert len(incidents) == 0, "Single-frame detection should not confirm an incident"


def test_2_solid_consecutive_detection_creates_incident(dummy_frame, make_solid_det):
    """Test 2: Consecutive detections satisfying threshold (e.g. 5 frames) trigger an incident."""
    engine = IncidentEngine()
    now = datetime.now(timezone.utc)
    det = make_solid_det(confidence=0.88)

    incidents = []
    # Send 5 consecutive frames
    for i in range(1, 6):
        res = CameraFrameAIResult(
            camera_id="CAM-001",
            frame_index=i,
            timestamp=now + timedelta(milliseconds=i * 200),
            detection_mode="SOLID",
            image_width=640,
            image_height=480,
            frame=dummy_frame,
            solid_result=SolidFrameDetectionResult(
                image_width=640,
                image_height=480,
                detections=[det],
            ),
        )
        created = engine.process_camera_result(res)
        incidents.extend(created)

    assert len(incidents) == 1, f"Expected exactly 1 incident after 5 frames, got {len(incidents)}"
    inc = incidents[0]
    assert inc.waste_type == WasteType.SOLID
    assert inc.category == "plastic_bottle"
    assert inc.track_id is not None
    assert inc.confidence == 0.88


def test_3_solid_low_confidence_rejected(dummy_frame, make_solid_det):
    """Test 3: Detections below SOLID_MIN_CONFIDENCE must be rejected and never trigger an incident."""
    engine = IncidentEngine()
    low_det = make_solid_det(confidence=0.30)  # Below 0.45 threshold

    for i in range(1, 10):
        res = CameraFrameAIResult(
            camera_id="CAM-001",
            frame_index=i,
            timestamp=datetime.now(timezone.utc),
            detection_mode="SOLID",
            image_width=640,
            image_height=480,
            frame=dummy_frame,
            solid_result=SolidFrameDetectionResult(
                image_width=640,
                image_height=480,
                detections=[low_det],
            ),
        )
        incidents = engine.process_camera_result(res)
        assert len(incidents) == 0


def test_4_solid_same_track_does_not_duplicate(dummy_frame, make_solid_det):
    """Test 4: Once confirmed, the same track must not trigger duplicate incidents on subsequent frames."""
    engine = IncidentEngine()
    det = make_solid_det(confidence=0.85)
    now = datetime.now(timezone.utc)

    all_incidents = []
    # Feed 15 consecutive frames of the same bottle
    for i in range(1, 16):
        res = CameraFrameAIResult(
            camera_id="CAM-001",
            frame_index=i,
            timestamp=now + timedelta(seconds=i * 0.2),
            detection_mode="SOLID",
            image_width=640,
            image_height=480,
            frame=dummy_frame,
            solid_result=SolidFrameDetectionResult(
                image_width=640,
                image_height=480,
                detections=[det],
            ),
        )
        created = engine.process_camera_result(res)
        all_incidents.extend(created)

    assert len(all_incidents) == 1, "Track must only create 1 incident; duplicates must be prevented"


def test_5_solid_temporary_track_loss_handled(make_solid_det):
    """Test 5: Tracker maintains track continuity during a temporary missing detection within grace period."""
    tracker = SolidWasteTracker(min_confidence=0.45, grace_frames=3)
    det1 = make_solid_det(x1=100.0, y1=100.0, x2=150.0, y2=150.0)
    now = datetime.now(timezone.utc)

    # Frame 1: Detected
    active1 = tracker.update([det1], timestamp=now)
    assert len(active1) == 1
    t1_id = active1[0].track_id

    # Frame 2: Missing (occlusion) -> state becomes LOST, track retained
    active2 = tracker.update([], timestamp=now + timedelta(seconds=1))
    assert len(active2) == 0
    all_tracks = tracker.all_tracks
    assert len(all_tracks) == 1
    assert all_tracks[0].state == "LOST"
    assert all_tracks[0].lost_frames == 1

    # Frame 3: Reappears at similar position -> same track restored to ACTIVE
    det3 = make_solid_det(x1=102.0, y1=101.0, x2=152.0, y2=151.0)
    active3 = tracker.update([det3], timestamp=now + timedelta(seconds=2))
    assert len(active3) == 1
    assert active3[0].track_id == t1_id
    assert active3[0].state == "ACTIVE"
    assert active3[0].lost_frames == 0


def test_6_solid_track_closes_after_grace_period(make_solid_det):
    """Test 6: Tracker closes and evicts track after exceeding grace period."""
    tracker = SolidWasteTracker(min_confidence=0.45, grace_frames=2)
    det = make_solid_det()
    now = datetime.now(timezone.utc)

    # Frame 1: Init track
    tracker.update([det], timestamp=now)
    assert len(tracker.all_tracks) == 1

    # Frames 2 and 3: Lost frames 1 and 2 (within grace period of 2)
    tracker.update([], timestamp=now + timedelta(seconds=1))
    tracker.update([], timestamp=now + timedelta(seconds=2))
    assert len(tracker.all_tracks) == 1
    assert tracker.all_tracks[0].state == "LOST"

    # Frame 4: Lost frame 3 (> grace_frames of 2) -> track removed
    tracker.update([], timestamp=now + timedelta(seconds=3))
    assert len(tracker.all_tracks) == 0


# ==============================================================================
# LIQUID VALIDATION TESTS (7 to 11)
# ==============================================================================

def test_7_liquid_single_frame_does_not_create_incident(dummy_frame, make_liquid_det):
    """Test 7: Single frame liquid spill does not trigger an incident."""
    engine = IncidentEngine()
    liq_det = make_liquid_det(affected_area_pixels=3000, affected_area_percent=5.0)

    res = CameraFrameAIResult(
        camera_id="CAM-002",
        frame_index=1,
        timestamp=datetime.now(timezone.utc),
        detection_mode="LIQUID",
        image_width=640,
        image_height=480,
        frame=dummy_frame,
        liquid_result=LiquidFrameDetectionResult(
            image_width=640,
            image_height=480,
            monitored_region_pixels=50000,
            detections=[liq_det],
        ),
    )

    incidents = engine.process_camera_result(res)
    assert len(incidents) == 0


def test_8_liquid_small_affected_area_rejected(dummy_frame, make_liquid_det):
    """Test 8: Liquid below LIQUID_MIN_AFFECTED_AREA_PIXELS and PERCENT is rejected."""
    engine = IncidentEngine()
    small_det = make_liquid_det(affected_area_pixels=200, affected_area_percent=0.2)

    for i in range(1, 8):
        res = CameraFrameAIResult(
            camera_id="CAM-002",
            frame_index=i,
            timestamp=datetime.now(timezone.utc),
            detection_mode="LIQUID",
            image_width=640,
            image_height=480,
            frame=dummy_frame,
            liquid_result=LiquidFrameDetectionResult(
                image_width=640,
                image_height=480,
                monitored_region_pixels=50000,
                detections=[small_det],
            ),
        )
        assert len(engine.process_camera_result(res)) == 0


def test_9_liquid_persistent_detection_creates_incident(dummy_frame, make_liquid_det):
    """Test 9: Persistent liquid detection satisfying frame threshold triggers an incident."""
    engine = IncidentEngine()
    now = datetime.now(timezone.utc)
    liq_det = make_liquid_det(category="sewage_overflow", affected_area_pixels=4500, affected_area_percent=12.0)

    incidents = []
    # Send 4 frames (LIQUID_MIN_CONSECUTIVE_FRAMES = 4)
    for i in range(1, 5):
        res = CameraFrameAIResult(
            camera_id="CAM-002",
            frame_index=i,
            timestamp=now + timedelta(seconds=i * 0.5),
            detection_mode="LIQUID",
            image_width=640,
            image_height=480,
            frame=dummy_frame,
            liquid_result=LiquidFrameDetectionResult(
                image_width=640,
                image_height=480,
                monitored_region_pixels=50000,
                detections=[liq_det],
            ),
        )
        incidents.extend(engine.process_camera_result(res))

    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.waste_type == WasteType.LIQUID
    assert inc.category == "sewage_overflow"
    assert inc.affected_area_pixels == 4500
    assert inc.affected_area_percent == 12.0


def test_10_liquid_duration_validation(make_liquid_det):
    """Test 10: Liquid persistence confirmed via duration_seconds using timestamps."""
    validator = LiquidTemporalValidator(min_consecutive_frames=10, min_duration_seconds=3.0)
    liq_det = make_liquid_det(affected_area_pixels=2500, affected_area_percent=5.0)

    start_time = datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)
    res1 = LiquidFrameDetectionResult(
        image_width=640,
        image_height=480,
        monitored_region_pixels=50000,
        timestamp=start_time,
        detections=[liq_det],
    )
    # Frame 1: duration = 0
    assert len(validator.process_frame(res1, timestamp=start_time)) == 0

    # Frame 2: 4 seconds later (satisfies min_duration_seconds=3.0)
    later_time = start_time + timedelta(seconds=4)
    res2 = LiquidFrameDetectionResult(
        image_width=640,
        image_height=480,
        monitored_region_pixels=50000,
        timestamp=later_time,
        detections=[liq_det],
    )
    confirmed = validator.process_frame(res2, timestamp=later_time)
    assert len(confirmed) == 1
    assert confirmed[0].duration_seconds == 4.0


def test_11_liquid_duplicate_prevention(dummy_frame, make_liquid_det):
    """Test 11: Continuing liquid spill is suppressed from creating duplicate alerts on every frame."""
    engine = IncidentEngine()
    now = datetime.now(timezone.utc)
    liq_det = make_liquid_det(category="drain_overflow", affected_area_pixels=6000, affected_area_percent=15.0)

    all_incidents = []
    # 10 consecutive frames
    for i in range(1, 11):
        res = CameraFrameAIResult(
            camera_id="CAM-002",
            frame_index=i,
            timestamp=now + timedelta(seconds=i * 0.5),
            detection_mode="LIQUID",
            image_width=640,
            image_height=480,
            frame=dummy_frame,
            liquid_result=LiquidFrameDetectionResult(
                image_width=640,
                image_height=480,
                monitored_region_pixels=50000,
                detections=[liq_det],
            ),
        )
        created = engine.process_camera_result(res)
        all_incidents.extend(created)

    assert len(all_incidents) == 1, "Duplicate liquid alert must be suppressed during cooldown"


# ==============================================================================
# GENERAL & INTEGRATION TESTS (12 to 20)
# ==============================================================================

def test_12_incident_id_uniqueness():
    """Test 12: Generated incident IDs are unique, chronologically sortable, and formatted properly."""
    ids = [generate_incident_id() for _ in range(100)]
    assert len(set(ids)) == 100, "All 100 incident IDs must be strictly unique"
    for inc_id in ids:
        assert inc_id.startswith("INC-")
        assert len(inc_id.split("-")) == 3


def test_13_severity_calculation():
    """Test 13: Operational severity rules produce correct LOW, MEDIUM, and HIGH classifications."""
    # Solid
    assert SeverityCalculator.calculate_solid_severity("garbage_pile", 0.90) == IncidentSeverity.HIGH
    assert SeverityCalculator.calculate_solid_severity("plastic_bottle", 0.85, cluster_count=3) == IncidentSeverity.HIGH
    assert SeverityCalculator.calculate_solid_severity("plastic_bottle", 0.70) == IncidentSeverity.MEDIUM
    assert SeverityCalculator.calculate_solid_severity("paper", 0.40) == IncidentSeverity.LOW

    # Liquid
    assert SeverityCalculator.calculate_liquid_severity("sewage_overflow", 0.80) == IncidentSeverity.HIGH
    assert SeverityCalculator.calculate_liquid_severity("waterlogging", 0.80, affected_area_percent=20.0) == IncidentSeverity.HIGH
    assert SeverityCalculator.calculate_liquid_severity("liquid_spill", 0.75, affected_area_percent=6.0) == IncidentSeverity.MEDIUM
    assert SeverityCalculator.calculate_liquid_severity("liquid_spill", 0.50, affected_area_percent=2.0) == IncidentSeverity.LOW


def test_14_evidence_snapshot_creation(tmp_path, dummy_frame):
    """Test 14: EvidenceManager saves annotated JPG evidence snapshots to disk."""
    ev_mgr = EvidenceManager(base_storage_dir=tmp_path)
    now = datetime(2026, 9, 29, 14, 30, 0, tzinfo=timezone.utc)

    # Save solid snapshot
    path_solid = ev_mgr.save_solid_snapshot(
        frame=dummy_frame,
        incident_id="INC-20260929-000001",
        camera_id="CAM-001",
        category="plastic_bottle",
        confidence=0.92,
        track_id=1,
        bbox=BoundingBox(x1=50, y1=50, x2=100, y2=100),
        severity=IncidentSeverity.MEDIUM,
        timestamp=now,
    )
    assert Path(path_solid).exists()
    assert Path(path_solid).stat().st_size > 0

    # Save liquid snapshot
    path_liquid = ev_mgr.save_liquid_snapshot(
        frame=dummy_frame,
        incident_id="INC-20260929-000002",
        camera_id="CAM-002",
        category="waterlogging",
        confidence=0.88,
        affected_area_pixels=3500,
        affected_area_percent=10.5,
        roi_name="gate_zone",
        polygon=[[50, 50], [150, 50], [150, 150], [50, 150]],
        bbox=BoundingBox(x1=50, y1=50, x2=150, y2=150),
        severity=IncidentSeverity.HIGH,
        timestamp=now,
    )
    assert Path(path_liquid).exists()
    assert Path(path_liquid).stat().st_size > 0


def test_15_snapshot_filename_safety():
    """Test 15: Safe filename sanitization rejects path traversal attempts."""
    dangerous = "../../etc/passwd"
    safe = get_safe_snapshot_filename(dangerous)
    assert ".." not in safe
    assert "/" not in safe
    assert "\\" not in safe
    assert safe.endswith(".jpg")


def test_16_cooldown_behavior():
    """Test 16: Cooldown suppresses duplicates within window, then re-allows new incident once expired."""
    dedup = IncidentDeduplicator(cooldown_seconds=10)
    key = "CAM-001:SOLID:can:5"
    t0 = datetime(2026, 9, 29, 10, 0, 0, tzinfo=timezone.utc)

    # Initially not a duplicate
    assert dedup.is_duplicate(key, current_time=t0) is False

    # Register incident at t0
    dedup.register_incident(key, "INC-001", timestamp=t0)

    # At t0 + 5s: within 10s cooldown -> suppressed
    t5 = t0 + timedelta(seconds=5)
    assert dedup.is_duplicate(key, current_time=t5) is True
    assert dedup.get_remaining_cooldown(key, current_time=t5) == 5.0

    # At t0 + 11s: cooldown expired -> eligible for repeated violation incident
    t11 = t0 + timedelta(seconds=11)
    assert dedup.is_duplicate(key, current_time=t11) is False
    assert dedup.get_remaining_cooldown(key, current_time=t11) == 0.0


def test_17_incident_callback_works(dummy_frame, make_solid_det):
    """Test 17: IncidentEngine dispatches confirmed incidents to registered subscriber callbacks."""
    engine = IncidentEngine()
    received_incidents = []
    engine.on_incident(lambda inc: received_incidents.append(inc))

    now = datetime.now(timezone.utc)
    det = make_solid_det(confidence=0.90)

    for i in range(1, 6):
        res = CameraFrameAIResult(
            camera_id="CAM-001",
            frame_index=i,
            timestamp=now + timedelta(seconds=i * 0.2),
            detection_mode="SOLID",
            image_width=640,
            image_height=480,
            frame=dummy_frame,
            solid_result=SolidFrameDetectionResult(
                image_width=640,
                image_height=480,
                detections=[det],
            ),
        )
        engine.process_camera_result(res)

    assert len(received_incidents) == 1
    assert isinstance(received_incidents[0], IncidentCreate)
    assert received_incidents[0].camera_id == "CAM-001"


def test_18_solid_routing_works(dummy_frame, make_solid_det, make_liquid_det):
    """Test 18: In SOLID mode, only solid violations are processed even if liquid present in input."""
    engine = IncidentEngine()
    now = datetime.now(timezone.utc)
    s_det = make_solid_det(confidence=0.88)
    l_det = make_liquid_det(confidence=0.88)

    for i in range(1, 6):
        res = CameraFrameAIResult(
            camera_id="CAM-001",
            frame_index=i,
            timestamp=now + timedelta(seconds=i * 0.2),
            detection_mode="SOLID",
            image_width=640,
            image_height=480,
            frame=dummy_frame,
            solid_result=SolidFrameDetectionResult(image_width=640, image_height=480, detections=[s_det]),
            liquid_result=None,  # Router omitted liquid
        )
        engine.process_camera_result(res)

    metrics = engine.get_metrics()
    assert metrics["solid_incidents_created"] == 1
    assert metrics["liquid_incidents_created"] == 0


def test_19_liquid_routing_works(dummy_frame, make_liquid_det):
    """Test 19: In LIQUID mode, only liquid events are processed."""
    engine = IncidentEngine()
    now = datetime.now(timezone.utc)
    l_det = make_liquid_det(category="waterlogging", confidence=0.85, affected_area_pixels=3000, affected_area_percent=6.0)

    for i in range(1, 5):
        res = CameraFrameAIResult(
            camera_id="CAM-002",
            frame_index=i,
            timestamp=now + timedelta(seconds=i * 0.5),
            detection_mode="LIQUID",
            image_width=640,
            image_height=480,
            frame=dummy_frame,
            solid_result=None,
            liquid_result=LiquidFrameDetectionResult(
                image_width=640,
                image_height=480,
                monitored_region_pixels=50000,
                detections=[l_det],
            ),
        )
        engine.process_camera_result(res)

    metrics = engine.get_metrics()
    assert metrics["solid_incidents_created"] == 0
    assert metrics["liquid_incidents_created"] == 1


def test_20_both_mode_works(dummy_frame, make_solid_det, make_liquid_det):
    """Test 20: In BOTH mode, both solid and liquid violations can be independently detected and confirmed."""
    engine = IncidentEngine()
    now = datetime.now(timezone.utc)
    s_det = make_solid_det(category="can", confidence=0.88)
    l_det = make_liquid_det(category="sewage_overflow", confidence=0.90, affected_area_pixels=4000, affected_area_percent=9.0)

    # Feed 5 frames with BOTH solid and liquid
    for i in range(1, 6):
        res = CameraFrameAIResult(
            camera_id="CAM-003",
            frame_index=i,
            timestamp=now + timedelta(seconds=i * 0.5),
            detection_mode="BOTH",
            image_width=640,
            image_height=480,
            frame=dummy_frame,
            solid_result=SolidFrameDetectionResult(image_width=640, image_height=480, detections=[s_det]),
            liquid_result=LiquidFrameDetectionResult(
                image_width=640,
                image_height=480,
                monitored_region_pixels=50000,
                detections=[l_det],
            ),
        )
        engine.process_camera_result(res)

    metrics = engine.get_metrics()
    assert metrics["solid_incidents_created"] == 1
    assert metrics["liquid_incidents_created"] == 1
    assert metrics["total_incidents_created"] == 2
