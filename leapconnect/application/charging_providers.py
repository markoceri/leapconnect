"""Import the sessions a charging provider billed into the cost records.

The provider's sessions are matched with the period's session list (the one
the Charging tab shows); a preview shows what would change, and applying it
sets the billed energy, cost and fees on the matched records — values entered
by hand are kept. Provider sessions the vehicle history doesn't show are only
created on request.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from leapconnect.application.charging_costs import list_sessions
from leapconnect.application.settings_store import (
    price_session_extras,
    recalculate_session,
)
from leapconnect.domain.charging.models import ChargingSessionCost
from leapconnect.domain.charging.providers import (
    CANDIDATE_WINDOW,
    DISMISSED,
    IMPORTED,
    MATCHED,
    PUBLIC_AC,
    PUBLIC_DC,
    UNCERTAIN,
    UNMATCHED,
    ProviderCandidate,
    ProviderMatch,
    ProviderSession,
    apply_provider_session,
    match_provider_sessions,
    new_record_for,
    rank_candidates,
    unlink_provider_session,
)
from leapconnect.domain.charging.sessions import ChargeSessionRow, naive_utc

if TYPE_CHECKING:
    from leapconnect.application.ports.charging_provider import ChargingProvider
    from leapconnect.application.ports.repositories import AppRepository

# Provider sessions are fetched a little before the period: a charge started
# just before it can still belong to a session listed in it.
FETCH_MARGIN = timedelta(days=1)

# The automatic import looks this far back
AUTO_SYNC_WINDOW = timedelta(days=14)


@dataclass
class ImportPreviewItem:
    """One provider session and what importing it would do."""

    match: ProviderMatch
    current: ChargingSessionCost | None  # the record as it is now
    proposed: ChargingSessionCost | None  # the record after the import
    energy_kept: bool = False  # energy entered by hand: not replaced
    cost_kept: bool = False  # cost entered by hand: not replaced


@dataclass
class ImportResult:
    applied: int = 0
    created: int = 0
    skipped: list[str] = field(default_factory=list)  # external ids


def _vehicle_dc(row: ChargeSessionRow) -> bool | None:
    """Whether the vehicle saw a DC charge; ``None`` without charging data."""
    return row.is_dc if row.parts else None


def _record_for_row(vin: str, row: ChargeSessionRow) -> ChargingSessionCost:
    """The row's record, or a new one for a session seen only in the history."""
    if row.record is not None:
        return row.record
    return ChargingSessionCost(
        vin=vin,
        start_ts=row.start_ts,
        end_ts=row.end_ts,
        tier_id=PUBLIC_DC if row.is_dc else PUBLIC_AC,
        energy_kwh=row.energy_kwh,
        peak_power_kw=row.peak_power_kw,
    )


async def _external_links(
    repo: AppRepository, provider: ChargingProvider
) -> dict[str, tuple[str, int]]:
    return await repo.get_external_links(provider.name)


def _linked_elsewhere(
    links: dict[str, tuple[str, int]], rows: list[ChargeSessionRow]
) -> set[str]:
    """Provider sessions linked to a record not among ``rows`` (another
    vehicle's, or outside the period): not to be linked again."""
    here = {r.record.id for r in rows if r.record is not None}
    return {eid for eid, (_vin, cid) in links.items() if cid not in here}


async def _matches(
    repo: AppRepository,
    provider: ChargingProvider,
    vin: str,
    start: datetime,
    end: datetime,
) -> list[ProviderMatch]:
    sessions = await provider.fetch_sessions(start - FETCH_MARGIN)
    sessions = [s for s in sessions if s.started_at is not None and s.started_at < end]
    rows = await list_sessions(repo, vin, start - FETCH_MARGIN, end)
    elsewhere = _linked_elsewhere(await _external_links(repo, provider), rows)
    matches = match_provider_sessions(sessions, rows, elsewhere)
    # Only the period's sessions: the margin is for matching, not listing
    return [
        m
        for m in matches
        if (m.row.start_ts if m.row else m.session.started_at) >= start
    ]


def _preview(vin: str, m: ProviderMatch) -> ImportPreviewItem:
    if m.row is None:
        proposed = new_record_for(vin, m.session) if m.status == UNMATCHED else None
        return ImportPreviewItem(m, None, proposed)
    current = m.row.record
    proposed = copy.deepcopy(_record_for_row(vin, m.row))
    apply_provider_session(proposed, m.session, vehicle_dc=_vehicle_dc(m.row))
    return ImportPreviewItem(
        m,
        current,
        proposed,
        energy_kept=bool(current and current.energy_manual),
        cost_kept=bool(
            current and (current.cost_manual or current.manual_price_kwh is not None)
        ),
    )


async def preview_provider_import(
    repo: AppRepository,
    provider: ChargingProvider,
    vin: str,
    start: datetime,
    end: datetime,
) -> list[ImportPreviewItem]:
    """What importing the provider's sessions of ``[start, end)`` would do."""
    return [_preview(vin, m) for m in await _matches(repo, provider, vin, start, end)]


async def apply_provider_import(
    repo: AppRepository,
    provider: ChargingProvider,
    vin: str,
    start: datetime,
    end: datetime,
    *,
    external_ids: set[str] | None = None,
    create_ids: set[str] | frozenset[str] = frozenset(),
) -> ImportResult:
    """Import the provider's sessions of ``[start, end)``.

    Matched (and already imported) sessions update their record — all of them
    when ``external_ids`` is ``None``, else the ones in it. Uncertain matches
    (place or energy don't fit: maybe another vehicle's charge) and the ones
    the user unlinked are imported only when in ``external_ids``; unmatched
    ones are created only when in ``create_ids``; sessions linked to another
    record are never touched.
    """
    result = ImportResult()
    for m in await _matches(repo, provider, vin, start, end):
        ps = m.session
        chosen = external_ids is not None and ps.external_id in external_ids
        if m.status == UNMATCHED and ps.external_id in create_ids:
            sc = new_record_for(vin, ps)
            result.created += 1
        elif (m.status in (MATCHED, IMPORTED) and (external_ids is None or chosen)) or (
            m.status in (UNCERTAIN, DISMISSED) and chosen
        ):
            sc = _record_for_row(vin, m.row)
            apply_provider_session(sc, ps, vehicle_dc=_vehicle_dc(m.row))
            result.applied += 1
        else:
            result.skipped.append(ps.external_id)
            continue
        await price_session_extras(repo, sc)
        await repo.upsert_session_cost(sc)
    return result


async def auto_sync_provider(
    repo: AppRepository, provider: ChargingProvider, vin: str, now: datetime
) -> ImportResult:
    """Automatic import of the recent sessions: plausible matches only
    (overlapping, with place and energy fitting); nothing is created."""
    return await apply_provider_import(
        repo, provider, vin, now - AUTO_SYNC_WINDOW, now + timedelta(minutes=1)
    )


# -- one session picked by hand -------------------------------------------------


@dataclass
class LinkCandidate:
    """A provider session offered for a session picked by hand."""

    candidate: ProviderCandidate
    proposed: ChargingSessionCost  # the record once linked
    linked_to: tuple[str, int] | None  # (vin, record id) it's linked to now
    best: bool = False  # the one to propose


async def _row_for(
    repo: AppRepository, vin: str, *, cost_id: int | None, start_ts: datetime | None
) -> ChargeSessionRow:
    """The listed session of a record, or of a session seen only in the
    history (by its start)."""
    if cost_id is not None:
        record = next(
            (c for c in await repo.get_session_costs(vin) if c.id == cost_id), None
        )
        if record is None or record.start_ts is None:
            raise LookupError(f"Session cost {cost_id} not found")
        start_ts = record.start_ts
    if start_ts is None:
        raise LookupError("A record id or a start time is needed")
    start_ts = naive_utc(start_ts)
    rows = await list_sessions(
        repo, vin, start_ts - timedelta(minutes=1), start_ts + timedelta(minutes=1)
    )
    row = next(
        (
            r
            for r in rows
            if (r.record is not None and r.record.id == cost_id)
            or (cost_id is None and r.record is None and r.start_ts == start_ts)
        ),
        None,
    )
    if row is None:
        raise LookupError("Charging session not found")
    return row


async def _sessions_around(
    provider: ChargingProvider, row: ChargeSessionRow
) -> list[ProviderSession]:
    start = naive_utc(row.start_ts)
    sessions = await provider.fetch_sessions(start - CANDIDATE_WINDOW)
    return [
        s for s in sessions if s.started_at and s.started_at <= start + CANDIDATE_WINDOW
    ]


async def find_link_candidates(
    repo: AppRepository,
    provider: ChargingProvider,
    vin: str,
    *,
    cost_id: int | None = None,
    start_ts: datetime | None = None,
) -> list[LinkCandidate]:
    """Provider sessions around a session picked by hand, best first; the
    first one is ``best`` when it overlaps, fits and isn't linked elsewhere."""
    row = await _row_for(repo, vin, cost_id=cost_id, start_ts=start_ts)
    links = await _external_links(repo, provider)
    own = row.record.id if row.record else None
    result = []
    for c in rank_candidates(await _sessions_around(provider, row), row):
        proposed = copy.deepcopy(_record_for_row(vin, row))
        apply_provider_session(proposed, c.session, vehicle_dc=_vehicle_dc(row))
        link = links.get(c.session.external_id)
        result.append(
            LinkCandidate(c, proposed, link if link and link[1] != own else None)
        )
    if result:
        first = result[0]
        first.best = (
            first.candidate.overlap is not None
            and not first.candidate.problems
            and first.linked_to is None
        )
    return result


async def link_provider_session(
    repo: AppRepository,
    provider: ChargingProvider,
    vin: str,
    external_id: str,
    *,
    cost_id: int | None = None,
    start_ts: datetime | None = None,
) -> ChargingSessionCost:
    """Link a session picked by hand to a provider session (confirmed by the
    user: no plausibility check). A provider session linked to another
    record moves here."""
    row = await _row_for(repo, vin, cost_id=cost_id, start_ts=start_ts)
    ps = next(
        (
            s
            for s in await _sessions_around(provider, row)
            if s.external_id == external_id
        ),
        None,
    )
    if ps is None:
        raise LookupError(f"{provider.label} session {external_id} not found")
    sc = _record_for_row(vin, row)
    link = (await _external_links(repo, provider)).get(external_id)
    if link is not None and link[1] != sc.id:
        other_vin, other_id = link
        other = next(
            (c for c in await repo.get_session_costs(other_vin) if c.id == other_id),
            None,
        )
        if other is not None:
            unlink_provider_session(other, disable_auto_link=False)
            await recalculate_session(repo, other)
            await repo.upsert_session_cost(other)
    apply_provider_session(sc, ps, vehicle_dc=_vehicle_dc(row))
    await price_session_extras(repo, sc)
    return await repo.upsert_session_cost(sc)


async def unlink_provider_record(
    repo: AppRepository, vin: str, cost_id: int
) -> ChargingSessionCost:
    """Unlink a record from its provider session: energy and cost go back to
    the measured / tier-priced ones (unless entered by hand), and the
    automatic import won't link it again."""
    sc = next((c for c in await repo.get_session_costs(vin) if c.id == cost_id), None)
    if sc is None:
        raise LookupError(f"Session cost {cost_id} not found")
    unlink_provider_session(sc)
    await recalculate_session(repo, sc)
    return await repo.upsert_session_cost(sc)
