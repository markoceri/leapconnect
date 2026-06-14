"""Per-VIN zone enter/exit tracking.

Holds the mutable "currently inside" state for each vehicle and delegates the
set math to the pure ``domain.zones.detect_transitions`` helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from leapconnect.domain.zones import detect_transitions

if TYPE_CHECKING:
    from leapconnect.domain.zones import Zone


class ZoneTracker:
    """Tracks which zones each vehicle is currently inside."""

    def __init__(self) -> None:
        # vin -> set of zone IDs the vehicle is currently inside
        self._inside: dict[str, set[int]] = {}

    def update(
        self, vin: str, lat: float, lon: float, zones: list[Zone]
    ) -> tuple[list[Zone], list[Zone]]:
        """Update state for a position fix, returning (entered, exited) zones."""
        prev_inside = self._inside.get(vin, set())
        entered, exited, current_inside = detect_transitions(
            zones, vin, lat, lon, prev_inside
        )
        self._inside[vin] = current_inside
        return entered, exited
