"""Liquid Waste Instance Segmentation and Affected-Area Inference Engine.

Supports:
- Single image inference (file path or numpy array)
- Image directory batch inference
- Local video stream inference with configurable frame sampling
- Precise affected-area pixel counting and percentage calculation
- Configurable Region of Interest (ROI) support
- Structured typed results adhering to ai.inference.schemas.LiquidFrameDetectionResult
- Mask overlay annotation with category, confidence, and area percentage
"""
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Union, Optional, Dict, Any, Tuple
import cv2
import numpy as np
from ultralytics import YOLO

# Ensure project root is in sys.path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from ai.configs import get_liquid_classes
from ai.inference.schemas import (
    BoundingBox,
    RegionOfInterest,
    LiquidDetection,
    LiquidFrameDetectionResult,
)
from backend.app.core.config import settings

logger = logging.getLogger("liquid_segmenter")

# Liquid class color palette (BGR) for visualization
LIQUID_COLORS = {
    0: (255, 140, 0),    # liquid_spill: deep cyan/sky-blue
    1: (0, 0, 180),      # sewage_overflow: dark crimson
    2: (255, 200, 0),    # waterlogging: bright cyan
    3: (0, 140, 255),    # drain_overflow: vibrant orange
}


def build_roi_mask(
    image_shape: Tuple[int, int],
    roi: Optional[RegionOfInterest] = None,
) -> Tuple[np.ndarray, int, str]:
    """Builds a binary mask for the monitored region of interest (ROI).
    
    Returns:
        (roi_binary_mask, monitored_pixel_count, roi_name)
    """
    h, w = image_shape[:2]
    if roi is None or (roi.polygon is None and roi.bbox is None):
        # Default: Entire frame is monitored
        mask = np.ones((h, w), dtype=np.uint8)
        return mask, h * w, "full_frame"

    mask = np.zeros((h, w), dtype=np.uint8)
    roi_name = roi.name or "custom_roi"

    if roi.polygon:
        pts = np.array(roi.polygon, dtype=np.int32)
        cv2.fillPoly(mask, [pts], 1)
    elif roi.bbox:
        x1 = max(0, int(roi.bbox.x1))
        y1 = max(0, int(roi.bbox.y1))
        x2 = min(w, int(roi.bbox.x2))
        y2 = min(h, int(roi.bbox.y2))
        mask[y1:y2, x1:x2] = 1

    pixel_count = int(np.count_nonzero(mask))
    if pixel_count == 0:
        # Fallback to avoid division by zero if empty ROI passed
        mask = np.ones((h, w), dtype=np.uint8)
        pixel_count = h * w
        roi_name = "full_frame_fallback"

    return mask, pixel_count, roi_name


class LiquidWasteSegmenter:
    """Production inference wrapper for Liquid Waste YOLO instance segmentation."""

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        confidence_threshold: Optional[float] = None,
        device: str = "auto",
        roi: Optional[RegionOfInterest] = None,
    ) -> None:
        self.classes = get_liquid_classes()
        self.confidence_threshold = (
            confidence_threshold if confidence_threshold is not None else settings.LIQUID_CONFIDENCE_THRESHOLD
        )
        resolved_model_path = model_path or settings.LIQUID_MODEL_PATH
        self.model_path = Path(resolved_model_path)

        # Fallback to yolov8n-seg.pt if weights do not exist yet
        if not self.model_path.is_file():
            fallback = Path("models/liquid/best.pt")
            if fallback.is_file():
                self.model_path = fallback
            else:
                logger.warning(
                    "Trained liquid weights not found at %s. Loading base yolov8n-seg.pt.",
                    self.model_path,
                )
                self.model_path = "yolov8n-seg.pt"

        from ai.training.train_solid import resolve_device
        self.device = resolve_device(device)
        self.model = YOLO(str(self.model_path))
        self.default_roi = roi

        logger.info(
            "LiquidWasteSegmenter initialized with model: %s on device: %s (conf: %.2f)",
            self.model_path,
            self.device,
            self.confidence_threshold,
        )

    def set_roi(self, roi: Optional[RegionOfInterest]) -> None:
        """Dynamically updates the monitored region of interest."""
        self.default_roi = roi

    def predict_frame(
        self,
        frame: np.ndarray,
        frame_index: Optional[int] = None,
        roi: Optional[RegionOfInterest] = None,
    ) -> Tuple[LiquidFrameDetectionResult, np.ndarray]:
        """Runs instance segmentation on a single image/frame and computes affected liquid area.
        
        Returns:
            (structured_result, combined_binary_liquid_mask)
        """
        start_time = time.perf_counter()
        h, w = frame.shape[:2]

        active_roi = roi or self.default_roi
        roi_mask, monitored_pixels, roi_name = build_roi_mask((h, w), active_roi)

        results = self.model.predict(
            source=frame,
            conf=self.confidence_threshold,
            device=self.device,
            verbose=False,
        )

        detections: List[LiquidDetection] = []
        combined_liquid_mask = np.zeros((h, w), dtype=np.uint8)

        if results and len(results) > 0 and results[0].masks is not None:
            boxes = results[0].boxes
            masks = results[0].masks

            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                conf = float(boxes.conf[i].item())
                xyxy = boxes.xyxy[i].tolist()
                class_name = self.classes[cls_id] if cls_id < len(self.classes) else f"liquid_{cls_id}"

                # Extract contour polygon points
                polygon_coords: List[List[float]] = []
                norm_polygon_coords: List[List[float]] = []
                if i < len(masks.xy):
                    poly_arr = masks.xy[i]
                    polygon_coords = [[round(float(pt[0]), 2), round(float(pt[1]), 2)] for pt in poly_arr]
                    norm_polygon_coords = [
                        [round(float(pt[0]) / w, 5), round(float(pt[1]) / h, 5)] for pt in poly_arr
                    ]

                # Convert instance mask to image scale binary mask
                inst_mask = np.zeros((h, w), dtype=np.uint8)
                if len(polygon_coords) >= 3:
                    pts = np.array(polygon_coords, dtype=np.int32)
                    cv2.fillPoly(inst_mask, [pts], 1)
                elif masks.data is not None and i < len(masks.data):
                    raw_m = masks.data[i].cpu().numpy().astype(np.uint8)
                    inst_mask = cv2.resize(raw_m, (w, h), interpolation=cv2.INTER_NEAREST)

                # Intersect with Monitored Region of Interest (ROI)
                effective_liquid_mask = cv2.bitwise_and(inst_mask, roi_mask)
                instance_liquid_pixels = int(np.count_nonzero(effective_liquid_mask))

                # Affected area percentage
                area_percent = round((instance_liquid_pixels / monitored_pixels) * 100.0, 3)

                # Accumulate combined mask
                combined_liquid_mask = cv2.bitwise_or(combined_liquid_mask, effective_liquid_mask)

                x1, y1, x2, y2 = xyxy
                enclosing_box = BoundingBox(
                    x1=round(x1, 2),
                    y1=round(y1, 2),
                    x2=round(x2, 2),
                    y2=round(y2, 2),
                )

                detections.append(
                    LiquidDetection(
                        class_id=cls_id,
                        class_name=class_name,
                        confidence=round(conf, 4),
                        bbox=enclosing_box,
                        polygon=polygon_coords,
                        normalized_polygon=norm_polygon_coords,
                        affected_area_pixels=instance_liquid_pixels,
                        affected_area_percent=area_percent,
                        monitored_region_pixels=monitored_pixels,
                    )
                )

        total_affected_pixels = int(np.count_nonzero(combined_liquid_mask))
        total_percent = round((total_affected_pixels / monitored_pixels) * 100.0, 3)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        frame_result = LiquidFrameDetectionResult(
            frame_index=frame_index,
            image_width=w,
            image_height=h,
            monitored_region_name=roi_name,
            monitored_region_pixels=monitored_pixels,
            total_affected_liquid_pixels=total_affected_pixels,
            total_affected_area_percent=total_percent,
            detections=detections,
            processing_time_ms=round(elapsed_ms, 2),
        )

        return frame_result, combined_liquid_mask

    def detect_image(
        self,
        image_path: Union[str, Path],
        roi: Optional[RegionOfInterest] = None,
    ) -> Tuple[LiquidFrameDetectionResult, np.ndarray]:
        """Runs segmentation on an image from disk and returns structured result and visualization."""
        img_p = Path(image_path)
        if not img_p.is_file():
            raise FileNotFoundError(f"Image not found at: {img_p}")

        mat = cv2.imread(str(img_p))
        if mat is None:
            raise ValueError(f"Could not decode image at: {img_p}")

        result, _ = self.predict_frame(mat, roi=roi)
        annotated = self.annotate_frame(mat, result, roi=roi)
        return result, annotated

    def detect_directory(
        self,
        directory_path: Union[str, Path],
        roi: Optional[RegionOfInterest] = None,
    ) -> List[Dict[str, Any]]:
        """Processes all supported images in a directory."""
        dir_p = Path(directory_path)
        if not dir_p.is_dir():
            raise NotADirectoryError(f"Directory not found: {dir_p}")

        supported = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        image_files = [p for p in dir_p.iterdir() if p.suffix.lower() in supported]

        results = []
        for img_file in image_files:
            res, _ = self.detect_image(img_file, roi=roi)
            results.append({
                "image_path": str(img_file),
                "image_name": img_file.name,
                "result": res.model_dump(),
            })
        return results

    def detect_video(
        self,
        video_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        sample_rate: int = 1,
        max_frames: Optional[int] = None,
        roi: Optional[RegionOfInterest] = None,
    ) -> List[LiquidFrameDetectionResult]:
        """Runs segmentation inference on a local video file."""
        vid_p = Path(video_path)
        if not vid_p.is_file():
            raise FileNotFoundError(f"Video file not found at: {vid_p}")

        cap = cv2.VideoCapture(str(vid_p))
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video at: {vid_p}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        writer: Optional[cv2.VideoWriter] = None
        if output_path:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(out_p), fourcc, fps / sample_rate, (w, h))

        frame_results: List[LiquidFrameDetectionResult] = []
        frame_idx = 0
        processed_count = 0

        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % sample_rate == 0:
                    res, _ = self.predict_frame(frame, frame_index=frame_idx, roi=roi)
                    frame_results.append(res)
                    processed_count += 1

                    if writer is not None:
                        annotated = self.annotate_frame(frame, res, roi=roi)
                        writer.write(annotated)

                    if max_frames and processed_count >= max_frames:
                        break

                frame_idx += 1
        finally:
            cap.release()
            if writer is not None:
                writer.release()

        logger.info(
            "Liquid video inference finished: %d frames sampled from %s",
            len(frame_results),
            vid_p.name,
        )
        return frame_results

    def annotate_frame(
        self,
        frame: np.ndarray,
        result: LiquidFrameDetectionResult,
        roi: Optional[RegionOfInterest] = None,
    ) -> np.ndarray:
        """Visualizes liquid segmentation polygons, mask blends, and ROI boundaries on frame."""
        annotated = frame.copy()
        h, w = frame.shape[:2]

        # Draw ROI boundary if active
        active_roi = roi or self.default_roi
        if active_roi and (active_roi.polygon or active_roi.bbox):
            if active_roi.polygon:
                pts = np.array(active_roi.polygon, dtype=np.int32)
                cv2.polylines(annotated, [pts], isClosed=True, color=(255, 255, 0), thickness=2)
            elif active_roi.bbox:
                bx = active_roi.bbox
                cv2.rectangle(
                    annotated,
                    (int(bx.x1), int(bx.y1)),
                    (int(bx.x2), int(bx.y2)),
                    (255, 255, 0),
                    2,
                )
            cv2.putText(
                annotated,
                f"ROI: {active_roi.name}",
                (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 0),
                1,
            )

        # Draw liquid instances
        for det in result.detections:
            color = LIQUID_COLORS.get(det.class_id, (0, 165, 255))
            if det.polygon and len(det.polygon) >= 3:
                pts = np.array(det.polygon, dtype=np.int32)
                # Fill mask overlay
                overlay = annotated.copy()
                cv2.fillPoly(overlay, [pts], color)
                cv2.addWeighted(overlay, 0.40, annotated, 0.60, 0, annotated)
                # Draw sharp contour boundary
                cv2.polylines(annotated, [pts], isClosed=True, color=color, thickness=2)

            # Label banner
            bx = det.bbox
            label = f"{det.class_name} ({det.confidence:.2f}) | Area: {det.affected_area_percent:.1f}%"
            (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            y_banner = max(0, int(bx.y1) - th - baseline - 4)
            cv2.rectangle(
                annotated,
                (int(bx.x1), y_banner),
                (int(bx.x1) + tw + 6, y_banner + th + baseline + 4),
                color,
                -1,
            )
            cv2.putText(
                annotated,
                label,
                (int(bx.x1) + 3, y_banner + th + 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        # Top summary bar
        summary_text = (
            f"Liquid Area: {result.total_affected_area_percent:.2f}% "
            f"({result.total_affected_liquid_pixels:,} px / {result.monitored_region_pixels:,} px)"
        )
        cv2.putText(
            annotated,
            summary_text,
            (20, h - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255) if result.has_violations else (0, 255, 0),
            2,
        )

        return annotated
