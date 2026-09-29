"""AI Frame Router dispatching camera frames to Solid and/or Liquid AI pipelines."""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
import numpy as np

from ai.inference.solid_detector import SolidWasteDetector
from ai.inference.liquid_segmenter import LiquidWasteSegmenter
from ai.inference.schemas import (
    SolidFrameDetectionResult,
    LiquidFrameDetectionResult,
    RegionOfInterest,
)

logger = logging.getLogger("ai_router")


@dataclass
class CameraFrameAIResult:
    """Consolidated inference result emitted for a single camera frame."""

    camera_id: str
    frame_index: int
    timestamp: datetime
    detection_mode: str
    image_width: int
    image_height: int
    frame: np.ndarray  # Raw evidence frame preserved for Phase 5 snapshot generation
    solid_result: Optional[SolidFrameDetectionResult] = None
    liquid_result: Optional[LiquidFrameDetectionResult] = None
    processing_time_ms: float = 0.0

    @property
    def has_violations(self) -> bool:
        solid_violation = self.solid_result is not None and self.solid_result.has_violations
        liquid_violation = self.liquid_result is not None and self.liquid_result.has_violations
        return solid_violation or liquid_violation

    @property
    def solid_count(self) -> int:
        return self.solid_result.count if self.solid_result else 0

    @property
    def liquid_count(self) -> int:
        return self.liquid_result.count if self.liquid_result else 0

    def summary(self) -> str:
        s_count = self.solid_count
        l_count = self.liquid_count
        l_area = f"{self.liquid_result.total_affected_area_percent:.1f}%" if self.liquid_result else "0%"
        return f"[{self.camera_id} Frame {self.frame_index}] Solid: {s_count} items | Liquid: {l_count} spills ({l_area})"


class AIRouter:
    """Routes camera frames to appropriate AI detection/segmentation engines based on camera mode."""

    def __init__(
        self,
        solid_detector: Optional[SolidWasteDetector] = None,
        liquid_segmenter: Optional[LiquidWasteSegmenter] = None,
    ) -> None:
        self.solid_detector = solid_detector
        self.liquid_segmenter = liquid_segmenter

    def _ensure_solid(self) -> SolidWasteDetector:
        if self.solid_detector is None:
            self.solid_detector = SolidWasteDetector()
        return self.solid_detector

    def _ensure_liquid(self) -> LiquidWasteSegmenter:
        if self.liquid_segmenter is None:
            self.liquid_segmenter = LiquidWasteSegmenter()
        return self.liquid_segmenter

    def process_frame(
        self,
        camera_id: str,
        frame: np.ndarray,
        frame_index: int,
        timestamp: Optional[datetime] = None,
        detection_mode: str = "BOTH",
        roi: Optional[RegionOfInterest] = None,
    ) -> CameraFrameAIResult:
        """Dispatches frame to AI models according to detection_mode (SOLID, LIQUID, or BOTH)."""
        start_time = time.perf_counter()
        ts = timestamp or datetime.now(timezone.utc)
        h, w = frame.shape[:2]

        mode = detection_mode.upper().strip()
        solid_res: Optional[SolidFrameDetectionResult] = None
        liquid_res: Optional[LiquidFrameDetectionResult] = None

        if mode in {"SOLID", "BOTH"}:
            try:
                detector = self._ensure_solid()
                solid_res = detector.predict_frame(frame, frame_index=frame_index)
            except Exception as e:
                logger.error("[%s] Error running solid detection: %s", camera_id, e)

        if mode in {"LIQUID", "BOTH"}:
            try:
                segmenter = self._ensure_liquid()
                liquid_res, _ = segmenter.predict_frame(frame, frame_index=frame_index, roi=roi)
            except Exception as e:
                logger.error("[%s] Error running liquid segmentation: %s", camera_id, e)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return CameraFrameAIResult(
            camera_id=camera_id,
            frame_index=frame_index,
            timestamp=ts,
            detection_mode=mode,
            image_width=w,
            image_height=h,
            frame=frame,
            solid_result=solid_res,
            liquid_result=liquid_res,
            processing_time_ms=round(elapsed_ms, 2),
        )
