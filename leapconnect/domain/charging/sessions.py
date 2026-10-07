"""Charge-session detection from telemetry snapshots.

Mirrors the Charging tab's client-side detection: a session is a run of
consecutive snapshots with ``battery_is_charging`` set. Used server-side to
find sessions the charge-start handler never recorded.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from leapconnect.domain.telemetry.models import VehicleSnapshot


@dataclass(frozen=True)
class DetectedChargeSession:
    start_ts: datetime
    end_ts: datetime | None  # None while the last run is still charging


def detect_charge_sessions(
    snapshots: Sequence[VehicleSnapshot],
) -> list[DetectedChargeSession]:
    """Split time-ordered snapshots into charging sessions."""
    sessions: list[DetectedChargeSession] = []
    start: VehicleSnapshot | None = None
    last: VehicleSnapshot | None = None
    for snap in snapshots:
        if snap.battery_is_charging:
            if start is None:
                start = snap
            last = snap
        elif start is not None:
            sessions.append(DetectedChargeSession(start.timestamp, last.timestamp))
            start = last = None
    if start is not None:
        sessions.append(DetectedChargeSession(start.timestamp, None))
    return sessions
