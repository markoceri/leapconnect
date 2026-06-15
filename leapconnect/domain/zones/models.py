"""Zone entities."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Zone:
    """A geographic zone, consumed by multiple bounded contexts.

    Notifications use it for enter/exit alerts; charging uses
    ``charging_tier_id`` to auto-select a price tier when a charge starts
    inside the zone.
    """

    id: int | None = None
    vin: str | None = None  # None = applies to all vehicles
    name: str = ""
    shape_type: str = "circle"  # "circle" | "polygon"
    latitude: float = 0.0  # circle center, or polygon centroid
    longitude: float = 0.0
    radius_m: float = 200.0  # used only when shape_type == "circle"
    points: list[list[float]] | None = None  # [[lat, lon], ...] for polygons
    notify_on_enter: bool = True
    notify_on_exit: bool = True
    enabled: bool = True
    charging_tier_id: str | None = None  # tier to bill when charging inside
    dwell_alert_minutes: int = 0  # alert if inside longer than this (0 = off)
    absence_alert_minutes: int = 0  # alert if away longer than this (0 = off)
