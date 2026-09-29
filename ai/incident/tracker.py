"""Solid Waste Object Tracker implementing ByteTrack-style two-stage IoU association."""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional, Any
import numpy as np

from ai.inference.schemas import SolidDetection, BoundingBox
from backend.app.core.config import settings

logger = logging.getLogger("incident_tracker")


def compute_iou(box1: BoundingBox, box2: BoundingBox) -> float:
    """Computes Intersection over Union (IoU) between two bounding boxes."""
    x_left = max(box1.x1, box2.x1)
    y_top = max(box1.y1, box2.y1)
    x_right = min(box1.x2, box2.x2)
    y_bottom = min(box1.y2, box2.y2)

    inter_width = max(0.0, x_right - x_left)
    inter_height = max(0.0, y_bottom - y_top)
    inter_area = inter_width * inter_height

    if inter_area <= 0.0:
        return 0.0

    union_area = box1.area + box2.area - inter_area
    if union_area <= 0.0:
        return 0.0

    return inter_area / union_area


@dataclass
class TrackedSolidObject:
    """A tracked solid waste object across consecutive video frames."""

    track_id: int
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
    first_seen: datetime
    last_seen: datetime
    consecutive_frames: int = 1
    total_frames_seen: int = 1
    lost_frames: int = 0
    state: str = "ACTIVE"  # "ACTIVE", "LOST", "REMOVED"
    is_confirmed: bool = False
    incident_created: bool = False

    @property
    def last_position(self) -> Tuple[float, float]:
        """Centroid (cx, cy) of the current bounding box."""
        cx = (self.bbox.x1 + self.bbox.x2) / 2.0
        cy = (self.bbox.y1 + self.bbox.y2) / 2.0
        return (round(cx, 1), round(cy, 1))

    @property
    def duration_seconds(self) -> float:
        """Total duration this object has been actively tracked in seconds."""
        delta = (self.last_seen - self.first_seen).total_seconds()
        return max(0.0, round(delta, 2))

    def to_dict(self) -> Dict[str, Any]:
        """Serializes tracking state for logging and API telemetry."""
        return {
            "track_id": self.track_id,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bounding_box": {
                "x1": self.bbox.x1,
                "y1": self.bbox.y1,
                "x2": self.bbox.x2,
                "y2": self.bbox.y2,
            },
            "last_position": self.last_position,
            "consecutive_frames": self.consecutive_frames,
            "total_frames_seen": self.total_frames_seen,
            "lost_frames": self.lost_frames,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "duration_seconds": self.duration_seconds,
            "state": self.state,
            "is_confirmed": self.is_confirmed,
            "incident_created": self.incident_created,
        }


class SolidWasteTracker:
    """Multi-object tracker for solid waste detections.
    
    Operates using two-stage IoU matching:
    1. Matches existing active tracks with high-confidence detections.
    2. Matches remaining/lost tracks with secondary detections to handle occlusion.
    Tracks are preserved during a configurable grace period (`grace_frames`) before closing.
    """

    def __init__(
        self,
        min_confidence: Optional[float] = None,
        grace_frames: Optional[int] = None,
        iou_threshold: Optional[float] = None,
    ) -> None:
        self.min_confidence = min_confidence if min_confidence is not None else settings.SOLID_MIN_CONFIDENCE
        self.grace_frames = grace_frames if grace_frames is not None else settings.SOLID_TRACK_GRACE_FRAMES
        self.iou_threshold = iou_threshold if iou_threshold is not None else settings.SOLID_TRACK_IOU_THRESHOLD

        self._next_track_id: int = 1
        self._tracks: Dict[int, TrackedSolidObject] = {}

    @property
    def active_tracks(self) -> List[TrackedSolidObject]:
        """Returns all currently active (non-removed) tracks."""
        return [t for t in self._tracks.values() if t.state == "ACTIVE"]

    @property
    def all_tracks(self) -> List[TrackedSolidObject]:
        """Returns all tracked objects including lost ones within grace period."""
        return [t for t in self._tracks.values() if t.state != "REMOVED"]

    def reset(self) -> None:
        """Clears all tracking state."""
        self._tracks.clear()
        self._next_track_id = 1

    def update(
        self,
        detections: List[SolidDetection],
        timestamp: Optional[datetime] = None,
        frame_index: Optional[int] = None,
    ) -> List[TrackedSolidObject]:
        """Updates tracks with detections from the current frame.
        
        Args:
            detections: List of SolidDetection objects from SolidWasteDetector.
            timestamp: Timezone-aware timestamp of the current frame.
            frame_index: Optional sequential frame number.
            
        Returns:
            List of TrackedSolidObject instances active in this frame.
        """
        ts = timestamp or datetime.now(timezone.utc)

        # 1. Partition detections into high-confidence and secondary
        high_dets = [d for d in detections if d.confidence >= self.min_confidence]
        low_dets = [d for d in detections if 0.20 <= d.confidence < self.min_confidence]

        # Candidate tracks: active and lost tracks within grace period
        candidate_track_ids = [
            tid for tid, t in self._tracks.items() if t.state in {"ACTIVE", "LOST"}
        ]

        # 2. Stage 1: Match existing candidate tracks with high-confidence detections
        matched_pairs, unmatched_track_ids, unmatched_high_dets = self._associate(
            candidate_track_ids, high_dets
        )

        for tid, det in matched_pairs:
            track = self._tracks[tid]
            track.bbox = det.bbox
            track.confidence = det.confidence
            track.class_id = det.class_id
            track.class_name = det.class_name
            track.consecutive_frames += 1
            track.total_frames_seen += 1
            track.lost_frames = 0
            track.last_seen = ts
            track.state = "ACTIVE"

        # 3. Stage 2: Match remaining unmatched tracks with secondary low-confidence detections
        if unmatched_track_ids and low_dets:
            matched_stage2, remaining_unmatched_tids, _ = self._associate(
                unmatched_track_ids, low_dets
            )
            for tid, det in matched_stage2:
                track = self._tracks[tid]
                track.bbox = det.bbox
                track.confidence = det.confidence
                track.consecutive_frames += 1
                track.total_frames_seen += 1
                track.lost_frames = 0
                track.last_seen = ts
                track.state = "ACTIVE"
            unmatched_track_ids = remaining_unmatched_tids

        # 4. Handle unmatched tracks (increment lost_frames or close if past grace period)
        for tid in unmatched_track_ids:
            track = self._tracks[tid]
            track.consecutive_frames = 0
            track.lost_frames += 1
            if track.lost_frames > self.grace_frames:
                track.state = "REMOVED"
                logger.debug("Track %d closed after exceeding %d grace frames", tid, self.grace_frames)
            else:
                track.state = "LOST"

        # 5. Initialize new tracks for unmatched high-confidence detections
        for det in unmatched_high_dets:
            new_tid = self._next_track_id
            self._next_track_id += 1

            new_track = TrackedSolidObject(
                track_id=new_tid,
                class_id=det.class_id,
                class_name=det.class_name,
                confidence=det.confidence,
                bbox=det.bbox,
                first_seen=ts,
                last_seen=ts,
                consecutive_frames=1,
                total_frames_seen=1,
                lost_frames=0,
                state="ACTIVE",
            )
            self._tracks[new_tid] = new_track
            logger.debug("New solid waste track %d created: %s (conf: %.2f)", new_tid, det.class_name, det.confidence)

        # 6. Purge removed tracks from memory to keep footprint bounded
        self._tracks = {tid: t for tid, t in self._tracks.items() if t.state != "REMOVED"}

        return [t for t in self._tracks.values() if t.state == "ACTIVE"]

    def _associate(
        self, track_ids: List[int], detections: List[SolidDetection]
    ) -> Tuple[List[Tuple[int, SolidDetection]], List[int], List[SolidDetection]]:
        """Greedy IoU association between track bounding boxes and detections."""
        if not track_ids or not detections:
            return [], track_ids, detections

        # Compute IoU matrix
        iou_matrix = np.zeros((len(track_ids), len(detections)), dtype=np.float32)
        for i, tid in enumerate(track_ids):
            t_box = self._tracks[tid].bbox
            for j, det in enumerate(detections):
                iou_matrix[i, j] = compute_iou(t_box, det.bbox)

        matched_pairs: List[Tuple[int, SolidDetection]] = []
        matched_tracks = set()
        matched_dets = set()

        # Greedy matching by maximum IoU
        while True:
            max_iou = 0.0
            best_i, best_j = -1, -1

            for i in range(len(track_ids)):
                if i in matched_tracks:
                    continue
                for j in range(len(detections)):
                    if j in matched_dets:
                        continue
                    if iou_matrix[i, j] > max_iou:
                        max_iou = iou_matrix[i, j]
                        best_i, best_j = i, j

            if max_iou < self.iou_threshold or best_i == -1:
                break

            matched_tracks.add(best_i)
            matched_dets.add(best_j)
            matched_pairs.append((track_ids[best_i], detections[best_j]))

        unmatched_track_ids = [
            track_ids[i] for i in range(len(track_ids)) if i not in matched_tracks
        ]
        unmatched_detections = [
            detections[j] for j in range(len(detections)) if j not in matched_dets
        ]

        return matched_pairs, unmatched_track_ids, unmatched_detections
