"""Geofence geometry (pure domain service).

Containment checks for circular and polygonal geofences plus small geometric
helpers. At geofence scale the small-angle distortion of treating lat/lon as
planar coordinates is negligible.
"""

from __future__ import annotations

import math

from leapconnect.domain.notifications.models import Geofence


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two GPS coordinates."""
    R = 6_371_000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def point_in_polygon(lat: float, lon: float, points: list) -> bool:
    """Return True if (lat, lon) lies inside the polygon defined by points.

    Uses the ray-casting algorithm. ``points`` is a list of [lat, lon] pairs.
    """
    if not points or len(points) < 3:
        return False
    inside = False
    n = len(points)
    j = n - 1
    for i in range(n):
        yi, xi = points[i][0], points[i][1]
        yj, xj = points[j][0], points[j][1]
        if ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside


def geofence_contains(geofence: Geofence, lat: float, lon: float) -> bool:
    """Return True if the vehicle position falls inside the geofence."""
    if geofence.shape_type == "polygon":
        return point_in_polygon(lat, lon, geofence.points or [])
    return haversine_distance_m(geofence.latitude, geofence.longitude, lat, lon) <= (
        geofence.radius_m
    )


def polygon_centroid(points: list[list[float]]) -> tuple[float, float]:
    """Average of the polygon vertices, used for map centering/fit."""
    lat = sum(p[0] for p in points) / len(points)
    lon = sum(p[1] for p in points) / len(points)
    return lat, lon
