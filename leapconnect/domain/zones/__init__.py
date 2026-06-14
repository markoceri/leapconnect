"""Zones context — geographic zones, geometry and transition detection.

A zone is a reusable location concept consumed by multiple contexts:
notifications (enter/exit alerts) and charging (tier auto-selection).
"""

from leapconnect.domain.zones.detection import detect_transitions
from leapconnect.domain.zones.geometry import (
    haversine_distance_m,
    point_in_polygon,
    polygon_centroid,
    zone_contains,
)
from leapconnect.domain.zones.models import Zone

__all__ = [
    "Zone",
    "detect_transitions",
    "haversine_distance_m",
    "point_in_polygon",
    "polygon_centroid",
    "zone_contains",
]
