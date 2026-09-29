"""Unified Incident Engine coordinating tracking, temporal validation, deduplication, and evidence generation."""
import logging
import threading
from datetime import datetime, timezone
from typing import List, Dict, Optional, Callable, Any

from ai.incident.tracker import SolidWasteTracker, TrackedSolidObject
from ai.incident.temporal_validator import (
    SolidTemporalValidator,
    LiquidTemporalValidator,
    TrackedLiquidEvent,
)
from ai.incident.severity import SeverityCalculator
from ai.incident.deduplicator import IncidentDeduplicator
from ai.incident.evidence import EvidenceManager, generate_incident_id
from backend.app.schemas.incident import IncidentCreate, WasteType, IncidentSeverity, IncidentStatus
from video.ai_router import CameraFrameAIResult

logger = logging.getLogger("incident_engine")


class IncidentEngine:
    """Core cleanliness incident detection engine.
    
    Transforms raw AI detections from Phase 4 CameraFrameAIResult into confirmed,
    deduplicated, severity-scored incident events with evidence snapshots.
    
    Decoupled from database persistence via event callbacks.
    """

    def __init__(
        self,
        deduplicator: Optional[IncidentDeduplicator] = None,
        evidence_manager: Optional[EvidenceManager] = None,
    ) -> None:
        self.deduplicator = deduplicator or IncidentDeduplicator()
        self.evidence_mgr = evidence_manager or EvidenceManager()

        # Per-camera state tracking to ensure camera independence
        self._solid_trackers: Dict[str, SolidWasteTracker] = {}
        self._solid_validators: Dict[str, SolidTemporalValidator] = {}
        self._liquid_validators: Dict[str, LiquidTemporalValidator] = {}

        self._callbacks: List[Callable[[IncidentCreate], None]] = []
        self._lock = threading.Lock()

        # Telemetry metrics
        self.total_incidents_created: int = 0
        self.solid_incidents_created: int = 0
        self.liquid_incidents_created: int = 0
        self.duplicates_suppressed: int = 0

    def on_incident(self, callback: Callable[[IncidentCreate], None]) -> None:
        """Registers a listener callback invoked whenever a new incident is confirmed."""
        with self._lock:
            self._callbacks.append(callback)

    def register_callback(self, callback: Callable[[IncidentCreate], None]) -> None:
        """Alias for on_incident."""
        self.on_incident(callback)

    def _get_solid_tracker(self, camera_id: str) -> SolidWasteTracker:
        if camera_id not in self._solid_trackers:
            self._solid_trackers[camera_id] = SolidWasteTracker()
        return self._solid_trackers[camera_id]

    def _get_solid_validator(self, camera_id: str) -> SolidTemporalValidator:
        if camera_id not in self._solid_validators:
            self._solid_validators[camera_id] = SolidTemporalValidator()
        return self._solid_validators[camera_id]

    def _get_liquid_validator(self, camera_id: str) -> LiquidTemporalValidator:
        if camera_id not in self._liquid_validators:
            self._liquid_validators[camera_id] = LiquidTemporalValidator()
        return self._liquid_validators[camera_id]

    def process_camera_result(self, result: CameraFrameAIResult) -> List[IncidentCreate]:
        """Processes a single CameraFrameAIResult from the multi-camera pipeline.
        
        Args:
            result: Preserved frame and AI detection/segmentation output from AIRouter.
            
        Returns:
            List of newly confirmed and created IncidentCreate objects.
        """
        camera_id = result.camera_id
        timestamp = result.timestamp
        frame = result.frame
        created_incidents: List[IncidentCreate] = []

        with self._lock:
            # ------------------------------------------------------------------
            # 1. SOLID WASTE PIPELINE
            # ------------------------------------------------------------------
            if result.solid_result and result.solid_result.has_violations:
                tracker = self._get_solid_tracker(camera_id)
                validator = self._get_solid_validator(camera_id)

                # Update multi-object tracker
                active_tracks = tracker.update(
                    detections=result.solid_result.detections,
                    timestamp=timestamp,
                    frame_index=result.frame_index,
                )

                # Temporal persistence validation
                confirmed_tracks = validator.validate_tracks(active_tracks)

                for track in confirmed_tracks:
                    dedup_key = self.deduplicator.build_solid_key(camera_id, track.class_name, track.track_id)

                    if self.deduplicator.is_duplicate(dedup_key, current_time=timestamp):
                        self.duplicates_suppressed += 1
                        logger.debug("[%s] Solid violation suppressed by cooldown: %s", camera_id, dedup_key)
                        continue

                    # Calculate severity
                    severity = SeverityCalculator.calculate_solid_severity(
                        category=track.class_name,
                        confidence=track.confidence,
                        duration_seconds=track.duration_seconds,
                        cluster_count=len(confirmed_tracks),
                    )

                    # Generate ID and evidence snapshot
                    incident_id = generate_incident_id(timestamp)
                    snapshot_path = self.evidence_mgr.save_solid_snapshot(
                        frame=frame,
                        incident_id=incident_id,
                        camera_id=camera_id,
                        category=track.class_name,
                        confidence=track.confidence,
                        track_id=track.track_id,
                        bbox=track.bbox,
                        severity=severity,
                        timestamp=timestamp,
                    )

                    incident = IncidentCreate(
                        incident_id=incident_id,
                        camera_id=camera_id,
                        waste_type=WasteType.SOLID,
                        category=track.class_name,
                        confidence=round(track.confidence, 4),
                        severity=severity,
                        snapshot_path=snapshot_path,
                        timestamp=timestamp,
                        track_id=track.track_id,
                        first_seen=track.first_seen,
                        last_seen=track.last_seen,
                        duration_seconds=track.duration_seconds,
                        status=IncidentStatus.NEW,
                        metadata={
                            "frame_index": result.frame_index,
                            "bounding_box": {
                                "x1": track.bbox.x1,
                                "y1": track.bbox.y1,
                                "x2": track.bbox.x2,
                                "y2": track.bbox.y2,
                            },
                            "cluster_count": len(confirmed_tracks),
                        },
                    )

                    # Mark track and record in cooldown
                    track.incident_created = True
                    self.deduplicator.register_incident(dedup_key, incident_id, timestamp)
                    self.total_incidents_created += 1
                    self.solid_incidents_created += 1
                    created_incidents.append(incident)

                    logger.info(
                        "[%s] SOLID incident created: %s (%s, track %d, conf %.2f, severity: %s)",
                        camera_id,
                        incident_id,
                        track.class_name,
                        track.track_id,
                        track.confidence,
                        severity.value,
                    )
                    self._dispatch_callbacks(incident)

            # ------------------------------------------------------------------
            # 2. LIQUID WASTE PIPELINE
            # ------------------------------------------------------------------
            if result.liquid_result and result.liquid_result.has_violations:
                liquid_val = self._get_liquid_validator(camera_id)
                roi_name = getattr(result.liquid_result, "roi_name", "global")

                # Validate area and temporal persistence
                confirmed_events = liquid_val.process_frame(
                    liquid_result=result.liquid_result,
                    timestamp=timestamp,
                    roi_name=roi_name,
                )

                for ev in confirmed_events:
                    dedup_key = self.deduplicator.build_liquid_key(camera_id, ev.category, ev.roi_name)

                    if self.deduplicator.is_duplicate(dedup_key, current_time=timestamp):
                        self.duplicates_suppressed += 1
                        logger.debug("[%s] Liquid violation suppressed by cooldown: %s", camera_id, dedup_key)
                        continue

                    # Calculate severity
                    severity = SeverityCalculator.calculate_liquid_severity(
                        category=ev.category,
                        confidence=ev.confidence,
                        affected_area_pixels=ev.affected_area_pixels,
                        affected_area_percent=ev.affected_area_percent,
                        duration_seconds=ev.duration_seconds,
                    )

                    # Generate ID and evidence snapshot
                    incident_id = generate_incident_id(timestamp)
                    snapshot_path = self.evidence_mgr.save_liquid_snapshot(
                        frame=frame,
                        incident_id=incident_id,
                        camera_id=camera_id,
                        category=ev.category,
                        confidence=ev.confidence,
                        affected_area_pixels=ev.affected_area_pixels,
                        affected_area_percent=ev.affected_area_percent,
                        roi_name=ev.roi_name,
                        polygon=ev.polygon,
                        bbox=ev.bbox,
                        severity=severity,
                        timestamp=timestamp,
                    )

                    incident = IncidentCreate(
                        incident_id=incident_id,
                        camera_id=camera_id,
                        waste_type=WasteType.LIQUID,
                        category=ev.category,
                        confidence=round(ev.confidence, 4),
                        severity=severity,
                        snapshot_path=snapshot_path,
                        timestamp=timestamp,
                        affected_area_pixels=ev.affected_area_pixels,
                        affected_area_percent=round(ev.affected_area_percent, 2),
                        affected_area=round(ev.affected_area_percent, 2),
                        roi_name=ev.roi_name,
                        first_seen=ev.first_seen,
                        last_seen=ev.last_seen,
                        duration_seconds=ev.duration_seconds,
                        status=IncidentStatus.NEW,
                        metadata={
                            "frame_index": result.frame_index,
                            "affected_area_pixels": ev.affected_area_pixels,
                            "affected_area_percent": ev.affected_area_percent,
                            "consecutive_frames": ev.consecutive_frames,
                        },
                    )

                    # Mark event and record in cooldown
                    ev.incident_created = True
                    self.deduplicator.register_incident(dedup_key, incident_id, timestamp)
                    self.total_incidents_created += 1
                    self.liquid_incidents_created += 1
                    created_incidents.append(incident)

                    logger.info(
                        "[%s] LIQUID incident created: %s (%s, %.1f%% area, conf %.2f, severity: %s)",
                        camera_id,
                        incident_id,
                        ev.category,
                        ev.affected_area_percent,
                        ev.confidence,
                        severity.value,
                    )
                    self._dispatch_callbacks(incident)

        return created_incidents

    def _dispatch_callbacks(self, incident: IncidentCreate) -> None:
        """Invokes registered subscriber callbacks safely without blocking."""
        for cb in self._callbacks:
            try:
                cb(incident)
            except Exception as e:
                logger.error("Error executing incident callback: %s", e)

    def get_metrics(self) -> Dict[str, Any]:
        """Returns structured health and performance metrics for the incident engine."""
        with self._lock:
            active_solid_tracks = sum(len(t.active_tracks) for t in self._solid_trackers.values())
            active_liquid_events = sum(len(v._active_events) for v in self._liquid_validators.values())

            return {
                "total_incidents_created": self.total_incidents_created,
                "solid_incidents_created": self.solid_incidents_created,
                "liquid_incidents_created": self.liquid_incidents_created,
                "duplicates_suppressed": self.duplicates_suppressed,
                "monitored_cameras": len(self._solid_trackers),
                "active_solid_tracks": active_solid_tracks,
                "active_liquid_events": active_liquid_events,
            }

    def reset(self) -> None:
        """Resets all tracking, temporal validation, and deduplication state."""
        with self._lock:
            self._solid_trackers.clear()
            self._solid_validators.clear()
            self._liquid_validators.clear()
            self.deduplicator.reset()
            self.total_incidents_created = 0
            self.solid_incidents_created = 0
            self.liquid_incidents_created = 0
            self.duplicates_suppressed = 0
