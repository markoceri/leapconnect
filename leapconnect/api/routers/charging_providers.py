"""Charging providers: connect eMSP accounts (EVDC, ...), import their billed
sessions, browse their charging points and the places the vehicle charged."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from leapconnect.api.deps import ContainerDep, RepoDep
from leapconnect.api.routers.charging import _cost_response
from leapconnect.api.schemas.charging import ChargingSessionCostResponse
from leapconnect.api.schemas.charging_providers import (
    ChargeSiteSchema,
    ChargeSitesResponse,
    ChargingStationSchema,
    ChargingStationsResponse,
    ProviderAccountResponse,
    ProviderAccountUpdate,
    ProviderFeeSchema,
    ProviderImportApplyRequest,
    ProviderImportApplyResponse,
    ProviderImportItem,
    ProviderImportPeriod,
    ProviderImportPreviewResponse,
    ProviderLinkCandidate,
    ProviderLinkCandidatesResponse,
    ProviderLinkRequest,
    ProviderLoginRequest,
    ProviderLoginResponse,
    ProviderSessionSchema,
    ProvidersResponse,
    ProviderTypeSchema,
    ProviderVerifyRequest,
)
from leapconnect.application.charging_providers import (
    apply_provider_import,
    charge_sites,
    find_link_candidates,
    find_stations,
    get_session_receipt,
    get_station,
    link_provider_session,
    locate_sessions,
    preview_provider_import,
    unlink_provider_record,
)
from leapconnect.application.ports.charging_provider import (
    ChargingProvider,
    ChargingProviderError,
)
from leapconnect.application.settings_store import load_preferences, resolve_timezone
from leapconnect.domain.charging.providers import ProviderSession
from leapconnect.domain.charging.sessions import month_bounds
from leapconnect.domain.charging.stations import ChargingStation
from leapconnect.infrastructure.charging_providers import (
    PROVIDER_TYPES,
    ChargingProviderRegistry,
)

router = APIRouter(tags=["charging-providers"])

# Charging points search radius (the provider pages its points nearest first)
MAX_STATIONS_RADIUS_M = 10_000


def get_registry(c: ContainerDep) -> ChargingProviderRegistry:
    if not c.charging_providers:
        raise HTTPException(status_code=503, detail="Charging providers not ready")
    return c.charging_providers


RegistryDep = Annotated[ChargingProviderRegistry, Depends(get_registry)]


def _provider_error(exc: ChargingProviderError) -> HTTPException:
    # Not 401: the frontend treats a 401 as an expired LeapConnect session
    return HTTPException(status_code=400 if exc.auth else 502, detail=str(exc))


def _label(provider: str) -> str:
    t = PROVIDER_TYPES.get(provider)
    return t.label if t else provider.upper()


def _account(p: ChargingProvider) -> ProviderAccountResponse:
    account = getattr(p, "account", None)
    return ProviderAccountResponse(
        id=p.account_id or 0,
        provider=p.provider,
        label=p.label,
        username=p.username or "",
        connected=p.connected,
        auto_sync=p.auto_sync,
        last_sync=account.last_sync if account else None,
        last_error=account.last_error if account else None,
    )


def _connected(
    registry: ChargingProviderRegistry, account_id: int | None = None
) -> list[ChargingProvider]:
    """The connected accounts (or the one asked for)."""
    if account_id is not None:
        p = registry.get(account_id)
        if p is None:
            raise HTTPException(status_code=404, detail="Charging provider not found")
        if not p.connected:
            raise HTTPException(
                status_code=409, detail=f"{p.label} account not connected"
            )
        return [p]
    providers = registry.connected()
    if not providers:
        raise HTTPException(status_code=409, detail="No charging provider connected")
    return providers


# -- accounts -------------------------------------------------------------------


@router.get("/api/charging/providers", response_model=ProvidersResponse)
async def list_providers(registry: RegistryDep) -> ProvidersResponse:
    """The supported charging providers and the connected accounts."""
    return ProvidersResponse(
        types=[ProviderTypeSchema(**t.__dict__) for t in PROVIDER_TYPES.values()],
        accounts=[_account(p) for p in registry.all()],
    )


@router.post("/api/charging/providers", response_model=ProviderLoginResponse)
async def connect_provider(
    body: ProviderLoginRequest, registry: RegistryDep
) -> ProviderLoginResponse:
    """Connect a charging provider account (the password is not stored).

    When the account has two-factor authentication, the login waits for the
    code under ``pending_id`` (``/api/charging/providers/pending/{id}/verify``).
    """
    try:
        account, pending_id, method = await registry.login(
            body.provider, body.username, body.password
        )
    except ChargingProviderError as exc:
        raise _provider_error(exc) from exc
    return ProviderLoginResponse(
        account=_account(account) if account else None,
        pending_id=pending_id,
        two_factor_method=method,
    )


@router.post(
    "/api/charging/providers/pending/{pending_id}/verify",
    response_model=ProviderAccountResponse,
)
async def verify_provider(
    pending_id: str, body: ProviderVerifyRequest, registry: RegistryDep
) -> ProviderAccountResponse:
    """Complete a login with its two-factor code."""
    try:
        return _account(await registry.verify(pending_id, body.code.strip()))
    except ChargingProviderError as exc:
        raise _provider_error(exc) from exc


@router.put(
    "/api/charging/providers/{account_id}", response_model=ProviderAccountResponse
)
async def update_provider(
    account_id: int, body: ProviderAccountUpdate, registry: RegistryDep
) -> ProviderAccountResponse:
    """Turn an account's automatic import on or off."""
    p = registry.get(account_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Charging provider not found")
    await p.set_auto_sync(body.auto_sync)
    return _account(p)


@router.delete("/api/charging/providers/{account_id}", status_code=204)
async def remove_provider(account_id: int, registry: RegistryDep) -> Response:
    """Disconnect an account (its device key and session are revoked); the
    sessions imported with it keep their values."""
    if not await registry.remove(account_id):
        raise HTTPException(status_code=404, detail="Charging provider not found")
    return Response(status_code=204)


# -- charging points ---------------------------------------------------------------


def _station_schema(s: ChargingStation) -> ChargingStationSchema:
    return ChargingStationSchema(
        provider=s.provider,
        provider_label=_label(s.provider),
        evse_id=s.evse_id,
        name=s.name,
        operator=s.operator,
        address=s.address,
        latitude=s.latitude,
        longitude=s.longitude,
        max_power_kw=s.max_power_kw,
        is_dc=s.is_dc,
        plugs=list(s.plugs),
        is_open_24h=s.is_open_24h,
        status=s.status,
        price=s.price,
        price_unit=s.price_unit,
        currency=s.currency,
        distance_m=s.distance_m,
    )


@router.get("/api/charging/stations", response_model=ChargingStationsResponse)
async def search_stations(
    registry: RegistryDep,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    radius_m: Annotated[float, Query(gt=0, le=MAX_STATIONS_RADIUS_M)] = 2000,
    providers: str | None = None,
) -> ChargingStationsResponse:
    """The charging points of the connected providers around a point, with
    their live status and price; ``providers``: comma-separated types (all
    when omitted). Several accounts of one provider are searched once."""
    types = {p for p in providers.split(",") if p} if providers else None
    result = await find_stations(registry.connected(), lat, lon, radius_m, types)
    return ChargingStationsResponse(
        stations=[_station_schema(s) for s in result.stations],
        errors={_label(k): v for k, v in result.errors.items()},
    )


@router.get(
    "/api/charging/stations/{provider}/{evse_id}",
    response_model=ChargingStationSchema,
)
async def get_station_details(
    provider: str, evse_id: str, repo: RepoDep, registry: RegistryDep
) -> ChargingStationSchema:
    """A charging point: live from its provider (status, price) when an
    account is connected, else its cached details."""
    station = await get_station(repo, registry.connected(), provider, evse_id)
    if station is None:
        raise HTTPException(status_code=404, detail="Charging point not found")
    return _station_schema(station)


@router.get("/api/vehicles/{vin}/charge-sites", response_model=ChargeSitesResponse)
async def get_charge_sites(
    vin: str, repo: RepoDep, c: ContainerDep
) -> ChargeSitesResponse:
    """The places where the vehicle charged, latest first: sessions, last
    charge, energy, cost and the charging points known there."""
    await locate_sessions(repo, vin, c.located_sessions)
    return ChargeSitesResponse(
        sites=[
            ChargeSiteSchema(
                latitude=s.latitude,
                longitude=s.longitude,
                sessions=s.sessions,
                first_ts=s.first_ts.isoformat() if s.first_ts else None,
                last_ts=s.last_ts.isoformat() if s.last_ts else None,
                energy_kwh=s.energy_kwh,
                cost=s.cost,
                zone_name=s.zone_name,
                tier_id=s.tier_id,
                stations=[_station_schema(st) for st in s.stations],
            )
            for s in await charge_sites(repo, vin)
        ]
    )


# -- import -------------------------------------------------------------------


def _session_schema(
    ps: ProviderSession, registry: ChargingProviderRegistry
) -> ProviderSessionSchema:
    account = registry.get(ps.account_id) if ps.account_id is not None else None
    return ProviderSessionSchema(
        provider=ps.provider,
        provider_label=_label(ps.provider),
        account_id=ps.account_id,
        account_username=account.username if account else None,
        external_id=ps.external_id,
        started_at=ps.started_at.isoformat() if ps.started_at else None,
        ended_at=ps.ended_at.isoformat() if ps.ended_at else None,
        energy_kwh=ps.energy_kwh,
        cost=ps.cost,
        energy_cost=ps.energy_cost,
        currency=ps.currency,
        price_kwh=ps.price_kwh,
        fees=[ProviderFeeSchema(label=f.label, amount=f.amount) for f in ps.fees],
        evse_id=ps.evse_id,
        operator=ps.operator,
        location=ps.location,
        station=_station_schema(ps.station) if ps.station else None,
    )


async def _period(repo, body: ProviderImportPeriod):
    tz = resolve_timezone((await load_preferences(repo)).timezone)
    return month_bounds(body.year, body.month, tz)


@router.post(
    "/api/vehicles/{vin}/charging-costs/import/preview",
    response_model=ProviderImportPreviewResponse,
)
async def preview_import(
    vin: str, body: ProviderImportPeriod, repo: RepoDep, registry: RegistryDep
) -> ProviderImportPreviewResponse:
    """The month's billed sessions of one account (or of every connected
    one), matched with the session list, and what importing them would
    change (nothing is saved)."""
    providers = _connected(registry, body.account_id)
    start, end = await _period(repo, body)
    try:
        items = await preview_provider_import(repo, providers, vin, start, end)
    except ChargingProviderError as exc:
        raise _provider_error(exc) from exc
    tiers = {t.id: t for t in await repo.get_price_tiers()}
    return ProviderImportPreviewResponse(
        items=[
            ProviderImportItem(
                status=i.match.status,
                session=_session_schema(i.match.session, registry),
                row_start_ts=i.match.row.start_ts.isoformat() if i.match.row else None,
                row_end_ts=i.match.row.end_ts.isoformat()
                if i.match.row and i.match.row.end_ts
                else None,
                current=_cost_response(i.current, tiers, {})
                if i.current and i.current.id
                else None,
                proposed=_cost_response(i.proposed, tiers, {}) if i.proposed else None,
                energy_kept=i.energy_kept,
                cost_kept=i.cost_kept,
                problems=list(i.match.problems),
            )
            for i in items
        ],
    )


@router.post(
    "/api/vehicles/{vin}/charging-costs/import/apply",
    response_model=ProviderImportApplyResponse,
)
async def apply_import(
    vin: str, body: ProviderImportApplyRequest, repo: RepoDep, registry: RegistryDep
) -> ProviderImportApplyResponse:
    """Import the month's billed sessions: the matched ones (or those in
    ``external_ids``) update their record, the unmatched ones in
    ``create_ids`` are created."""
    providers = _connected(registry, body.account_id)
    start, end = await _period(repo, body)
    try:
        result = await apply_provider_import(
            repo,
            providers,
            vin,
            start,
            end,
            external_ids=set(body.external_ids)
            if body.external_ids is not None
            else None,
            create_ids=set(body.create_ids),
        )
    except ChargingProviderError as exc:
        raise _provider_error(exc) from exc
    return ProviderImportApplyResponse(
        applied=result.applied, created=result.created, skipped=len(result.skipped)
    )


# -- one session picked by hand --------------------------------------------------


async def _cost_out(repo, sc):
    tiers = {t.id: t for t in await repo.get_price_tiers()}
    bands = {b.id: b for b in await repo.get_time_bands("home_grid")}
    return _cost_response(sc, tiers, bands)


@router.get(
    "/api/vehicles/{vin}/charging-costs/link/candidates",
    response_model=ProviderLinkCandidatesResponse,
)
async def get_link_candidates(
    vin: str,
    repo: RepoDep,
    registry: RegistryDep,
    cost_id: int | None = None,
    start_ts: datetime | None = None,
) -> ProviderLinkCandidatesResponse:
    """The connected accounts' billed sessions around a session (its record,
    or its start when seen only in the history), best first, with what
    linking each would change."""
    try:
        found = await find_link_candidates(
            repo, _connected(registry), vin, cost_id=cost_id, start_ts=start_ts
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ChargingProviderError as exc:
        raise _provider_error(exc) from exc
    tiers = {t.id: t for t in await repo.get_price_tiers()}
    return ProviderLinkCandidatesResponse(
        candidates=[
            ProviderLinkCandidate(
                session=_session_schema(c.candidate.session, registry),
                overlap_minutes=int(c.candidate.overlap.total_seconds() // 60)
                if c.candidate.overlap is not None
                else None,
                problems=list(c.candidate.problems),
                best=c.best,
                linked_vin=c.linked_to[0] if c.linked_to else None,
                linked_cost_id=c.linked_to[1] if c.linked_to else None,
                proposed=_cost_response(c.proposed, tiers, {}),
            )
            for c in found
        ],
    )


@router.post(
    "/api/vehicles/{vin}/charging-costs/link",
    response_model=ChargingSessionCostResponse,
)
async def link_session(
    vin: str, body: ProviderLinkRequest, repo: RepoDep, registry: RegistryDep
) -> ChargingSessionCostResponse:
    """Link a session to the billed session the user picked: its billed
    values are applied (values entered by hand are kept)."""
    [provider] = _connected(registry, body.account_id)
    try:
        sc = await link_provider_session(
            repo,
            provider,
            vin,
            body.external_id,
            cost_id=body.cost_id,
            start_ts=datetime.fromisoformat(body.start_ts) if body.start_ts else None,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ChargingProviderError as exc:
        raise _provider_error(exc) from exc
    return await _cost_out(repo, sc)


@router.delete(
    "/api/vehicles/{vin}/charging-costs/{cost_id}/link",
    response_model=ChargingSessionCostResponse,
)
async def unlink_session(
    vin: str, cost_id: int, repo: RepoDep
) -> ChargingSessionCostResponse:
    """Unlink a session from its billed session: energy and cost go back to
    the automatic ones (unless entered by hand), and the automatic import
    won't link it again."""
    try:
        sc = await unlink_provider_record(repo, vin, cost_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await _cost_out(repo, sc)


@router.get("/api/vehicles/{vin}/charging-costs/{cost_id}/receipt")
async def get_receipt(
    vin: str, cost_id: int, repo: RepoDep, registry: RegistryDep
) -> Response:
    """The PDF receipt of a session imported from a charging provider."""
    try:
        sc, filename, content = await get_session_receipt(
            repo, registry.all(), vin, cost_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ChargingProviderError as exc:
        raise _provider_error(exc) from exc
    name = filename or f"{sc.external_source}-receipt-{sc.external_id}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{name}"'},
    )
