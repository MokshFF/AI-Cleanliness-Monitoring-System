"""Solid Waste Object Detection Inference Pipeline.

Supports:
- Single image inference (file path or numpy array)
- Image directory batch inference
- Local video stream inference with optional annotated video output
- Structured typed results adhering to ai.inference.schemas
- Drawing annotations on image/frame
"""
import logging
import sys
import time
from pathlib import Path
from typing import List, Union, Optional, Dict, Any, Generator, Tuple

# Ensure project root is in sys.path for direct CLI script execution
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import cv2
import numpy as np
from ultralytics import YOLO

from ai.configs import get_solid_classes
from ai.inference.schemas import BoundingBox, SolidDetection, SolidFrameDetectionResult
from backend.app.core.config import settings

logger = logging.getLogger("solid_detector")

# Color palette for solid waste classes (BGR for OpenCV)
CLASS_COLORS = {
    0: (0, 165, 255),   # plastic_bottle: orange
    1: (255, 0, 0),     # plastic_bag: blue
    2: (0, 255, 255),   # paper: yellow
    3: (0, 255, 0),     # can: green
    4: (0, 0, 255),     # food_waste: red
    5: (128, 0, 128),   # garbage_pile: purple
}


class SolidWasteDetector:
    """Production inference wrapper for Solid Waste YOLO detection."""

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        confidence_threshold: Optional[float] = None,
        device: str = "auto",
    ) -> None:
        self.classes = get_solid_classes()
        self.confidence_threshold = (
            confidence_threshold if confidence_threshold is not None else settings.SOLID_CONFIDENCE_THRESHOLD
        )
        resolved_model_path = model_path or settings.SOLID_MODEL_PATH
        self.model_path = Path(resolved_model_path)

        # Fallback to yolov8n base if weights do not exist yet (pre-training / smoke state)
        if not self.model_path.is_file():
            fallback = Path("models/solid/best.pt")
            if fallback.is_file():
                self.model_path = fallback
            else:
                logger.warning(
                    "Trained weights not found at %s. Loading base yolov8n.pt for pipeline execution.",
                    self.model_path,
                )
                self.model_path = "yolov8n.pt"

        from ai.training.train_solid import resolve_device
        self.device = resolve_device(device)
        self.model = YOLO(str(self.model_path))
        logger.info(
            "SolidWasteDetector initialized with model: %s on device: %s (conf: %.2f)",
            self.model_path,
            self.device,
            self.confidence_threshold,
        )

    def predict_frame(
        self,
        frame: np.ndarray,
        frame_index: Optional[int] = None,
    ) -> SolidFrameDetectionResult:
        """Runs detection on a single RGB/BGR numpy array and returns structured result."""
        start_time = time.perf_counter()
        h, w = frame.shape[:2]

        results = self.model.predict(
            source=frame,
            conf=self.confidence_threshold,
            device=self.device,
            verbose=False,
        )

        detections: List[SolidDetection] = []
        if results and len(results) > 0:
            boxes = results[0].boxes
            for box in boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                xyxy = box.xyxy[0].tolist()

                # Map class ID safely to solid taxonomy
                class_name = self.classes[cls_id] if cls_id < len(self.classes) else f"class_{cls_id}"

                x1, y1, x2, y2 = xyxy
                norm_bbox = BoundingBox(
                    x1=max(0.0, min(1.0, x1 / w)),
                    y1=max(0.0, min(1.0, y1 / h)),
                    x2=max(0.0, min(1.0, x2 / w)),
                    y2=max(0.0, min(1.0, y2 / h)),
                )

                detections.append(
                    SolidDetection(
                        class_id=cls_id,
                        class_name=class_name,
                        confidence=round(conf, 4),
                        bbox=BoundingBox(
                            x1=round(x1, 2),
                            y1=round(y1, 2),
                            x2=round(x2, 2),
                            y2=round(y2, 2),
                        ),
                        normalized_bbox=norm_bbox,
                    )
                )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return SolidFrameDetectionResult(
            frame_index=frame_index,
            image_width=w,
            image_height=h,
            detections=detections,
            processing_time_ms=round(elapsed_ms, 2),
        )

    def detect_image(
        self, image_path: Union[str, Path]
    ) -> Tuple[SolidFrameDetectionResult, np.ndarray]:
        """Detects solid waste in an image file on disk.
        
        Returns:
            (structured_result, annotated_image_bgr)
        """
        img_p = Path(image_path)
        if not img_p.is_file():
            raise FileNotFoundError(f"Image not found at: {img_p}")

        mat = cv2.imread(str(img_p))
        if mat is None:
            raise ValueError(f"Could not decode image at: {img_p}")

        result = self.predict_frame(mat)
        annotated = self.annotate_frame(mat, result)
        return result, annotated

    def detect_directory(
        self, directory_path: Union[str, Path]
    ) -> List[Dict[str, Any]]:
        """Processes all supported images in a directory."""
        dir_p = Path(directory_path)
        if not dir_p.is_dir():
            raise NotADirectoryError(f"Directory not found: {dir_p}")

        supported = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        image_files = [p for p in dir_p.iterdir() if p.suffix.lower() in supported]

        results = []
        for img_file in image_files:
            res, _ = self.detect_image(img_file)
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
    ) -> List[SolidFrameDetectionResult]:
        """Runs inference on a local video file.
        
        Args:
            video_path: Path to video file
            output_path: Optional destination to save annotated MP4 video
            sample_rate: Process 1 frame every sample_rate frames
            max_frames: Optional cap on total frames processed
            
        Returns:
            List of SolidFrameDetectionResult
        """
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

        frame_results: List[SolidFrameDetectionResult] = []
        frame_idx = 0
        processed_count = 0

        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % sample_rate == 0:
                    res = self.predict_frame(frame, frame_index=frame_idx)
                    frame_results.append(res)
                    processed_count += 1

                    if writer is not None:
                        annotated = self.annotate_frame(frame, res)
                        writer.write(annotated)

                    if max_frames and processed_count >= max_frames:
                        break

                frame_idx += 1
        finally:
            cap.release()
            if writer is not None:
                writer.release()

        logger.info(
            "Video inference finished: %d frames sampled from %s",
            len(frame_results),
            vid_p.name,
        )
        return frame_results

    def annotate_frame(
        self, frame: np.ndarray, result: SolidFrameDetectionResult
    ) -> np.ndarray:
        """Draws bounding boxes, category tags, and confidence scores onto frame."""
        annotated = frame.copy()
        for det in result.detections:
            color = CLASS_COLORS.get(det.class_id, (0, 255, 0))
            x1 = int(det.bbox.x1)
            y1 = int(det.bbox.y1)
            x2 = int(det.bbox.x2)
            y2 = int(det.bbox.y2)

            # Draw rectangle
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            # Draw label banner
            label_text = f"{det.class_name} {det.confidence:.2f}"
            (tw, th), baseline = cv2.getTextSize(
                label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            banner_y1 = max(0, y1 - th - baseline - 4)
            cv2.rectangle(
                annotated,
                (x1, banner_y1),
                (x1 + tw + 6, banner_y1 + th + baseline + 4),
                color,
                -1,
            )
            cv2.putText(
                annotated,
                label_text,
                (x1 + 3, banner_y1 + th + 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        return annotated
