"""Per-VIN zone enter/exit tracking.

Holds the mutable "currently inside" state for each vehicle and delegates the
set math to the pure ``domain.zones.detect_transitions`` helper. Also keeps the
per-``(vin, zone)`` entry/exit timestamps used for dwell and absence alerts.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from leapconnect.domain.zones import detect_transitions

if TYPE_CHECKING:
    from leapconnect.domain.zones import Zone


class ZoneTracker:
    """Tracks which zones each vehicle is currently inside, with dwell timers."""

    def __init__(self) -> None:
        # vin -> set of zone IDs the vehicle is currently inside
        self._inside: dict[str, set[int]] = {}
        # (vin, zone_id) -> monotonic time the vehicle entered / last left
        self._entered_at: dict[tuple[str, int], float] = {}
        self._left_at: dict[tuple[str, int], float] = {}
        # Emit-once guards, reset on the opposite transition
        self._dwell_fired: set[tuple[str, int]] = set()
        self._absence_fired: set[tuple[str, int]] = set()

    def update(
        self, vin: str, lat: float, lon: float, zones: list[Zone]
    ) -> tuple[list[Zone], list[Zone]]:
        """Update state for a position fix, returning (entered, exited) zones."""
        prev_inside = self._inside.get(vin, set())
        entered, exited, current_inside = detect_transitions(
            zones, vin, lat, lon, prev_inside
        )
        now = time.monotonic()
        for zone in entered:
            key = (vin, zone.id)
            self._entered_at[key] = now
            self._dwell_fired.discard(key)
            self._absence_fired.discard(key)
        for zone in exited:
            key = (vin, zone.id)
            self._left_at[key] = now
            self._entered_at.pop(key, None)
            self._dwell_fired.discard(key)
            self._absence_fired.discard(key)
        self._inside[vin] = current_inside
        return entered, exited

    def due_alerts(
        self, vin: str, zones: list[Zone], now: float | None = None
    ) -> list[tuple[Zone, str]]:
        """Return (zone, kind) pairs whose dwell/absence threshold just crossed.

        ``kind`` is ``"dwell"`` (inside longer than ``dwell_alert_minutes``) or
        ``"absence"`` (away longer than ``absence_alert_minutes`` since the last
        recorded exit). Each fires once until the opposite transition resets it.
        """
        if now is None:
            now = time.monotonic()
        inside = self._inside.get(vin, set())
        results: list[tuple[Zone, str]] = []
        for zone in zones:
            if not zone.enabled or not zone.id:
                continue
            if zone.vin and zone.vin != vin:
                continue
            key = (vin, zone.id)
            if (
                zone.dwell_alert_minutes
                and zone.id in inside
                and key not in self._dwell_fired
            ):
                entered_at = self._entered_at.get(key)
                if (
                    entered_at is not None
                    and now - entered_at >= zone.dwell_alert_minutes * 60
                ):
                    self._dwell_fired.add(key)
                    results.append((zone, "dwell"))
            if (
                zone.absence_alert_minutes
                and zone.id not in inside
                and key not in self._absence_fired
            ):
                left_at = self._left_at.get(key)
                if (
                    left_at is not None
                    and now - left_at >= zone.absence_alert_minutes * 60
                ):
                    self._absence_fired.add(key)
                    results.append((zone, "absence"))
        return results

    def current_zone_ids(self, vin: str) -> set[int]:
        """Zone IDs the vehicle is currently inside (for presence surfacing)."""
        return set(self._inside.get(vin, set()))

    def tracked_vins(self) -> list[str]:
        """VINs the tracker has seen a position for."""
        return list(self._inside)
