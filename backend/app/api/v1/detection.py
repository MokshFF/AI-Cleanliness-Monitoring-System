"""Detection REST API endpoints for single-image and single-camera prototype integration."""
import io
import logging
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from starlette import status as http_status

from backend.app.core.config import settings
from backend.app.schemas.detection import (
    DetectionItem,
    ImageDetectionResponse,
    VideoProcessResponse,
    CameraTestStatusResponse,
)
from backend.app.schemas.incident import (
    IncidentCreate,
    WasteType,
    IncidentSeverity,
    IncidentStatus,
)
from backend.app.schemas.user import UserResponse
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.api.deps import get_incident_repo, require_operator_or_admin
from backend.app.websocket.manager import get_connection_manager
from backend.app.websocket.alerts import create_incident_created_event
from backend.app.services.prototype_runner import get_prototype_runner
from ai.inference.solid_detector import SolidWasteDetector
from ai.inference.liquid_segmenter import LiquidWasteSegmenter
from ai.incident.severity import SeverityCalculator
from ai.incident.evidence import generate_incident_id

logger = logging.getLogger("api_detection")
router = APIRouter(prefix="/detection", tags=["Detection Prototype"])

# Cached detector instances
_solid_detector: Optional[SolidWasteDetector] = None
_liquid_segmenter: Optional[LiquidWasteSegmenter] = None


def get_solid_detector() -> SolidWasteDetector:
    global _solid_detector
    if _solid_detector is None:
        _solid_detector = SolidWasteDetector()
    return _solid_detector


def get_liquid_segmenter() -> LiquidWasteSegmenter:
    global _liquid_segmenter
    if _liquid_segmenter is None:
        _liquid_segmenter = LiquidWasteSegmenter()
    return _liquid_segmenter


@router.post("/image", response_model=ImageDetectionResponse)
async def detect_image(
    file: UploadFile = File(..., description="Uploaded image file (JPG, PNG, WebP)"),
    camera_id: Optional[str] = Form(None, description="Optional associated camera identifier"),
    location_name: Optional[str] = Form(None, description="Optional physical location name"),
    detection_mode: str = Form("both", description="Detection mode: 'solid', 'liquid', or 'both'"),
    create_incident: bool = Form(True, description="Whether to automatically confirm and persist incidents"),
    current_user: UserResponse = Depends(require_operator_or_admin),
    incident_repo: IncidentRepository = Depends(get_incident_repo),
):
    """Processes an uploaded image through YOLO detection/segmentation.
    
    1. Validates file extension and size
    2. Runs inference via SolidWasteDetector and/or LiquidWasteSegmenter
    3. Produces annotated visualization
    4. Automatically creates and persists cleanliness incident if violations are detected
    5. Dispatches real-time WebSocket alert to React Admin Dashboard
    """
    start_time = time.perf_counter()

    # 1. Validate file extension
    filename = file.filename or "upload.jpg"
    suffix = Path(filename).suffix.lower()
    allowed_suffixes = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    if suffix not in allowed_suffixes:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{suffix}'. Allowed formats: {', '.join(allowed_suffixes)}",
        )

    # 2. Read and validate size (max 10MB)
    contents = await file.read()
    max_size_bytes = 10 * 1024 * 1024
    if len(contents) > max_size_bytes:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size of 10MB (received: {len(contents)/(1024*1024):.2f}MB)",
        )

    # 3. Decode image
    nparr = np.frombuffer(contents, np.uint8)
    mat = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if mat is None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Failed to decode image. Corrupted or invalid image data.",
        )

    now = datetime.now(timezone.utc)
    img_uid = f"IMG-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    cam_id = camera_id or "IMAGE_UPLOAD"
    loc_name = location_name or ("Camera " + cam_id if camera_id else "Manual Inspection Zone")

    detections: List[DetectionItem] = []
    annotated_mat = mat.copy()
    mode = detection_mode.lower()

    # 4. Run Solid Waste Detection
    solid_result = None
    if mode in {"solid", "both"}:
        try:
            s_detector = get_solid_detector()
            solid_result = s_detector.predict_frame(mat)
            if solid_result and solid_result.has_violations:
                annotated_mat = s_detector.annotate_frame(annotated_mat, solid_result)
                for det in solid_result.detections:
                    detections.append(
                        DetectionItem(
                            class_name=det.class_name,
                            waste_type="SOLID",
                            confidence=det.confidence,
                            bbox=[det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2],
                        )
                    )
        except Exception as e:
            logger.error("Error running solid detector: %s", e)

    # 5. Run Liquid Waste Segmentation
    liquid_result = None
    if mode in {"liquid", "both"}:
        try:
            l_segmenter = get_liquid_segmenter()
            res_val = l_segmenter.predict_frame(mat)
            liquid_result = res_val[0] if isinstance(res_val, tuple) else res_val
            if liquid_result and liquid_result.has_violations:
                annotated_mat = l_segmenter.annotate_frame(annotated_mat, liquid_result)
                for ldet in liquid_result.detections:
                    detections.append(
                        DetectionItem(
                            class_name=ldet.category,
                            waste_type="LIQUID",
                            confidence=ldet.confidence,
                            bbox=[ldet.bbox.x1, ldet.bbox.y1, ldet.bbox.x2, ldet.bbox.y2],
                            mask_polygon=ldet.mask_polygon,
                            affected_area_percentage=ldet.affected_area_percentage,
                            affected_area_pixels=ldet.affected_area_pixels,
                        )
                    )
        except Exception as e:
            logger.error("Error running liquid segmenter: %s", e)

    # 6. Save Annotated Image Safely
    annotated_dir = settings.BASE_DIR / "storage" / "annotated"
    annotated_dir.mkdir(parents=True, exist_ok=True)
    ann_filename = f"ANN-{img_uid}.jpg"
    ann_filepath = annotated_dir / ann_filename
    cv2.imwrite(str(ann_filepath), annotated_mat)
    annotated_url = f"/api/v1/detection/annotated/{ann_filename}"

    # 7. Incident Creation & WebSocket Broadcast
    incident_ids: List[str] = []
    if create_incident and len(detections) > 0:
        # Create incident for top violation
        top_det = max(detections, key=lambda d: d.confidence)
        inc_id = generate_incident_id(now)

        if top_det.waste_type == "SOLID":
            sev = SeverityCalculator.calculate_solid_severity(
                category=top_det.class_name,
                confidence=top_det.confidence,
                duration_seconds=0.0,
                cluster_count=len(detections),
            )
        else:
            sev = SeverityCalculator.calculate_liquid_severity(
                category=top_det.class_name,
                confidence=top_det.confidence,
                affected_area_percent=top_det.affected_area_percentage or 5.0,
                duration_seconds=0.0,
            )

        # Save snapshot path
        snapshot_rel_path = f"storage/annotated/{ann_filename}"

        inc_create = IncidentCreate(
            incident_id=inc_id,
            camera_id=cam_id,
            waste_type=WasteType(top_det.waste_type),
            category=top_det.class_name,
            confidence=top_det.confidence,
            severity=sev,
            snapshot_path=snapshot_rel_path,
            timestamp=now,
            status=IncidentStatus.NEW,
            bounding_box=top_det.bbox,
            mask_polygon=top_det.mask_polygon,
            affected_area_percent=top_det.affected_area_percentage,
            affected_area_pixels=top_det.affected_area_pixels,
            metadata={"source": "IMAGE_UPLOAD", "location_name": loc_name},
        )

        try:
            persisted = await incident_repo.create(inc_create.model_dump())
            incident_ids.append(inc_id)

            # Real-time WebSocket dispatch to React Admin Dashboard
            ws_manager = get_connection_manager()
            event = create_incident_created_event(persisted)
            await ws_manager.broadcast(event)
            logger.info("Image upload generated incident %s, broadcasted via WebSocket", inc_id)
        except Exception as e:
            logger.error("Failed persisting image incident %s: %s", inc_id, e)

    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    return ImageDetectionResponse(
        success=True,
        image_id=img_uid,
        camera_id=cam_id,
        location_name=loc_name,
        detections=detections,
        incident_created=len(incident_ids) > 0,
        incident_ids=incident_ids,
        annotated_image_url=annotated_url,
        processing_time_ms=elapsed_ms,
    )


@router.get("/annotated/{filename}")
async def get_annotated_image(
    filename: str,
    current_user: UserResponse = Depends(require_operator_or_admin),
):
    """Securely streams annotated detection images with path traversal protection."""
    annotated_dir = (settings.BASE_DIR / "storage" / "annotated").resolve()
    target_file = (annotated_dir / filename).resolve()

    # Path traversal check
    try:
        target_file.relative_to(annotated_dir)
    except ValueError:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Access denied")

    if not target_file.is_file():
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Annotated image not found")

    return FileResponse(path=str(target_file), media_type="image/jpeg")


@router.post("/video", response_model=VideoProcessResponse)
async def process_video(
    file: Optional[UploadFile] = File(None, description="Uploaded MP4 video file"),
    video_name: Optional[str] = Form(None, description="Or name of pre-loaded sample video (e.g. cctv_sample.mp4)"),
    camera_id: Optional[str] = Form("VIDEO_PROTOTYPE", description="Source camera ID"),
    current_user: UserResponse = Depends(require_operator_or_admin),
    incident_repo: IncidentRepository = Depends(get_incident_repo),
):
    """Processes a local MP4 video file through AI detection at target 5 FPS."""
    start_time = time.perf_counter()
    videos_dir = settings.BASE_DIR / "storage" / "test_videos"

    # Resolve target video path
    if file:
        temp_dir = settings.BASE_DIR / "storage" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        vid_path = temp_dir / f"vid_{uuid.uuid4().hex[:8]}.mp4"
        with open(vid_path, "wb") as out_f:
            shutil.copyfileobj(file.file, out_f)
        resolved_name = file.filename or "uploaded.mp4"
    elif video_name:
        vid_path = (videos_dir / video_name).resolve()
        try:
            vid_path.relative_to(videos_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Access denied")
        if not vid_path.is_file():
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=f"Video '{video_name}' not found")
        resolved_name = video_name
    else:
        # Default fallback
        vid_path = videos_dir / "cctv_sample.mp4"
        if not vid_path.is_file():
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="No video specified or available")
        resolved_name = "cctv_sample.mp4"

    cap = cv2.VideoCapture(str(vid_path))
    if not cap.isOpened():
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="Could not open video file")

    orig_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 100)
    sample_interval = max(1, int(orig_fps / 5.0))  # 5 FPS sampling

    s_detector = get_solid_detector()
    frames_processed = 0
    detections_count = 0
    incident_ids: List[str] = []
    latest_frame = None
    frame_idx = 0
    now = datetime.now(timezone.utc)

    # Process up to 50 sampled frames for responsiveness
    while frame_idx < total_frames and frames_processed < 50:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % sample_interval == 0:
            frames_processed += 1
            res = s_detector.predict_frame(frame, frame_index=frame_idx)
            if res and res.has_violations:
                detections_count += len(res.detections)
                latest_frame = s_detector.annotate_frame(frame, res)

                # Persist incident on persistent detection
                if frames_processed >= 3 and len(incident_ids) == 0:
                    inc_id = generate_incident_id(now)
                    top_d = res.detections[0]
                    ann_dir = settings.BASE_DIR / "storage" / "annotated"
                    ann_dir.mkdir(parents=True, exist_ok=True)
                    snap_name = f"SNAP-{inc_id}.jpg"
                    cv2.imwrite(str(ann_dir / snap_name), latest_frame)

                    inc_doc = IncidentCreate(
                        incident_id=inc_id,
                        camera_id=camera_id,
                        waste_type=WasteType.SOLID,
                        category=top_d.class_name,
                        confidence=top_d.confidence,
                        severity=IncidentSeverity.MEDIUM,
                        snapshot_path=f"storage/annotated/{snap_name}",
                        timestamp=now,
                        status=IncidentStatus.NEW,
                        bounding_box=[top_d.bbox.x1, top_d.bbox.y1, top_d.bbox.x2, top_d.bbox.y2],
                    )
                    created = await incident_repo.create(inc_doc.model_dump())
                    incident_ids.append(inc_id)

                    ws_manager = get_connection_manager()
                    await ws_manager.broadcast(create_incident_created_event(created))

        frame_idx += 1

    cap.release()

    # Save latest annotated frame
    annotated_url = None
    if latest_frame is not None:
        ann_dir = settings.BASE_DIR / "storage" / "annotated"
        ann_dir.mkdir(parents=True, exist_ok=True)
        f_name = f"VID-FRAME-{uuid.uuid4().hex[:8]}.jpg"
        cv2.imwrite(str(ann_dir / f_name), latest_frame)
        annotated_url = f"/api/v1/detection/annotated/{f_name}"

    elapsed = time.perf_counter() - start_time
    proc_fps = round(frames_processed / elapsed, 1) if elapsed > 0 else 5.0

    return VideoProcessResponse(
        success=True,
        video_name=resolved_name,
        camera_id=camera_id,
        frames_processed=frames_processed,
        detections_count=detections_count,
        incident_created=len(incident_ids) > 0,
        incident_ids=incident_ids,
        processing_fps=proc_fps,
        duration_seconds=round(elapsed, 2),
        annotated_frame_url=annotated_url,
    )


# -----------------------------------------------------------------------------
# Single Camera / RTSP Prototype Runner Controls
# -----------------------------------------------------------------------------

@router.post("/camera-test/start")
async def start_camera_test(
    camera_id: Optional[str] = Form(None),
    camera_name: Optional[str] = Form(None),
    stream_source: Optional[str] = Form(None, description="Optional RTSP stream or local MP4 path"),
    current_user: UserResponse = Depends(require_operator_or_admin),
):
    """Starts the single prototype camera stream runner."""
    runner = get_prototype_runner()
    success = runner.start_camera(
        camera_id=camera_id,
        camera_name=camera_name,
        stream_source=stream_source,
    )
    return {"status": "started" if success else "failed", "camera_id": runner.camera_id}


@router.post("/camera-test/stop")
async def stop_camera_test(
    current_user: UserResponse = Depends(require_operator_or_admin),
):
    """Stops the prototype camera stream runner."""
    runner = get_prototype_runner()
    runner.stop_camera()
    return {"status": "stopped"}


@router.get("/camera-test/status", response_model=CameraTestStatusResponse)
async def get_camera_test_status(
    current_user: UserResponse = Depends(require_operator_or_admin),
):
    """Returns telemetry and detection metrics for the single-camera prototype."""
    runner = get_prototype_runner()
    return runner.get_status()


@router.get("/camera-test/frame")
async def get_camera_test_frame(
    current_user: UserResponse = Depends(require_operator_or_admin),
):
    """Streams the latest processed frame from the prototype camera runner."""
    runner = get_prototype_runner()
    frame_jpeg = runner.get_latest_frame_jpeg()
    if frame_jpeg is None:
        # Generate placeholder frame
        img = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.putText(img, "Awaiting Camera Feed...", (160, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
        ret, buf = cv2.imencode(".jpg", img)
        frame_jpeg = buf.tobytes()

    return Response(content=frame_jpeg, media_type="image/jpeg")
