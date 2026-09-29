"""Temporal validation and persistence verification for solid and liquid waste violations."""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Any

from ai.inference.schemas import (
    SolidDetection,
    LiquidDetection,
    BoundingBox,
    SolidFrameDetectionResult,
    LiquidFrameDetectionResult,
)
from ai.incident.tracker import TrackedSolidObject
from backend.app.core.config import settings

logger = logging.getLogger("temporal_validator")


class SolidTemporalValidator:
    """Validates solid waste tracking persistence against configured frame thresholds."""

    def __init__(
        self,
        min_consecutive_frames: Optional[int] = None,
        min_confidence: Optional[float] = None,
    ) -> None:
        self.min_consecutive_frames = (
            min_consecutive_frames
            if min_consecutive_frames is not None
            else settings.SOLID_MIN_CONSECUTIVE_FRAMES
        )
        self.min_confidence = (
            min_confidence
            if min_confidence is not None
            else settings.SOLID_MIN_CONFIDENCE
        )

    def validate_tracks(
        self, tracks: List[TrackedSolidObject]
    ) -> List[TrackedSolidObject]:
        """Filters active tracks that meet persistence and confidence thresholds.
        
        A track is confirmed once its consecutive frame count reaches min_consecutive_frames
        and its confidence satisfies min_confidence.
        """
        confirmed: List[TrackedSolidObject] = []
        for track in tracks:
            if track.confidence < self.min_confidence:
                continue

            if track.consecutive_frames >= self.min_consecutive_frames:
                track.is_confirmed = True
                confirmed.append(track)

        return confirmed


@dataclass
class TrackedLiquidEvent:
    """Persistent liquid waste accumulation event tracked over time."""

    category: str
    class_id: int
    confidence: float
    affected_area_pixels: int
    affected_area_percent: float
    roi_name: str
    bbox: BoundingBox
    polygon: List[List[float]]
    first_seen: datetime
    last_seen: datetime
    consecutive_frames: int = 1
    total_frames_seen: int = 1
    missed_frames: int = 0
    is_confirmed: bool = False
    incident_created: bool = False

    @property
    def duration_seconds(self) -> float:
        """Wall-clock duration of the liquid event in seconds."""
        delta = (self.last_seen - self.first_seen).total_seconds()
        return max(0.0, round(delta, 2))

    def to_dict(self) -> Dict[str, Any]:
        """Serializes liquid event state."""
        return {
            "category": self.category,
            "class_id": self.class_id,
            "confidence": round(self.confidence, 4),
            "affected_area_pixels": self.affected_area_pixels,
            "affected_area_percent": round(self.affected_area_percent, 2),
            "roi_name": self.roi_name,
            "consecutive_frames": self.consecutive_frames,
            "total_frames_seen": self.total_frames_seen,
            "duration_seconds": self.duration_seconds,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "is_confirmed": self.is_confirmed,
            "incident_created": self.incident_created,
        }


class LiquidTemporalValidator:
    """Validates liquid waste instance segmentation against area and temporal persistence."""

    def __init__(
        self,
        min_confidence: Optional[float] = None,
        min_affected_area_pixels: Optional[int] = None,
        min_affected_area_percent: Optional[float] = None,
        area_check_mode: Optional[str] = None,
        min_consecutive_frames: Optional[int] = None,
        min_duration_seconds: Optional[float] = None,
        grace_frames: int = 3,
    ) -> None:
        self.min_confidence = (
            min_confidence
            if min_confidence is not None
            else settings.LIQUID_MIN_CONFIDENCE
        )
        self.min_affected_area_pixels = (
            min_affected_area_pixels
            if min_affected_area_pixels is not None
            else settings.LIQUID_MIN_AFFECTED_AREA_PIXELS
        )
        self.min_affected_area_percent = (
            min_affected_area_percent
            if min_affected_area_percent is not None
            else settings.LIQUID_MIN_AFFECTED_AREA_PERCENT
        )
        self.area_check_mode = (
            area_check_mode
            if area_check_mode is not None
            else settings.LIQUID_AREA_CHECK_MODE.upper()
        )
        self.min_consecutive_frames = (
            min_consecutive_frames
            if min_consecutive_frames is not None
            else settings.LIQUID_MIN_CONSECUTIVE_FRAMES
        )
        self.min_duration_seconds = (
            min_duration_seconds
            if min_duration_seconds is not None
            else settings.LIQUID_MIN_DURATION_SECONDS
        )
        self.grace_frames = grace_frames

        # Active events indexed by (category, roi_name)
        self._active_events: Dict[Tuple[str, str], TrackedLiquidEvent] = {}

    def reset(self) -> None:
        """Clears all active liquid tracking states."""
        self._active_events.clear()

    def check_area_threshold(self, pixels: int, percent: float) -> bool:
        """Evaluates whether liquid affected area satisfies configured conditions."""
        pix_ok = pixels >= self.min_affected_area_pixels
        pct_ok = percent >= self.min_affected_area_percent

        if self.area_check_mode == "AND":
            return pix_ok and pct_ok
        elif self.area_check_mode == "PIXELS":
            return pix_ok
        elif self.area_check_mode == "PERCENT":
            return pct_ok
        else:  # Default "OR"
            return pix_ok or pct_ok

    def process_frame(
        self,
        liquid_result: LiquidFrameDetectionResult,
        timestamp: Optional[datetime] = None,
        roi_name: str = "global",
    ) -> List[TrackedLiquidEvent]:
        """Updates liquid temporal tracking with detections from current frame.
        
        Args:
            liquid_result: Output from LiquidWasteSegmenter.
            timestamp: Timezone-aware timestamp.
            roi_name: Monitored region name.
            
        Returns:
            List of TrackedLiquidEvent objects that meet persistence requirements in this frame.
        """
        ts = timestamp or liquid_result.timestamp or datetime.now(timezone.utc)
        confirmed_events: List[TrackedLiquidEvent] = []
        seen_keys = set()

        for det in liquid_result.detections:
            # 1. Confidence validation
            if det.confidence < self.min_confidence:
                continue

            # 2. Affected area validation
            if not self.check_area_threshold(det.affected_area_pixels, det.affected_area_percent):
                continue

            key = (det.class_name, roi_name)
            seen_keys.add(key)

            if key in self._active_events:
                event = self._active_events[key]
                event.consecutive_frames += 1
                event.total_frames_seen += 1
                event.missed_frames = 0
                event.last_seen = ts
                event.confidence = max(event.confidence, det.confidence)
                event.affected_area_pixels = det.affected_area_pixels
                event.affected_area_percent = det.affected_area_percent
                event.polygon = det.polygon
                event.bbox = det.bbox
            else:
                event = TrackedLiquidEvent(
                    category=det.class_name,
                    class_id=det.class_id,
                    confidence=det.confidence,
                    affected_area_pixels=det.affected_area_pixels,
                    affected_area_percent=det.affected_area_percent,
                    roi_name=roi_name,
                    bbox=det.bbox,
                    polygon=det.polygon,
                    first_seen=ts,
                    last_seen=ts,
                    consecutive_frames=1,
                    total_frames_seen=1,
                )
                self._active_events[key] = event

            # 3. Temporal persistence validation: consecutive frames and/or wall-clock duration
            frames_ok = event.consecutive_frames >= self.min_consecutive_frames
            duration_ok = event.duration_seconds >= self.min_duration_seconds

            # Persistence is confirmed if consecutive frame threshold is satisfied
            # (or duration requirement if frames are sparse)
            if frames_ok or (event.consecutive_frames >= 2 and duration_ok):
                event.is_confirmed = True
                confirmed_events.append(event)

        # 4. Handle events not observed in current frame (decay / close)
        unseen_keys = [k for k in self._active_events if k not in seen_keys]
        for key in unseen_keys:
            ev = self._active_events[key]
            ev.missed_frames += 1
            ev.consecutive_frames = 0
            if ev.missed_frames > self.grace_frames:
                del self._active_events[key]

        return confirmed_events
