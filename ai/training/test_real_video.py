"""Video Ingestion & Incident Engine Verification on real CCTV sample.

Tests video frame processing at 5 FPS through the new solid waste model,
evaluating tracking, temporal validation, duplicate suppression, and incident generation.
"""
import logging
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import cv2
from ai.inference.solid_detector import SolidWasteDetector
from ai.incident.incident_engine import IncidentEngine
from video.ai_router import CameraFrameAIResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger("video_test")


def test_video(video_path: Path, target_fps: int = 5) -> Dict[str, Any]:
    logger.info("Opening video: %s", video_path)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video at: {video_path}")

    orig_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / orig_fps

    frame_interval = max(1, int(round(orig_fps / target_fps)))
    logger.info("Video duration: %.2f s (%d frames @ %.1f FPS), sampling every %d frame(s) (~%d FPS)",
                duration_sec, total_frames, orig_fps, frame_interval, target_fps)

    detector = SolidWasteDetector(confidence_threshold=0.30)
    engine = IncidentEngine()
    incidents = []
    engine.on_incident(lambda inc: incidents.append(inc))

    processed_frames = 0
    raw_detections_count = 0
    t0 = time.perf_counter()

    frame_idx = 0
    simulated_time = datetime.now(timezone.utc)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            h, w = frame.shape[:2]
            res = detector.predict_frame(frame, frame_index=processed_frames)
            raw_detections_count += res.count

            c_res = CameraFrameAIResult(
                camera_id="CCTV-CAM-01",
                frame_index=processed_frames,
                timestamp=simulated_time + timedelta(seconds=processed_frames * (1.0 / target_fps)),
                detection_mode="solid",
                image_width=w,
                image_height=h,
                frame=frame,
                solid_result=res,
            )
            engine.process_camera_result(c_res)
            processed_frames += 1

        frame_idx += 1

    cap.release()
    t1 = time.perf_counter()
    elapsed = t1 - t0
    ai_fps = processed_frames / max(elapsed, 1e-4)

    logger.info("=" * 60)
    logger.info("VIDEO VERIFICATION COMPLETED")
    logger.info("Duration:           %.2f s", duration_sec)
    logger.info("Frames processed:   %d", processed_frames)
    logger.info("Elapsed AI time:    %.2f s (%.1f FPS)", elapsed, ai_fps)
    logger.info("Raw detections:     %d", raw_detections_count)
    logger.info("Incidents created:  %d", len(incidents))
    logger.info("Duplicates blocked: %d", engine.duplicates_suppressed)
    logger.info("=" * 60)

    return {
        "video_path": str(video_path),
        "video_duration_seconds": round(duration_sec, 2),
        "frames_processed": processed_frames,
        "ai_processing_time_seconds": round(elapsed, 2),
        "ai_fps": round(ai_fps, 1),
        "raw_detections": raw_detections_count,
        "unique_incidents": len(incidents),
        "duplicates_suppressed": engine.duplicates_suppressed,
        "incidents": [
            {
                "incident_id": inc.incident_id,
                "category": inc.category,
                "severity": str(inc.severity),
                "confidence": inc.confidence,
            }
            for inc in incidents
        ],
    }


if __name__ == "__main__":
    vid = ROOT_DIR / "storage" / "test_videos" / "cctv_sample.mp4"
    res = test_video(vid, target_fps=5)
    print("Test video summary:", res)
