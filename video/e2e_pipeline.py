"""End-to-End Local CCTV Video Ingestion and AI Routing Pipeline Demonstration."""
import logging
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from video.camera_config import CameraConfig
from video.camera_manager import CameraManager
from video.simulator import create_simulated_camera_config
from video.ai_router import CameraFrameAIResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger("e2e_pipeline")


def run_e2e_demo(duration_seconds: float = 3.0) -> bool:
    """Runs a live end-to-end ingestion test across two simulated CCTV streams."""
    logger.info("=" * 70)
    logger.info("PHASE 4 — END-TO-END VIDEO INGESTION & AI ROUTING DEMONSTRATION")
    logger.info("=" * 70)

    solid_video = Path("storage/test_videos/cctv_sample.mp4")
    liquid_video = Path("storage/test_videos/liquid_cctv_sample.mp4")

    if not solid_video.is_file():
        from ai.datasets.synthetic_smoke_data import generate_sample_video
        generate_sample_video(solid_video, num_frames=30, fps=15)

    if not liquid_video.is_file():
        from ai.datasets.synthetic_liquid_smoke_data import generate_liquid_sample_video
        generate_liquid_sample_video(liquid_video, num_frames=30, fps=15)

    manager = CameraManager()
    processed_results = []

    def on_frame_result(result: CameraFrameAIResult):
        processed_results.append(result)
        logger.info(
            "--> Dispatched Result: %s (Time: %.1fms)",
            result.summary(),
            result.processing_time_ms,
        )

    # 1. Camera 1 (Main Gate - Solid Waste Detection Mode)
    cam1_cfg = create_simulated_camera_config(
        camera_id="CAM-001",
        video_path=solid_video,
        name="Main Entrance CCTV",
        location_name="North Gate Pavement",
        detection_mode="SOLID",
        target_fps=4.0,
    )

    # 2. Camera 2 (Drain Area - Liquid Waste Segmentation Mode)
    cam2_cfg = create_simulated_camera_config(
        camera_id="CAM-002",
        video_path=liquid_video,
        name="Drainage Channel CCTV",
        location_name="Perimeter Storm Drain",
        detection_mode="LIQUID",
        target_fps=4.0,
    )

    # 3. Camera 3 (Canteen Quad - Dual BOTH Mode)
    cam3_cfg = create_simulated_camera_config(
        camera_id="CAM-003",
        video_path=solid_video,
        name="Canteen Courtyard CCTV",
        location_name="Central Food Court",
        detection_mode="BOTH",
        target_fps=3.0,
    )

    manager.add_camera(cam1_cfg, on_result=on_frame_result)
    manager.add_camera(cam2_cfg, on_result=on_frame_result)
    manager.add_camera(cam3_cfg, on_result=on_frame_result)

    logger.info("Starting 3 independent camera workers simultaneously...")
    manager.start_all()

    time.sleep(duration_seconds)

    logger.info("Stopping camera ingestion...")
    manager.stop_all()

    statuses = manager.get_all_statuses()
    logger.info("=" * 70)
    logger.info("MULTI-CAMERA HEALTH TELEMETRY:")
    for s in statuses:
        logger.info(
            "  * %s (%s) | Status: %s | Captured: %d frames | Processed: %d frames | Dropped: %d | Proc FPS: %.1f",
            s["camera_id"],
            s["detection_mode"],
            s["status"],
            s["frames_received"],
            s["frames_processed"],
            s["frames_dropped"],
            s["processing_fps"],
        )
    logger.info("=" * 70)
    logger.info("Total AI-routed frame results received: %d", len(processed_results))

    success = len(processed_results) > 0 and all(s["frames_processed"] > 0 for s in statuses)
    if success:
        logger.info("[SUCCESS] End-to-end multi-camera ingestion verified!")
    else:
        logger.error("[FAILURE] One or more cameras failed to process frames.")

    return success


if __name__ == "__main__":
    passed = run_e2e_demo(duration_seconds=2.5)
    sys.exit(0 if passed else 1)
