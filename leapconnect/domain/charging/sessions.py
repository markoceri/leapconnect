"""Charge sessions of a period: detection from telemetry + pairing with records.

A charging *run* is a span of consecutive snapshots with ``battery_is_charging``
set. A session is either a single run, or a stored record whose time window
holds several runs (merged by the user: a charge interrupted and resumed in
place, e.g. by plugging out/in or by unlocking the car).

Periods (a calendar month, a range of days) are in the user's time zone; a
session belongs to the period its (real) start falls in. This is the single
source of the session lists of the Charging and History tabs and of the
month-end cost calculation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, time, timedelta, tzinfo

from leapconnect.domain.charging.location import DC_CHARGE_STATE
from leapconnect.domain.charging.models import ChargingSessionCost
from leapconnect.domain.telemetry.models import VehicleSnapshot

# A stored record within this distance of a detected start is the same session.
SAME_SESSION_TOLERANCE = timedelta(minutes=2)

# History fetched around the period: a charge running across either boundary
# must be seen whole, or one already running when the period starts looks like
# a new session beginning at the period's first snapshot.
HISTORY_MARGIN = timedelta(days=1)

# Default longest pause between two runs that can still be merged into one
# session (chosen per merge, within the limits below).
MERGE_MAX_GAP = timedelta(hours=2)
MERGE_MAX_GAP_LIMITS = (timedelta(minutes=1), timedelta(hours=12))

# Why runs can't be merged
MERGE_ONGOING = "ongoing"
MERGE_TOO_FAR_APART = "too_far_apart"
MERGE_VEHICLE_MOVED = "vehicle_moved"
MERGE_DIFFERENT_PLACE = "different_place"
MERGE_NOT_IN_HISTORY = "not_in_history"
MERGE_TOO_FEW = "too_few"
MERGE_TIER_CONFLICT = "tier_conflict"
MERGE_DUPLICATE = "duplicate"

MERGE_REASON_LABELS = {
    MERGE_ONGOING: "a session is still in progress",
    MERGE_TOO_FAR_APART: "a pause between sessions exceeds the maximum",
    MERGE_VEHICLE_MOVED: "the vehicle moved between sessions",
    MERGE_DIFFERENT_PLACE: "sessions are in different places",
    MERGE_NOT_IN_HISTORY: "a session has no charging data in the vehicle history",
    MERGE_DUPLICATE: "a session is a possible duplicate: delete it instead",
    MERGE_TOO_FEW: "select at least two sessions",
    MERGE_TIER_CONFLICT: "sessions have different tiers: choose one",
}


# The same problems, worded for the single session they concern
MERGE_SESSION_PROBLEM_LABELS = {
    MERGE_ONGOING: "Still in progress",
    MERGE_NOT_IN_HISTORY: "No charging data in the vehicle history",
    MERGE_DUPLICATE: (
        "Possible duplicate of another session, which already counts this charge:"
        " delete it instead of merging"
    ),
}


@dataclass(frozen=True)
class DetectedChargeSession:
    """One charging run seen in the history."""

    start_ts: datetime
    end_ts: datetime | None  # None while the last run is still charging
    energy_kwh: float | None = None
    peak_power_kw: float | None = None
    start_soc: int | None = None
    end_soc: int | None = None
    # Odometer (km) at the first/last valid reading of the run
    start_odometer: int | None = None
    end_odometer: int | None = None
    # Last GPS fix of the run (the first can be stale, left over from before
    # the car woke up), and whether it was a DC charge
    latitude: float | None = None
    longitude: float | None = None
    is_dc: bool = False


@dataclass(frozen=True)
class ChargeSessionRow:
    """One row of a period's session list.

    ``record`` is the stored cost record, if any; ``parts`` are the charging
    runs it covers (more than one for a merged session); ``detected_end_ts`` is
    the end seen in the history (lets an open record whose stop was missed be
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
    parts: tuple[DetectedChargeSession, ...] = field(default=())
    # Record (with charging runs) whose window this run-less record lies in:
    # most likely a duplicate of it
    duplicate_of: ChargingSessionCost | None = None

    @property
    def location(self) -> tuple[float, float] | None:
        """Where the car charged: the last GPS fix of its latest run that has
        one, ``(latitude, longitude)``."""
        fix = next(
            (p for p in reversed(self.parts) if p.latitude and p.longitude), None
        )
        return (fix.latitude, fix.longitude) if fix else None

    @property
    def is_dc(self) -> bool:
        return any(p.is_dc for p in self.parts)


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


# -- detection ----------------------------------------------------------------


def _session(
    run: list[VehicleSnapshot], peak: float, *, open_ended: bool
) -> DetectedChargeSession:
    start, last = run[0], run[-1]
    energy = None
    first_wh, last_wh = start.battery_dump_energy, last.battery_dump_energy
    if first_wh is not None and last_wh is not None:
        energy = round(abs(last_wh - first_wh) / 1000, 2)
    # Partial payloads report the odometer as 0: only trust positive readings.
    odometers = [s.drive_total_mileage for s in run if (s.drive_total_mileage or 0) > 0]
    fix = next(
        (s for s in reversed(run) if s.vehicle_latitude and s.vehicle_longitude),
        None,
    )
    return DetectedChargeSession(
        start_ts=start.timestamp,
        end_ts=None if open_ended else last.timestamp,
        energy_kwh=energy,
        peak_power_kw=round(peak, 1) if peak > 0 else None,
        start_soc=start.battery_soc,
        end_soc=last.battery_soc,
        start_odometer=odometers[0] if odometers else None,
        end_odometer=odometers[-1] if odometers else None,
        latitude=fix.vehicle_latitude if fix else None,
        longitude=fix.vehicle_longitude if fix else None,
        is_dc=any(s.battery_charge_state == DC_CHARGE_STATE for s in run),
    )


def detect_charge_sessions(
    snapshots: Sequence[VehicleSnapshot],
) -> list[DetectedChargeSession]:
    """Split time-ordered snapshots into charging runs."""
    sessions: list[DetectedChargeSession] = []
    run: list[VehicleSnapshot] = []
    peak = 0.0
    for snap in snapshots:
        if snap.battery_is_charging:
            if not run:
                peak = 0.0
            run.append(snap)
            if snap.battery_charging_power_kw is not None:
                peak = max(peak, snap.battery_charging_power_kw)
        elif run:
            sessions.append(_session(run, peak, open_ended=False))
            run = []
    if run:
        sessions.append(_session(run, peak, open_ended=True))
    return sessions


# -- pairing with stored records ----------------------------------------------


def _owner(
    ds: DetectedChargeSession, stored: Sequence[ChargingSessionCost]
) -> ChargingSessionCost | None:
    """The record a run belongs to: the one starting closest to it (within
    ``SAME_SESSION_TOLERANCE``), else a closed record whose window contains
    its start (a merged session)."""
    ds_start = naive_utc(ds.start_ts)
    near = [
        (abs(naive_utc(c.start_ts) - ds_start), i, c)
        for i, c in enumerate(stored)
        if c.start_ts and abs(naive_utc(c.start_ts) - ds_start) < SAME_SESSION_TOLERANCE
    ]
    if near:
        return min(near)[2]
    for c in stored:
        if (
            c.start_ts
            and c.end_ts
            and naive_utc(c.start_ts) <= ds_start <= naive_utc(c.end_ts)
        ):
            return c
    return None


def _row(
    parts: Sequence[DetectedChargeSession],
    record: ChargingSessionCost | None = None,
) -> ChargeSessionRow:
    first = parts[0] if parts else None
    last = parts[-1] if parts else None
    energies = [p.energy_kwh for p in parts if p.energy_kwh is not None]
    peaks = [p.peak_power_kw for p in parts if p.peak_power_kw is not None]
    detected_energy = round(sum(energies), 2) if energies else None
    detected_peak = max(peaks) if peaks else None
    if record is None:
        return ChargeSessionRow(
            start_ts=naive_utc(first.start_ts),
            end_ts=naive_utc(last.end_ts),
            energy_kwh=detected_energy,
            peak_power_kw=detected_peak,
            start_soc=first.start_soc,
            end_soc=last.end_soc,
            parts=tuple(parts),
        )
    return ChargeSessionRow(
        start_ts=naive_utc(record.start_ts),
        end_ts=naive_utc(record.end_ts),
        record=record,
        energy_kwh=record.energy_kwh
        if record.energy_kwh is not None
        else detected_energy,
        peak_power_kw=record.peak_power_kw
        if record.peak_power_kw is not None
        else detected_peak,
        detected_end_ts=naive_utc(last.end_ts) if last else None,
        start_soc=first.start_soc if first else None,
        end_soc=last.end_soc if last else None,
        parts=tuple(parts),
    )


def pair_sessions(
    detected: Sequence[DetectedChargeSession],
    stored: Sequence[ChargingSessionCost],
    start: datetime,
    end: datetime,
) -> list[ChargeSessionRow]:
    """Sessions starting in ``[start, end)`` (naive UTC), newest first.

    Each run goes to the record starting within ``SAME_SESSION_TOLERANCE`` of
    it, or else to the closed record whose window contains it (merged
    sessions); remaining runs are listed on their own. Records with no run in
    the history (e.g. created by hand) are listed as-is.
    """

    def in_period(ts: datetime | None) -> bool:
        return ts is not None and start <= naive_utc(ts) < end

    by_record: dict[int, list[DetectedChargeSession]] = {}
    rows: list[ChargeSessionRow] = []
    for ds in detected:
        owner = _owner(ds, stored)
        if owner is not None and owner.id is not None:
            by_record.setdefault(owner.id, []).append(ds)
        elif owner is None and in_period(ds.start_ts):
            rows.append(_row([ds]))
    for c in stored:
        if not in_period(c.start_ts):
            continue
        parts = by_record.get(c.id, [])
        row = _row(parts, c)
        if not parts:
            container = _container(c, stored, by_record)
            if container is not None:
                row = replace(row, duplicate_of=container)
        rows.append(row)
    rows.sort(key=lambda r: r.start_ts, reverse=True)
    return rows


def _container(
    record: ChargingSessionCost,
    stored: Sequence[ChargingSessionCost],
    by_record: dict[int, list[DetectedChargeSession]],
) -> ChargingSessionCost | None:
    """The closed record with charging runs whose window ``record`` starts in.

    A record without runs of its own lying inside such a window describes a
    charge the other record already counts — e.g. the ones created at a UTC
    month start for a charge running across it (issue #31).
    """
    start = naive_utc(record.start_ts)
    return next(
        (
            c
            for c in stored
            if c.id != record.id
            and by_record.get(c.id)
            and c.start_ts
            and c.end_ts
            and naive_utc(c.start_ts) <= start <= naive_utc(c.end_ts)
        ),
        None,
    )


# -- merging ------------------------------------------------------------------


@dataclass(frozen=True)
class MergeGap:
    """The pause between two consecutive runs, with the merge checks.

    ``same_odometer``/``same_place`` are ``None`` when they can't be checked
    (no odometer reading, no GPS fix).
    """

    start_ts: datetime  # end of the previous run
    end_ts: datetime  # start of the next run
    within_max_gap: bool
    same_odometer: bool | None
    same_place: bool | None

    @property
    def minutes(self) -> int:
        return round((self.end_ts - self.start_ts).total_seconds() / 60)


def merge_gaps(
    runs: Sequence[DetectedChargeSession],
    zone_names: Sequence[str | None],
    max_gap: timedelta = MERGE_MAX_GAP,
) -> list[MergeGap]:
    """Checks for every pause between finished, time-ordered ``runs``.

    The place of a run is compared with the last known place before it, so a
    run without GPS fix doesn't hide a change of place.
    """
    gaps: list[MergeGap] = []
    known_place = zone_names[0] if zone_names else None
    for i, (prev, cur) in enumerate(zip(runs, runs[1:], strict=False)):
        place = zone_names[i + 1]
        same_place = None
        if place is not None and known_place is not None:
            same_place = place == known_place
        if place is not None:
            known_place = place
        same_odometer = None
        if prev.end_odometer is not None and cur.start_odometer is not None:
            same_odometer = prev.end_odometer == cur.start_odometer
        start, end = naive_utc(prev.end_ts), naive_utc(cur.start_ts)
        gaps.append(
            MergeGap(
                start_ts=start,
                end_ts=end,
                within_max_gap=end - start <= max_gap,
                same_odometer=same_odometer,
                same_place=same_place,
            )
        )
    return gaps


def merge_violation(
    runs: Sequence[DetectedChargeSession],
    zone_names: Sequence[str | None],
    max_gap: timedelta = MERGE_MAX_GAP,
) -> str | None:
    """Why time-ordered ``runs`` (with the zone of each) can't be one session.

    Runs merge only when they are a charge interrupted and resumed in place:
    all finished, the vehicle never moved (same odometer) and stayed in the
    same place, with pauses no longer than ``max_gap``. A zone of ``None``
    means the place is unknown (no GPS fix) and is not compared; ``""`` is
    "outside every zone".
    """
    if len(runs) < 2:
        return MERGE_TOO_FEW
    if any(r.end_ts is None for r in runs):
        return MERGE_ONGOING
    gaps = merge_gaps(runs, zone_names, max_gap)
    if any(g.same_place is False for g in gaps):
        return MERGE_DIFFERENT_PLACE
    if any(g.same_odometer is False for g in gaps):
        return MERGE_VEHICLE_MOVED
    if any(not g.within_max_gap for g in gaps):
        return MERGE_TOO_FAR_APART
    return None
