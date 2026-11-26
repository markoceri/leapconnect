"""Import the sessions the charging providers billed into the cost records.

The sessions of the chosen provider accounts are matched with the period's
session list (the one the Charging tab shows); a preview shows what would
change, and applying it sets the billed energy, cost and fees on the matched
records — values entered by hand are kept. Provider sessions the vehicle
history doesn't show are only created on request.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from leapconnect.application.charging_costs import list_sessions
from leapconnect.application.ports.charging_provider import (
    ChargingProvider,
    ChargingProviderError,
)
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
    ProviderOngoingSession,
    ProviderSession,
    apply_provider_session,
    match_provider_sessions,
    new_record_for,
    ongoing_problems,
    rank_candidates,
    unlink_provider_session,
)
from leapconnect.domain.charging.sessions import ChargeSessionRow, naive_utc
from leapconnect.domain.charging.stations import (
    ChargeSite,
    ChargingStation,
    group_charge_sites,
    unique_by_evse,
)

if TYPE_CHECKING:
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
    repo: AppRepository, providers: Sequence[ChargingProvider]
) -> dict[tuple[str, str], tuple[str, int]]:
    """Records imported from the providers' types, any vehicle:
    ``{(provider, external_id): (vin, record id)}``."""
    links = {}
    for name in dict.fromkeys(p.provider for p in providers):
        for eid, link in (await repo.get_external_links(name)).items():
            links[(name, eid)] = link
    return links


def _linked_elsewhere(
    links: dict[tuple[str, str], tuple[str, int]], rows: list[ChargeSessionRow]
) -> set[tuple[str, str]]:
    """Provider sessions linked to a record not among ``rows`` (another
    vehicle's, or outside the period): not to be linked again."""
    here = {r.record.id for r in rows if r.record is not None}
    return {key for key, (_vin, cid) in links.items() if cid not in here}


async def _fetch(
    providers: Sequence[ChargingProvider], since: datetime
) -> list[ProviderSession]:
    """The sessions of every account, oldest first; one session read
    through two accounts counts once."""
    sessions: dict[tuple[str, str], ProviderSession] = {}
    for provider in providers:
        for s in await provider.fetch_sessions(since):
            sessions.setdefault(s.key, s)
    return sorted(sessions.values(), key=lambda s: s.started_at or datetime.min)


async def _save_stations(repo: AppRepository, sessions: list[ProviderSession]) -> None:
    """Cache the charging points the sessions were billed on."""
    await repo.upsert_charging_stations(
        unique_by_evse([s.station for s in sessions if s.station is not None])
    )


async def _matches(
    repo: AppRepository,
    providers: Sequence[ChargingProvider],
    vin: str,
    start: datetime,
    end: datetime,
) -> list[ProviderMatch]:
    sessions = await _fetch(providers, start - FETCH_MARGIN)
    sessions = [s for s in sessions if s.started_at is not None and s.started_at < end]
    rows = await list_sessions(repo, vin, start - FETCH_MARGIN, end)
    elsewhere = _linked_elsewhere(await _external_links(repo, providers), rows)
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
    providers: Sequence[ChargingProvider],
    vin: str,
    start: datetime,
    end: datetime,
) -> list[ImportPreviewItem]:
    """What importing the providers' sessions of ``[start, end)`` would do."""
    return [_preview(vin, m) for m in await _matches(repo, providers, vin, start, end)]


async def apply_provider_import(
    repo: AppRepository,
    providers: Sequence[ChargingProvider],
    vin: str,
    start: datetime,
    end: datetime,
    *,
    external_ids: set[str] | None = None,
    create_ids: set[str] | frozenset[str] = frozenset(),
) -> ImportResult:
    """Import the providers' sessions of ``[start, end)``.

    Matched (and already imported) sessions update their record — all of them
    when ``external_ids`` is ``None``, else the ones in it. Uncertain matches
    (place or energy don't fit: maybe another vehicle's charge) and the ones
    the user unlinked are imported only when in ``external_ids``; unmatched
    ones are created only when in ``create_ids``; sessions linked to another
    record are never touched.
    """
    result = ImportResult()
    imported = []
    for m in await _matches(repo, providers, vin, start, end):
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
        imported.append(ps)
    await _save_stations(repo, imported)
    return result


async def auto_sync_provider(
    repo: AppRepository, provider: ChargingProvider, vin: str, now: datetime
) -> ImportResult:
    """Automatic import of the recent sessions: plausible matches only
    (overlapping, with place and energy fitting); nothing is created."""
    return await apply_provider_import(
        repo, [provider], vin, now - AUTO_SYNC_WINDOW, now + timedelta(minutes=1)
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
    providers: Sequence[ChargingProvider], row: ChargeSessionRow
) -> list[ProviderSession]:
    start = naive_utc(row.start_ts)
    sessions = await _fetch(providers, start - CANDIDATE_WINDOW)
    return [
        s for s in sessions if s.started_at and s.started_at <= start + CANDIDATE_WINDOW
    ]


async def find_link_candidates(
    repo: AppRepository,
    providers: Sequence[ChargingProvider],
    vin: str,
    *,
    cost_id: int | None = None,
    start_ts: datetime | None = None,
) -> list[LinkCandidate]:
    """The accounts' sessions around a session picked by hand, best first;
    the first one is ``best`` when it overlaps, fits and isn't linked
    elsewhere."""
    row = await _row_for(repo, vin, cost_id=cost_id, start_ts=start_ts)
    links = await _external_links(repo, providers)
    own = row.record.id if row.record else None
    result = []
    for c in rank_candidates(await _sessions_around(providers, row), row):
        proposed = copy.deepcopy(_record_for_row(vin, row))
        apply_provider_session(proposed, c.session, vehicle_dc=_vehicle_dc(row))
        link = links.get(c.session.key)
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
            for s in await _sessions_around([provider], row)
            if s.external_id == external_id
        ),
        None,
    )
    if ps is None:
        raise LookupError(f"{provider.label} session {external_id} not found")
    sc = _record_for_row(vin, row)
    link = (await _external_links(repo, [provider])).get(
        (provider.provider, external_id)
    )
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
    await _save_stations(repo, [ps])
    return await repo.upsert_session_cost(sc)


async def unlink_provider_record(
    repo: AppRepository, vin: str, cost_id: int
) -> ChargingSessionCost:
    """Unlink a record from its provider session: energy and cost go back to
    the measured / tier-priced ones (unless entered by hand), and the
    automatic import won't link it again."""
    sc = await _record(repo, vin, cost_id)
    unlink_provider_session(sc)
    await recalculate_session(repo, sc)
    return await repo.upsert_session_cost(sc)


async def _record(repo: AppRepository, vin: str, cost_id: int) -> ChargingSessionCost:
    sc = next((c for c in await repo.get_session_costs(vin) if c.id == cost_id), None)
    if sc is None:
        raise LookupError(f"Session cost {cost_id} not found")
    return sc


def _account_for(
    providers: Sequence[ChargingProvider], sc: ChargingSessionCost
) -> ChargingProvider:
    """The account a record was imported with, else a connected one of the
    same provider (removed and connected again, it has a new id)."""
    if not sc.external_source or not sc.external_id:
        raise LookupError("Session not imported from a charging provider")
    same = [p for p in providers if p.provider == sc.external_source and p.connected]
    own = next((p for p in same if p.account_id == sc.provider_account_id), None)
    if own is None and not same:
        raise ChargingProviderError(
            f"No {sc.external_source.upper()} account connected", auth=True
        )
    return own or same[0]


async def get_session_receipt(
    repo: AppRepository, providers: Sequence[ChargingProvider], vin: str, cost_id: int
) -> tuple[ChargingSessionCost, str | None, bytes]:
    """The PDF receipt of an imported session: ``(record, filename, PDF)``."""
    sc = await _record(repo, vin, cost_id)
    filename, content = await _account_for(providers, sc).get_receipt(sc.external_id)
    return sc, filename, content


# -- charging points -----------------------------------------------------------


def _one_per_type(providers: Sequence[ChargingProvider]) -> list[ChargingProvider]:
    """One connected account per provider type: the network is the same."""
    by_type: dict[str, ChargingProvider] = {}
    for p in providers:
        if p.connected:
            by_type.setdefault(p.provider, p)
    return list(by_type.values())


@dataclass
class StationsResult:
    stations: list[ChargingStation] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)  # provider -> message


async def find_stations(
    providers: Sequence[ChargingProvider],
    latitude: float,
    longitude: float,
    radius_m: float,
    types: set[str] | None = None,
) -> StationsResult:
    """The charging points within ``radius_m`` of a point, of each provider
    type (``types``: only those), with their live status and price. A
    provider failing doesn't hide the others."""
    result = StationsResult()
    for p in _one_per_type(providers):
        if types is not None and p.provider not in types:
            continue
        try:
            result.stations += await p.find_stations(latitude, longitude, radius_m)
        except ChargingProviderError as exc:
            result.errors[p.provider] = str(exc)
    result.stations = unique_by_evse(result.stations)
    return result


async def get_station(
    repo: AppRepository,
    providers: Sequence[ChargingProvider],
    provider: str,
    evse_id: str,
) -> ChargingStation | None:
    """A charging point: live from its provider when an account is
    connected (and its details cached), else as cached."""
    live = next((p for p in _one_per_type(providers) if p.provider == provider), None)
    if live is not None:
        try:
            station = await live.get_station(evse_id)
        except ChargingProviderError:
            station = None
        if station is not None:
            await repo.upsert_charging_stations([station])
            return station
    return (await repo.get_charging_stations([(provider, evse_id)])).get(
        (provider, evse_id)
    )


# -- charge sites ----------------------------------------------------------------


async def locate_sessions(
    repo: AppRepository, vin: str, checked: set[int] | None = None
) -> None:
    """Find where the closed sessions without a position charged (from the
    vehicle history); ``checked``: record ids already looked for, skipped
    and updated (a session without GPS stays without)."""
    checked = checked if checked is not None else set()
    missing = [
        sc
        for sc in await repo.get_session_costs(vin)
        if sc.latitude is None
        and sc.start_ts is not None
        and sc.end_ts is not None
        and sc.id not in checked
    ]
    if not missing:
        return
    # One look at the history per month with sessions to locate
    months: dict[tuple[int, int], list[ChargingSessionCost]] = {}
    for sc in missing:
        months.setdefault((sc.start_ts.year, sc.start_ts.month), []).append(sc)
    for group in months.values():
        start = min(naive_utc(sc.start_ts) for sc in group)
        end = max(naive_utc(sc.start_ts) for sc in group)
        # list_sessions stores the position of the records it pairs
        await list_sessions(
            repo, vin, start - timedelta(minutes=1), end + timedelta(minutes=1)
        )
        checked.update(sc.id for sc in group)


async def charge_sites(repo: AppRepository, vin: str) -> list[ChargeSite]:
    """The places where the vehicle charged, latest first, with the charging
    points known there."""
    records = await repo.get_session_costs(vin)
    keys = list(
        {
            (r.external_source, r.evse_id)
            for r in records
            if r.external_source and r.evse_id
        }
    )
    stations = await repo.get_charging_stations(keys) if keys else {}
    return group_charge_sites(records, stations)


# -- sessions in progress --------------------------------------------------------


@dataclass
class OngoingItem:
    """A provider session in progress and the vehicle's charge it may be."""

    session: ProviderOngoingSession
    row: ChargeSessionRow | None  # the vehicle's open charge, if charging
    problems: tuple[str, ...] = ()  # why it may be another vehicle's charge
    linked_to: tuple[str, int] | None = None  # already linked (another record)

    @property
    def plausible(self) -> bool:
        return not self.problems and self.linked_to is None

    @property
    def estimate_energy_kwh(self) -> float | None:
        """The energy the cost so far is estimated on: the charger's live
        reading (what gets billed), else what the car took so far."""
        live = self.session.live
        if live is not None and live.energy_kwh is not None:
            return live.energy_kwh
        return self.row.energy_kwh if self.row else None

    @property
    def estimated_cost(self) -> float | None:
        """The tariff × the energy so far."""
        energy = self.estimate_energy_kwh
        if self.session.price_kwh is None or energy is None:
            return None
        return round(self.session.price_kwh * energy, 2)


@dataclass
class OngoingResult:
    items: list[OngoingItem] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)  # provider -> message


async def _with_station(
    repo: AppRepository, provider: ChargingProvider, o: ProviderOngoingSession
) -> ProviderOngoingSession:
    """The session with its charging point: as it came, cached, or read."""
    if o.station is not None or not o.evse_id:
        if o.station is not None:
            await repo.upsert_charging_stations([o.station])
        return o
    key = (o.provider, o.evse_id)
    station = (await repo.get_charging_stations([key])).get(key)
    if station is None:
        try:
            station = await provider.get_station(o.evse_id)
        except ChargingProviderError:
            station = None
        if station is not None:
            await repo.upsert_charging_stations([station])
    return replace(o, station=station) if station is not None else o


async def ongoing_provider_sessions(
    repo: AppRepository,
    providers: Sequence[ChargingProvider],
    vin: str,
    now: datetime,
) -> OngoingResult:
    """The connected accounts' sessions in progress, each with the vehicle's
    open charge and why it may not be this vehicle's (``problems``): the car
    isn't charging, or the charger is far from it."""
    result = OngoingResult()
    sessions: dict[tuple[str, str], tuple[ChargingProvider, ProviderOngoingSession]]
    sessions = {}
    for p in providers:
        if not p.connected:
            continue
        try:
            for o in await p.get_ongoing_sessions():
                sessions.setdefault(o.key, (p, o))
        except ChargingProviderError as exc:
            result.errors[p.provider] = str(exc)
    if not sessions:
        return result
    rows = await list_sessions(repo, vin, now - timedelta(days=2), now)
    row = next((r for r in rows if r.end_ts is None), None)
    links = await _external_links(repo, [p for p, _o in sessions.values()])
    own = row.record.id if row and row.record else None
    for p, o in sessions.values():
        o = await _with_station(repo, p, o)
        link = links.get(o.key)
        result.items.append(
            OngoingItem(
                o,
                row,
                ongoing_problems(o, row),
                link if link and link[1] != own else None,
            )
        )
    return result
