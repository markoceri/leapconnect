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
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from leapconnect.application.settings_store import recalculate_session
from leapconnect.domain.charging.location import (
    DC_CHARGE_STATE,
    resolve_charge_location,
)
from leapconnect.domain.charging.models import ChargingSessionCost
from leapconnect.domain.charging.sessions import detect_charge_sessions

if TYPE_CHECKING:
    from leapconnect.application.ports.repositories import AppRepository

# A stored record within this distance of a detected start is the same session
# (matches the frontend's merge tolerance).
SAME_SESSION_TOLERANCE = timedelta(minutes=2)

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


def _naive_utc(ts: datetime | None) -> datetime | None:
    """Snapshots are stored as naive UTC; align client timestamps with them."""
    if ts is None or ts.tzinfo is None:
        return ts
    return ts.astimezone(UTC).replace(tzinfo=None)


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
    window = [s for s in history if start <= _naive_utc(s.timestamp) <= end]
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
        start = _naive_utc(item.start_ts)
        end = _naive_utc(item.end_ts)

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
                    and abs(_naive_utc(c.start_ts) - start) < SAME_SESSION_TOLERANCE
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


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    """``[first instant, first instant of next month)`` as naive UTC."""
    start = datetime(year, month, 1)
    end = datetime(year + month // 12, month % 12 + 1, 1)
    return start, end


async def find_month_missing_costs(
    repo: AppRepository, vin: str, year: int, month: int
) -> list[MissingCostSession]:
    """Server-side equivalent of the Charging tab's "missing costs" selection.

    Returns every session started in the month (UTC) without a cost: stored
    records, snapshot-only sessions, and open records whose end is visible in
    the history (carrying that end so they can be closed).
    """
    start, end = month_bounds(year, month)
    # One extra day on each side so a charge running across midnight is seen
    # whole: its end in the next month, and — for one already running when the
    # month starts — its real start, so it isn't mistaken for a new session
    # beginning at the first snapshot of the month.
    history = await repo.get_history(
        vin,
        from_date=(start - timedelta(days=1)).date().isoformat(),
        to_date=end.date().isoformat(),
        max_points=None,
    )
    detected = [
        s
        for s in detect_charge_sessions(history)
        if start <= _naive_utc(s.start_ts) < end
    ]
    stored = [
        c
        for c in await repo.get_session_costs(vin)
        if c.start_ts and start <= _naive_utc(c.start_ts) < end
    ]

    missing: list[MissingCostSession] = []
    matched_ids: set[int] = set()
    for ds in detected:
        ds_start = _naive_utc(ds.start_ts)
        match = next(
            (
                c
                for c in stored
                if abs(_naive_utc(c.start_ts) - ds_start) < SAME_SESSION_TOLERANCE
            ),
            None,
        )
        if match is None:
            missing.append(MissingCostSession(start_ts=ds_start, end_ts=ds.end_ts))
            continue
        matched_ids.add(match.id)
        if match.cost is None:
            missing.append(
                MissingCostSession(
                    start_ts=_naive_utc(match.start_ts),
                    end_ts=match.end_ts or ds.end_ts,
                    cost_id=match.id,
                )
            )
    for c in stored:
        if c.cost is None and c.id not in matched_ids:
            missing.append(
                MissingCostSession(
                    start_ts=_naive_utc(c.start_ts), end_ts=c.end_ts, cost_id=c.id
                )
            )
    return missing


async def calculate_month_missing_costs(
    repo: AppRepository, vin: str, year: int, month: int
) -> MissingCostsResult:
    """Unattended month-end run: infer tiers, skip unknown ones, close orphans."""
    sessions = await find_month_missing_costs(repo, vin, year, month)
    if not sessions:
        return MissingCostsResult()
    return await calculate_missing_costs(repo, vin, sessions, close_orphans=True)
