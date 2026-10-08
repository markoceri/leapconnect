"""Charge sessions of a period: detection from telemetry + merge with records.

A session is a run of consecutive snapshots with ``battery_is_charging`` set.
Periods (a calendar month, a range of days) are in the user's time zone; a
session belongs to the period its (real) start falls in. This is the single
source of the session lists of the Charging and History tabs and of the
month-end cost calculation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo

from leapconnect.domain.charging.models import ChargingSessionCost
from leapconnect.domain.telemetry.models import VehicleSnapshot

# A stored record within this distance of a detected start is the same session.
SAME_SESSION_TOLERANCE = timedelta(minutes=2)

# History fetched around the period: a charge running across either boundary
# must be seen whole, or one already running when the period starts looks like
# a new session beginning at the period's first snapshot.
HISTORY_MARGIN = timedelta(days=1)


@dataclass(frozen=True)
class DetectedChargeSession:
    start_ts: datetime
    end_ts: datetime | None  # None while the last run is still charging
    energy_kwh: float | None = None
    peak_power_kw: float | None = None
    start_soc: int | None = None
    end_soc: int | None = None


@dataclass(frozen=True)
class ChargeSessionRow:
    """One row of a period's session list.

    ``record`` is the stored cost record, if any; ``detected_end_ts`` is the
    end seen in the history (lets an open record whose stop was missed be
    closed).
    """

    start_ts: datetime
    end_ts: datetime | None
    record: ChargingSessionCost | None = None
    energy_kwh: float | None = None
    peak_power_kw: float | None = None
    detected_end_ts: datetime | None = None
    start_soc: int | None = None
    end_soc: int | None = None


def naive_utc(ts: datetime | None) -> datetime | None:
    """Normalize to naive UTC (stored timestamps are naive UTC)."""
    if ts is None or ts.tzinfo is None:
        return ts
    return ts.astimezone(UTC).replace(tzinfo=None)


def month_bounds(year: int, month: int, tz: tzinfo = UTC) -> tuple[datetime, datetime]:
    """``[first instant, first instant of next month)`` of a month in ``tz``,
    as naive UTC."""
    start = datetime(year, month, 1, tzinfo=tz)
    end = datetime(year + month // 12, month % 12 + 1, 1, tzinfo=tz)
    return naive_utc(start), naive_utc(end)


def day_range_bounds(
    first: date, last: date, tz: tzinfo = UTC
) -> tuple[datetime, datetime]:
    """``[first day 00:00, day after last 00:00)`` in ``tz``, as naive UTC."""
    start = datetime.combine(first, time(), tzinfo=tz)
    end = datetime.combine(last + timedelta(days=1), time(), tzinfo=tz)
    return naive_utc(start), naive_utc(end)


def _session(
    start: VehicleSnapshot, last: VehicleSnapshot, peak: float, *, open_ended: bool
) -> DetectedChargeSession:
    energy = None
    first_wh, last_wh = start.battery_dump_energy, last.battery_dump_energy
    if first_wh is not None and last_wh is not None:
        energy = round(abs(last_wh - first_wh) / 1000, 2)
    return DetectedChargeSession(
        start_ts=start.timestamp,
        end_ts=None if open_ended else last.timestamp,
        energy_kwh=energy,
        peak_power_kw=round(peak, 1) if peak > 0 else None,
        start_soc=start.battery_soc,
        end_soc=last.battery_soc,
    )


def detect_charge_sessions(
    snapshots: Sequence[VehicleSnapshot],
) -> list[DetectedChargeSession]:
    """Split time-ordered snapshots into charging sessions."""
    sessions: list[DetectedChargeSession] = []
    start: VehicleSnapshot | None = None
    last: VehicleSnapshot | None = None
    peak = 0.0
    for snap in snapshots:
        if snap.battery_is_charging:
            if start is None:
                start = snap
                peak = 0.0
            last = snap
            if snap.battery_charging_power_kw is not None:
                peak = max(peak, snap.battery_charging_power_kw)
        elif start is not None:
            sessions.append(_session(start, last, peak, open_ended=False))
            start = last = None
    if start is not None:
        sessions.append(_session(start, last, peak, open_ended=True))
    return sessions


def merge_sessions(
    detected: Sequence[DetectedChargeSession],
    stored: Sequence[ChargingSessionCost],
    start: datetime,
    end: datetime,
) -> list[ChargeSessionRow]:
    """Sessions of ``[start, end)`` (naive UTC), newest first.

    Detected sessions are paired with the stored record starting within
    ``SAME_SESSION_TOLERANCE``; records matching no detected session (e.g.
    created by hand, or older than the retained history) are listed as-is.
    """

    def in_period(ts: datetime | None) -> bool:
        return ts is not None and start <= naive_utc(ts) < end

    rows: list[ChargeSessionRow] = []
    merged_ids: set[int] = set()
    for ds in detected:
        ds_start = naive_utc(ds.start_ts)
        if not in_period(ds_start):
            continue
        match = next(
            (
                c
                for c in stored
                if c.start_ts
                and abs(naive_utc(c.start_ts) - ds_start) < SAME_SESSION_TOLERANCE
            ),
            None,
        )
        if match is None:
            rows.append(
                ChargeSessionRow(
                    start_ts=ds_start,
                    end_ts=naive_utc(ds.end_ts),
                    energy_kwh=ds.energy_kwh,
                    peak_power_kw=ds.peak_power_kw,
                    start_soc=ds.start_soc,
                    end_soc=ds.end_soc,
                )
            )
            continue
        if match.id is not None:
            merged_ids.add(match.id)
        rows.append(
            ChargeSessionRow(
                start_ts=naive_utc(match.start_ts),
                end_ts=naive_utc(match.end_ts),
                record=match,
                energy_kwh=match.energy_kwh
                if match.energy_kwh is not None
                else ds.energy_kwh,
                peak_power_kw=match.peak_power_kw
                if match.peak_power_kw is not None
                else ds.peak_power_kw,
                detected_end_ts=naive_utc(ds.end_ts),
                start_soc=ds.start_soc,
                end_soc=ds.end_soc,
            )
        )
    for c in stored:
        if c.id in merged_ids or not in_period(c.start_ts):
            continue
        rows.append(
            ChargeSessionRow(
                start_ts=naive_utc(c.start_ts),
                end_ts=naive_utc(c.end_ts),
                record=c,
                energy_kwh=c.energy_kwh,
                peak_power_kw=c.peak_power_kw,
            )
        )
    rows.sort(key=lambda r: r.start_ts, reverse=True)
    return rows
