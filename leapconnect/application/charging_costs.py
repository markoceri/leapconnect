"""Bulk "calculate missing costs" for charging sessions.

Handles three kinds of sessions that lack a cost:

- a stored record whose energy/cost could not be measured at charge stop
  → re-measured and re-costed;
- a session detected only from snapshots (the charge start was never seen)
  → zone/tier resolved from the snapshots in its window and a record created;
- a stored record left open because the charge stop was missed ("orphan")
  → closed with the snapshot-detected end, only when explicitly requested.

The same logic runs unattended at month end (``calculate_month_missing_costs``)
for the previous month, finding the sessions server-side.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, tzinfo
from typing import TYPE_CHECKING

from leapconnect.application.settings_store import (
    calculate_session_cost,
    load_user_timezone,
    recalculate_session,
)
from leapconnect.domain.charging.location import (
    DC_CHARGE_STATE,
    resolve_charge_location,
)
from leapconnect.domain.charging.models import ChargingSessionCost
from leapconnect.domain.charging.sessions import (
    HISTORY_MARGIN,
    MERGE_MAX_GAP,
    MERGE_NOT_IN_HISTORY,
    MERGE_ONGOING,
    MERGE_TIER_CONFLICT,
    MERGE_TOO_FEW,
    SAME_SESSION_TOLERANCE,
    ChargeSessionRow,
    DetectedChargeSession,
    MergeGap,
    detect_charge_sessions,
    merge_gaps,
    merge_violation,
    month_bounds,
    naive_utc,
    pair_sessions,
)

if TYPE_CHECKING:
    from leapconnect.application.ports.repositories import AppRepository

SKIP_ONGOING = "ongoing"
SKIP_NO_TIER = "no_tier"
SKIP_NO_ENERGY = "no_energy"
SKIP_NOT_FOUND = "not_found"

SKIP_REASON_LABELS = {
    SKIP_NO_TIER: "tier not inferable",
    SKIP_NO_ENERGY: "energy not measurable",
    SKIP_ONGOING: "still open",
    SKIP_NOT_FOUND: "session no longer exists",
}


@dataclass
class MissingCostSession:
    """A session the client wants costed."""

    start_ts: datetime
    end_ts: datetime | None = None
    cost_id: int | None = None


@dataclass
class SkippedSession:
    start_ts: datetime
    reason: str


@dataclass
class MissingCostsResult:
    calculated: int = 0
    skipped: list[SkippedSession] = field(default_factory=list)


async def _locate_from_snapshots(
    repo: AppRepository, vin: str, start: datetime, end: datetime
):
    """Resolve zone/tier for a session from the snapshots in its window."""
    history = await repo.get_history(
        vin,
        from_date=start.date().isoformat(),
        to_date=end.date().isoformat(),
        max_points=None,
    )
    window = [s for s in history if start <= naive_utc(s.timestamp) <= end]
    positioned = next(
        (s for s in window if s.vehicle_latitude and s.vehicle_longitude), None
    )
    is_dc = any(s.battery_charge_state == DC_CHARGE_STATE for s in window)
    return resolve_charge_location(
        await repo.get_zones(vin),
        positioned.vehicle_latitude if positioned else None,
        positioned.vehicle_longitude if positioned else None,
        is_dc=is_dc,
    )


async def calculate_missing_costs(
    repo: AppRepository,
    vin: str,
    sessions: list[MissingCostSession],
    *,
    fallback_tier_id: str | None = None,
    close_orphans: bool = False,
) -> MissingCostsResult:
    """Compute costs for the given sessions; report the ones left untouched.

    ``fallback_tier_id`` is applied to snapshot-only sessions whose tier cannot
    be inferred (no DC charge, not inside a zone with a tier); when ``None``
    those sessions are skipped. ``close_orphans`` lets an open stored record be
    closed with the client-detected ``end_ts``.
    """
    result = MissingCostsResult()
    stored = await repo.get_session_costs(vin)
    by_id = {sc.id: sc for sc in stored}

    for item in sessions:
        start = naive_utc(item.start_ts)
        end = naive_utc(item.end_ts)

        if item.cost_id is not None:
            sc = by_id.get(item.cost_id)
            if sc is None:
                result.skipped.append(SkippedSession(start, SKIP_NOT_FOUND))
                continue
            if sc.end_ts is None:
                if not (close_orphans and end):
                    result.skipped.append(SkippedSession(start, SKIP_ONGOING))
                    continue
                sc.end_ts = end
        else:
            if end is None:
                result.skipped.append(SkippedSession(start, SKIP_ONGOING))
                continue
            # Guard against a record created since the client loaded the list.
            sc = next(
                (
                    c
                    for c in stored
                    if c.start_ts
                    and abs(naive_utc(c.start_ts) - start) < SAME_SESSION_TOLERANCE
                ),
                None,
            )
            if sc is None:
                location = await _locate_from_snapshots(repo, vin, start, end)
                tier_id = location.tier_id or fallback_tier_id
                if not tier_id:
                    result.skipped.append(SkippedSession(start, SKIP_NO_TIER))
                    continue
                sc = ChargingSessionCost(
                    vin=vin,
                    start_ts=start,
                    end_ts=end,
                    tier_id=tier_id,
                    zone_name=location.zone_name,
                )
                stored.append(sc)

        await recalculate_session(repo, sc)
        if sc.cost is None:
            # Nothing measurable — don't persist an empty new record.
            if sc.id is not None:
                await repo.upsert_session_cost(sc)
            result.skipped.append(SkippedSession(start, SKIP_NO_ENERGY))
            continue
        await repo.upsert_session_cost(sc)
        result.calculated += 1

    return result


async def list_sessions(
    repo: AppRepository, vin: str, start: datetime, end: datetime
) -> list[ChargeSessionRow]:
    """Charging sessions starting in ``[start, end)`` (naive UTC), newest first.

    Sessions are detected from the full (not downsampled) snapshots and paired
    with the stored cost records.
    """
    # Repository dates are UTC days (whole days, end inclusive).
    history = await repo.get_history(
        vin,
        from_date=(start - HISTORY_MARGIN).date().isoformat(),
        to_date=(end + HISTORY_MARGIN).date().isoformat(),
        max_points=None,
    )
    return pair_sessions(
        detect_charge_sessions(history),
        await repo.get_session_costs(vin),
        start,
        end,
    )


async def list_month_sessions(
    repo: AppRepository, vin: str, year: int, month: int, tz: tzinfo | None = None
) -> list[ChargeSessionRow]:
    """The month's charging sessions, newest first — the Charging tab's list.

    The month is a calendar month in the user's time zone (``tz``, from the
    preferences when omitted).
    """
    if tz is None:
        tz = await load_user_timezone(repo)
    return await list_sessions(repo, vin, *month_bounds(year, month, tz))


async def find_month_missing_costs(
    repo: AppRepository, vin: str, year: int, month: int, tz: tzinfo | None = None
) -> list[MissingCostSession]:
    """The month's sessions without a cost, oldest first.

    Same selection as the Charging tab's "missing costs" button: stored
    records, snapshot-only sessions, and open records whose end is visible in
    the history (carrying that end so they can be closed).
    """
    missing: list[MissingCostSession] = []
    for row in reversed(await list_month_sessions(repo, vin, year, month, tz)):
        if row.duplicate_of is not None:
            continue  # its charge is already counted by the other record
        rec = row.record
        if rec is None:
            missing.append(MissingCostSession(start_ts=row.start_ts, end_ts=row.end_ts))
        elif rec.cost is None:
            missing.append(
                MissingCostSession(
                    start_ts=row.start_ts,
                    end_ts=row.end_ts or row.detected_end_ts,
                    cost_id=rec.id,
                )
            )
    return missing


async def calculate_month_missing_costs(
    repo: AppRepository, vin: str, year: int, month: int, tz: tzinfo | None = None
) -> MissingCostsResult:
    """Unattended month-end run: infer tiers, skip unknown ones, close orphans."""
    sessions = await find_month_missing_costs(repo, vin, year, month, tz)
    if not sessions:
        return MissingCostsResult()
    return await calculate_missing_costs(repo, vin, sessions, close_orphans=True)


# -- merging ----------------------------------------------------------------


class MergeError(Exception):
    """The selected sessions can't be merged; ``reason`` is a MERGE_* code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class MergePlan:
    """What merging a selection would do: the dialog's preview, and the
    input of the merge itself."""

    rows: list[ChargeSessionRow]  # oldest first, the in-between ones included
    runs: list[DetectedChargeSession] = field(default_factory=list)
    places: list[str | None] = field(default_factory=list)
    gaps: list[MergeGap] = field(default_factory=list)
    tiers: list[str] = field(default_factory=list)  # tiers of the sessions
    tier_id: str | None = None  # tier of the result; None when to be chosen
    energy_kwh: float | None = None
    cost: float | None = None  # estimated, run by run
    reason: str | None = None  # why it can't be merged (MERGE_*)

    @property
    def zone_name(self) -> str | None:
        return next((p for p in self.places if p), None)


async def plan_merge(
    repo: AppRepository,
    vin: str,
    starts: list[datetime],
    *,
    tier_id: str | None = None,
    max_gap: timedelta = MERGE_MAX_GAP,
) -> MergePlan:
    """Check a merge of the sessions starting at ``starts`` without saving.

    Every session between the first and the last selected one is included.
    The rules are in ``merge_violation``; ``reason`` is set when they fail.
    """
    starts = sorted(naive_utc(s) for s in starts)
    if len(starts) < 2:
        return MergePlan(rows=[], reason=MERGE_TOO_FEW)
    rows = list(
        reversed(
            await list_sessions(
                repo, vin, starts[0], starts[-1] + timedelta(microseconds=1)
            )
        )
    )
    plan = MergePlan(rows=rows)
    if len(rows) < 2:
        plan.reason = MERGE_TOO_FEW
        return plan
    if any(r.record is not None and r.record.end_ts is None for r in rows):
        plan.reason = MERGE_ONGOING
        return plan
    if any(not r.parts for r in rows):
        plan.reason = MERGE_NOT_IN_HISTORY
        return plan

    zones = await repo.get_zones(vin)
    tiers: list[str] = []
    for row in rows:
        for run in row.parts:
            location = resolve_charge_location(
                zones, run.latitude, run.longitude, is_dc=run.is_dc
            )
            if row.record is not None and row.record.zone_name:
                place = row.record.zone_name
            elif run.latitude and run.longitude:
                place = location.zone_name or ""
            else:
                place = None  # no GPS fix: place unknown
            plan.runs.append(run)
            plan.places.append(place)
            if row.record is None and location.tier_id:
                tiers.append(location.tier_id)
        if row.record is not None:
            tiers.append(row.record.tier_id)
    plan.tiers = list(dict.fromkeys(tiers))
    energies = [r.energy_kwh for r in plan.runs if r.energy_kwh is not None]
    plan.energy_kwh = round(sum(energies), 2) if energies else None
    plan.reason = merge_violation(plan.runs, plan.places, max_gap)
    if plan.reason == MERGE_ONGOING:
        return plan
    plan.gaps = merge_gaps(plan.runs, plan.places, max_gap)

    if tier_id is None and len(plan.tiers) > 1:
        plan.reason = plan.reason or MERGE_TIER_CONFLICT
        return plan
    plan.tier_id = tier_id or next(iter(plan.tiers), "home_grid")
    plan.cost = 0.0
    for run in plan.runs:
        if run.energy_kwh:
            plan.cost += await calculate_session_cost(
                repo, plan.tier_id, run.energy_kwh, run.start_ts, run.end_ts
            )
    plan.cost = round(plan.cost, 4)
    return plan


async def merge_charge_sessions(
    repo: AppRepository,
    vin: str,
    starts: list[datetime],
    *,
    tier_id: str | None = None,
    max_gap: timedelta = MERGE_MAX_GAP,
) -> ChargingSessionCost:
    """Merge the sessions starting at ``starts`` into one record.

    Meant for a charge interrupted and resumed in place (plug out/in, car
    unlocked mid-charge); checked by ``plan_merge``. The earliest stored
    record is kept (or one is created), its window stretched over all the
    runs, and the other records are deleted; energy and cost are then
    re-measured run by run. Deleting the merged record splits it back into
    its runs.
    """
    plan = await plan_merge(repo, vin, starts, tier_id=tier_id, max_gap=max_gap)
    if plan.reason:
        raise MergeError(plan.reason)
    rows, runs = plan.rows, plan.runs
    records = [r.record for r in rows if r.record is not None]
    keeper = records[0] if records else ChargingSessionCost(vin=vin)
    keeper.start_ts = rows[0].start_ts
    keeper.end_ts = max(
        [naive_utc(runs[-1].end_ts)]
        + [naive_utc(r.end_ts) for r in records if r.end_ts]
    )
    keeper.tier_id = plan.tier_id
    keeper.zone_name = plan.zone_name or keeper.zone_name
    peaks = [r.peak_power_kw for r in runs if r.peak_power_kw is not None]
    keeper.peak_power_kw = max(peaks) if peaks else keeper.peak_power_kw
    notes = [r.note for r in records if r.note]
    keeper.note = " · ".join(dict.fromkeys(notes)) or None
    keeper.energy_kwh = None
    keeper.cost = None
    keeper = await repo.upsert_session_cost(keeper)
    for other in records[1:]:
        await repo.delete_session_cost(other.id)
    await recalculate_session(repo, keeper)
    return await repo.upsert_session_cost(keeper)
