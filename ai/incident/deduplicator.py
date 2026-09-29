"""Incident deduplication and cooldown mechanism to prevent violation alert spam."""
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Any

from backend.app.core.config import settings

logger = logging.getLogger("incident_deduplicator")


class IncidentDeduplicator:
    """Manages cooldown intervals to prevent duplicate alerts for persistent violations.
    
    Deduplication Keys:
    - Solid Waste:  "{camera_id}:SOLID:{category}:{track_id}"
    - Liquid Waste: "{camera_id}:LIQUID:{category}:{roi_name}"
    """

    def __init__(self, cooldown_seconds: Optional[int] = None) -> None:
        self.cooldown_seconds = (
            cooldown_seconds
            if cooldown_seconds is not None
            else settings.INCIDENT_COOLDOWN_SECONDS
        )
        # Map of dedup_key -> (last_incident_time, last_incident_id)
        self._cooldown_table: Dict[str, Tuple[datetime, str]] = {}

    @staticmethod
    def build_solid_key(camera_id: str, category: str, track_id: int) -> str:
        """Constructs deduplication key for a tracked solid waste object."""
        return f"{camera_id}:SOLID:{category.lower().strip()}:{track_id}"

    @staticmethod
    def build_liquid_key(camera_id: str, category: str, roi_name: str = "global") -> str:
        """Constructs deduplication key for a liquid waste accumulation event."""
        return f"{camera_id}:LIQUID:{category.lower().strip()}:{roi_name.lower().strip()}"

    def is_duplicate(self, dedup_key: str, current_time: Optional[datetime] = None) -> bool:
        """Checks if an incident is currently suppressed under active cooldown.
        
        Returns:
            True if an incident was already emitted within cooldown_seconds;
            False if never emitted or if cooldown period has elapsed.
        """
        if dedup_key not in self._cooldown_table:
            return False

        last_time, incident_id = self._cooldown_table[dedup_key]
        now = current_time or datetime.now(timezone.utc)
        elapsed = (now - last_time).total_seconds()

        if elapsed < self.cooldown_seconds:
            logger.debug(
                "Duplicate suppressed for %s (last: %s, elapsed: %.1fs < %ds)",
                dedup_key,
                incident_id,
                elapsed,
                self.cooldown_seconds,
            )
            return True

        # Cooldown has expired: eligible for a repeated violation incident
        logger.info(
            "Cooldown expired for %s (elapsed: %.1fs >= %ds). Eligible for new incident.",
            dedup_key,
            elapsed,
            self.cooldown_seconds,
        )
        return False

    def register_incident(
        self,
        dedup_key: str,
        incident_id: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Records an emitted incident to initiate cooldown."""
        now = timestamp or datetime.now(timezone.utc)
        self._cooldown_table[dedup_key] = (now, incident_id)
        logger.debug("Cooldown registered for %s (incident: %s, duration: %ds)", dedup_key, incident_id, self.cooldown_seconds)

    def get_remaining_cooldown(self, dedup_key: str, current_time: Optional[datetime] = None) -> float:
        """Returns remaining cooldown time in seconds, or 0.0 if not on cooldown."""
        if dedup_key not in self._cooldown_table:
            return 0.0
        last_time, _ = self._cooldown_table[dedup_key]
        now = current_time or datetime.now(timezone.utc)
        elapsed = (now - last_time).total_seconds()
        remaining = self.cooldown_seconds - elapsed
        return max(0.0, round(remaining, 1))

    def clear_key(self, dedup_key: str) -> bool:
        """Removes a key from cooldown (e.g. when track is resolved)."""
        return self._cooldown_table.pop(dedup_key, None) is not None

    def reset(self) -> None:
        """Clears all cooldown tracking."""
        self._cooldown_table.clear()

    def cleanup(self, max_age_seconds: Optional[float] = None) -> int:
        """Purges old expired cooldown records to prevent unbounded memory growth."""
        cutoff_age = max_age_seconds if max_age_seconds is not None else (self.cooldown_seconds * 2.0)
        now = datetime.now(timezone.utc)
        keys_to_remove = []

        for key, (last_time, _) in self._cooldown_table.items():
            if (now - last_time).total_seconds() > cutoff_age:
                keys_to_remove.append(key)

        for k in keys_to_remove:
            del self._cooldown_table[k]

        return len(keys_to_remove)
