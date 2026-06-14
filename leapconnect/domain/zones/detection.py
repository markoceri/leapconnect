"""Pure zone transition detection.

Given the zones a vehicle is currently inside vs. the previous set, compute the
enter/exit transitions. No mutable state lives here — the caller owns the
per-VIN ``prev_inside`` set (see ``application.zones.tracker.ZoneTracker``),
keeping the domain pure (stdlib + ``leapconnect.domain.*`` only).
"""

from __future__ import annotations

from leapconnect.domain.zones.geometry import zone_contains
from leapconnect.domain.zones.models import Zone


def detect_transitions(
    zones: list[Zone],
    vin: str,
    lat: float,
    lon: float,
    prev_inside: set[int],
) -> tuple[list[Zone], list[Zone], set[int]]:
    """Resolve enter/exit transitions for a position update.

    Returns ``(entered, exited, current_inside)`` where ``entered``/``exited``
    are the zones crossed since ``prev_inside`` and ``current_inside`` is the
    set of zone IDs the vehicle is now inside (to be stored for the next call).
    Disabled zones, ID-less zones, and zones scoped to another VIN are ignored.
    """
    current_inside: set[int] = set()
    by_id: dict[int, Zone] = {}
    for zone in zones:
        if not zone.enabled or not zone.id:
            continue
        if zone.vin and zone.vin != vin:
            continue
        by_id[zone.id] = zone
        if zone_contains(zone, lat, lon):
            current_inside.add(zone.id)

    entered = [by_id[zid] for zid in current_inside - prev_inside if zid in by_id]
    exited = [by_id[zid] for zid in prev_inside - current_inside if zid in by_id]
    return entered, exited, current_inside
