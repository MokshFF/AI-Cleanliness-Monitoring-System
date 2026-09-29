"""Incident ID generation and annotated evidence snapshot management."""
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Tuple
import cv2
import numpy as np

from ai.inference.schemas import BoundingBox
from backend.app.core.config import settings
from backend.app.schemas.incident import IncidentSeverity

logger = logging.getLogger("incident_evidence")


# Global atomic sequence counter for incident IDs
_id_lock = threading.Lock()
_daily_counter = 0
_last_counter_date = ""


def generate_incident_id(timestamp: Optional[datetime] = None) -> str:
    """Generates a unique, chronological, sortable incident identifier.
    
    Format: INC-YYYYMMDD-XXXXXX (e.g. INC-20260929-000001)
    Guaranteed thread-safe and deterministic.
    """
    global _daily_counter, _last_counter_date

    ts = timestamp or datetime.now(timezone.utc)
    date_str = ts.strftime("%Y%m%d")

    with _id_lock:
        if date_str != _last_counter_date:
            _daily_counter = 0
            _last_counter_date = date_str
        _daily_counter += 1
        seq = _daily_counter

    return f"INC-{date_str}-{seq:06d}"


def get_safe_snapshot_filename(incident_id: str) -> str:
    """Validates and formats a safe filename for evidence snapshots."""
    # Strict regex check to prevent path traversal
    clean_id = re.sub(r"[^A-Za-z0-9_-]", "", incident_id)
    if not clean_id:
        clean_id = f"INC-UNKNOWN-{int(datetime.now(timezone.utc).timestamp())}"
    return f"{clean_id}.jpg"


class EvidenceManager:
    """Manages creation and storage of annotated evidence images for confirmed incidents."""

    def __init__(self, base_storage_dir: Optional[Path] = None) -> None:
        self.base_dir = Path(base_storage_dir or settings.SNAPSHOT_STORAGE_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_snapshot_path(self, incident_id: str, timestamp: datetime) -> Path:
        """Computes partitioned snapshot path: storage/snapshots/YYYY/MM/DD/INC-...jpg."""
        safe_fname = get_safe_snapshot_filename(incident_id)
        year = timestamp.strftime("%Y")
        month = timestamp.strftime("%m")
        day = timestamp.strftime("%d")

        target_dir = self.base_dir / year / month / day
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / safe_fname

    def save_solid_snapshot(
        self,
        frame: np.ndarray,
        incident_id: str,
        camera_id: str,
        category: str,
        confidence: float,
        track_id: int,
        bbox: BoundingBox,
        severity: IncidentSeverity,
        timestamp: Optional[datetime] = None,
    ) -> str:
        """Annotates and saves an evidence snapshot for a solid waste incident."""
        ts = timestamp or datetime.now(timezone.utc)
        annotated = frame.copy()
        h, w = annotated.shape[:2]

        # Severity color coding (BGR)
        color = (0, 0, 255) if severity == IncidentSeverity.HIGH else (0, 140, 255) if severity == IncidentSeverity.MEDIUM else (0, 255, 0)

        # 1. Draw Bounding Box
        x1, y1 = max(0, int(bbox.x1)), max(0, int(bbox.y1))
        x2, y2 = min(w, int(bbox.x2)), min(h, int(bbox.y2))
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        # 2. Draw Target Label
        label = f"[{incident_id}] {category} (ID:{track_id} {confidence:.2f})"
        (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        label_y1 = max(0, y1 - lh - 6)
        cv2.rectangle(annotated, (x1, label_y1), (x1 + lw + 8, label_y1 + lh + 6), color, -1)
        cv2.putText(annotated, label, (x1 + 4, label_y1 + lh + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # 3. Draw Top Information Banner
        banner_text = f"EVIDENCE [{severity.value}] | {camera_id} | {ts.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        cv2.rectangle(annotated, (0, 0), (w, 28), (20, 20, 20), -1)
        cv2.putText(annotated, banner_text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # 4. Save to disk
        out_path = self.get_snapshot_path(incident_id, ts)
        cv2.imwrite(str(out_path), annotated, [cv2.IMWRITE_JPEG_QUALITY, 90])
        logger.info("[%s] Evidence snapshot saved: %s", camera_id, out_path)
        return str(out_path)

    def save_liquid_snapshot(
        self,
        frame: np.ndarray,
        incident_id: str,
        camera_id: str,
        category: str,
        confidence: float,
        affected_area_pixels: int,
        affected_area_percent: float,
        roi_name: str,
        polygon: List[List[float]],
        bbox: Optional[BoundingBox],
        severity: IncidentSeverity,
        timestamp: Optional[datetime] = None,
    ) -> str:
        """Annotates and saves an evidence snapshot for a liquid waste incident."""
        ts = timestamp or datetime.now(timezone.utc)
        annotated = frame.copy()
        h, w = annotated.shape[:2]

        color = (0, 0, 255) if severity == IncidentSeverity.HIGH else (0, 140, 255) if severity == IncidentSeverity.MEDIUM else (0, 255, 255)

        # 1. Draw Liquid Polygon overlay if available
        if polygon and len(polygon) >= 3:
            pts = np.array(polygon, dtype=np.int32).reshape((-1, 1, 2))
            overlay = annotated.copy()
            cv2.fillPoly(overlay, [pts], color)
            cv2.addWeighted(overlay, 0.35, annotated, 0.65, 0, annotated)
            cv2.polylines(annotated, [pts], isClosed=True, color=color, thickness=2)

        # 2. Draw Bounding Box / Label
        if bbox:
            bx1, by1 = max(0, int(bbox.x1)), max(0, int(bbox.y1))
            label = f"[{incident_id}] {category} ({affected_area_percent:.1f}% / {affected_area_pixels}px)"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            label_y1 = max(0, by1 - lh - 6)
            cv2.rectangle(annotated, (bx1, label_y1), (bx1 + lw + 8, label_y1 + lh + 6), color, -1)
            cv2.putText(annotated, label, (bx1 + 4, label_y1 + lh + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        # 3. Draw Top Information Banner
        banner_text = f"EVIDENCE [{severity.value}] | {camera_id} (ROI: {roi_name}) | {ts.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        cv2.rectangle(annotated, (0, 0), (w, 28), (20, 20, 20), -1)
        cv2.putText(annotated, banner_text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # 4. Save to disk
        out_path = self.get_snapshot_path(incident_id, ts)
        cv2.imwrite(str(out_path), annotated, [cv2.IMWRITE_JPEG_QUALITY, 90])
        logger.info("[%s] Liquid evidence snapshot saved: %s", camera_id, out_path)
        return str(out_path)
