"""Application-level configurable severity calculation for solid and liquid cleanliness incidents."""
import logging
from enum import Enum
from typing import Optional

from backend.app.schemas.incident import IncidentSeverity

logger = logging.getLogger("incident_severity")


class SeverityCalculator:
    """Calculates application-level incident severity (LOW, MEDIUM, HIGH).
    
    NOTE: These rules are application-level operational severity classifications
    designed for municipal triage and do NOT represent official statutory standards.
    """

    # High severity categories
    SOLID_HIGH_SEVERITY_CLASSES = {"garbage_pile"}
    LIQUID_HIGH_SEVERITY_CLASSES = {"sewage_overflow", "drain_overflow"}

    # Moderate severity categories
    SOLID_MEDIUM_SEVERITY_CLASSES = {"plastic_bottle", "plastic_bag", "can", "food_waste"}
    LIQUID_MEDIUM_SEVERITY_CLASSES = {"liquid_spill", "waterlogging"}

    @classmethod
    def calculate_solid_severity(
        cls,
        category: str,
        confidence: float,
        duration_seconds: float = 0.0,
        cluster_count: int = 1,
    ) -> IncidentSeverity:
        """Determines severity for solid waste incidents.
        
        Rules:
        - HIGH:
            * Category is 'garbage_pile' (large pile / major blockage)
            * Cluster of 3 or more tracked items in the monitored scene
            * Long persistence (>= 60s) with high confidence (>= 0.75)
        - MEDIUM:
            * Non-biodegradable / sanitary items (plastic, cans, food waste) with conf >= 0.60
            * Waste persisting >= 15 seconds
            * Cluster of 2 items
        - LOW:
            * Paper waste or isolated small items with duration < 15s and conf < 0.60
        """
        cat_lower = category.lower().strip()

        # Rule 1: High severity triggers
        if cat_lower in cls.SOLID_HIGH_SEVERITY_CLASSES:
            return IncidentSeverity.HIGH
        if cluster_count >= 3:
            return IncidentSeverity.HIGH
        if duration_seconds >= 60.0 and confidence >= 0.75:
            return IncidentSeverity.HIGH

        # Rule 2: Medium severity triggers
        if cluster_count >= 2:
            return IncidentSeverity.MEDIUM
        if cat_lower in cls.SOLID_MEDIUM_SEVERITY_CLASSES and (confidence >= 0.60 or duration_seconds >= 15.0):
            return IncidentSeverity.MEDIUM

        # Rule 3: Low severity fallback
        return IncidentSeverity.LOW

    @classmethod
    def calculate_liquid_severity(
        cls,
        category: str,
        confidence: float,
        affected_area_pixels: int = 0,
        affected_area_percent: float = 0.0,
        duration_seconds: float = 0.0,
    ) -> IncidentSeverity:
        """Determines severity for liquid waste incidents.
        
        Rules:
        - HIGH:
            * Critical biohazard or infrastructure overflow ('sewage_overflow', 'drain_overflow')
            * Severe inundation (affected area >= 15.0% or >= 10,000 pixels)
            * Persistent accumulation (duration >= 30s with area >= 10.0%)
        - MEDIUM:
            * Moderate spills or waterlogging (area >= 5.0% or >= 3,000 pixels or duration >= 10s)
        - LOW:
            * Minor localized waterlogging or small puddles (< 5.0% area and < 10s duration)
        """
        cat_lower = category.lower().strip()

        # Rule 1: High severity triggers
        if cat_lower in cls.LIQUID_HIGH_SEVERITY_CLASSES:
            return IncidentSeverity.HIGH
        if affected_area_percent >= 15.0 or affected_area_pixels >= 10000:
            return IncidentSeverity.HIGH
        if duration_seconds >= 30.0 and affected_area_percent >= 10.0:
            return IncidentSeverity.HIGH

        # Rule 2: Medium severity triggers
        if cat_lower in cls.LIQUID_MEDIUM_SEVERITY_CLASSES:
            if affected_area_percent >= 5.0 or affected_area_pixels >= 3000 or duration_seconds >= 10.0:
                return IncidentSeverity.MEDIUM

        # Rule 3: Low severity fallback
        return IncidentSeverity.LOW
