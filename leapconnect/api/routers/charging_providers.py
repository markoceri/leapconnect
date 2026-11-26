"""Charging providers: connect an EVDC account and import its billed sessions."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from evdc_network_api import EvdcApiError, EvdcAuthError
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from leapconnect.api.deps import ContainerDep, RepoDep
from leapconnect.api.routers.charging import _cost_response
from leapconnect.api.schemas.charging import ChargingSessionCostResponse
from leapconnect.api.schemas.charging_providers import (
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
    ProviderSessionSchema,
    ProviderSettingsUpdate,
    ProviderStatusResponse,
    ProviderVerifyRequest,
)
from leapconnect.application.charging_providers import (
    apply_provider_import,
    find_link_candidates,
    link_provider_session,
    preview_provider_import,
    unlink_provider_record,
)
from leapconnect.application.settings_store import load_preferences, resolve_timezone
from leapconnect.domain.charging.providers import ProviderSession
from leapconnect.domain.charging.sessions import month_bounds
from leapconnect.infrastructure.evdc.service import EvdcService

router = APIRouter(tags=["charging-providers"])


def get_evdc(c: ContainerDep) -> EvdcService:
    if not c.evdc_service:
        raise HTTPException(status_code=503, detail="EVDC provider not ready")
    return c.evdc_service


EvdcDep = Annotated[EvdcService, Depends(get_evdc)]


def _connected(evdc: EvdcService) -> EvdcService:
    if not evdc.connected:
        raise HTTPException(status_code=409, detail="No EVDC account connected")
    return evdc


def _status(evdc: EvdcService) -> ProviderStatusResponse:
    return ProviderStatusResponse(
        provider=evdc.name, label=evdc.label, **evdc.status_dict()
    )


def _provider_error(exc: EvdcApiError) -> HTTPException:
    # Not 401: the frontend treats a 401 as an expired LeapConnect session
    status = 400 if isinstance(exc, EvdcAuthError) else 502
    return HTTPException(status_code=status, detail=f"EVDC: {exc}")


@router.get("/api/charging/providers/evdc", response_model=ProviderStatusResponse)
async def get_evdc_status(evdc: EvdcDep) -> ProviderStatusResponse:
    """Whether an EVDC account is connected, and the automatic import."""
    return _status(evdc)


@router.put("/api/charging/providers/evdc", response_model=ProviderStatusResponse)
async def update_evdc_settings(
    body: ProviderSettingsUpdate, evdc: EvdcDep
) -> ProviderStatusResponse:
    """Turn the automatic import of the billed sessions on or off."""
    await evdc.set_auto_sync(body.auto_sync)
    return _status(evdc)


@router.post(
    "/api/charging/providers/evdc/session", response_model=ProviderStatusResponse
)
async def connect_evdc(
    body: ProviderLoginRequest, evdc: EvdcDep
) -> ProviderStatusResponse:
    """Connect an EVDC account (the password is not stored).

    When the account has two-factor authentication, ``two_factor_pending``
    tells which code to send to ``/session/verify``.
    """
    try:
        await evdc.login(body.email, body.password)
    except EvdcApiError as exc:
        raise _provider_error(exc) from exc
    return _status(evdc)


@router.post(
    "/api/charging/providers/evdc/session/verify",
    response_model=ProviderStatusResponse,
)
async def verify_evdc(
    body: ProviderVerifyRequest, evdc: EvdcDep
) -> ProviderStatusResponse:
    """Complete the login with the two-factor code."""
    try:
        await evdc.verify(body.code.strip())
    except EvdcApiError as exc:
        raise _provider_error(exc) from exc
    return _status(evdc)


@router.delete(
    "/api/charging/providers/evdc/session", response_model=ProviderStatusResponse
)
async def disconnect_evdc(evdc: EvdcDep) -> ProviderStatusResponse:
    """Disconnect the account: its device key and session are revoked."""
    await evdc.disconnect()
    return _status(evdc)


# -- import -------------------------------------------------------------------


def _session_schema(ps: ProviderSession) -> ProviderSessionSchema:
    return ProviderSessionSchema(
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
    )


async def _period(repo, body: ProviderImportPeriod):
    tz = resolve_timezone((await load_preferences(repo)).timezone)
    return month_bounds(body.year, body.month, tz)


@router.post(
    "/api/vehicles/{vin}/charging-costs/import/evdc/preview",
    response_model=ProviderImportPreviewResponse,
)
async def preview_evdc_import(
    vin: str, body: ProviderImportPeriod, repo: RepoDep, evdc: EvdcDep
) -> ProviderImportPreviewResponse:
    """The month's EVDC sessions, matched with the session list, and what
    importing them would change (nothing is saved)."""
    start, end = await _period(repo, body)
    try:
        items = await preview_provider_import(repo, _connected(evdc), vin, start, end)
    except EvdcApiError as exc:
        raise _provider_error(exc) from exc
    tiers = {t.id: t for t in await repo.get_price_tiers()}
    return ProviderImportPreviewResponse(
        provider=evdc.name,
        items=[
            ProviderImportItem(
                status=i.match.status,
                session=_session_schema(i.match.session),
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
    "/api/vehicles/{vin}/charging-costs/import/evdc/apply",
    response_model=ProviderImportApplyResponse,
)
async def apply_evdc_import(
    vin: str, body: ProviderImportApplyRequest, repo: RepoDep, evdc: EvdcDep
) -> ProviderImportApplyResponse:
    """Import the month's EVDC sessions: the matched ones (or those in
    ``external_ids``) update their record, the unmatched ones in
    ``create_ids`` are created."""
    start, end = await _period(repo, body)
    try:
        result = await apply_provider_import(
            repo,
            _connected(evdc),
            vin,
            start,
            end,
            external_ids=set(body.external_ids)
            if body.external_ids is not None
            else None,
            create_ids=set(body.create_ids),
        )
    except EvdcApiError as exc:
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
    "/api/vehicles/{vin}/charging-costs/link/evdc/candidates",
    response_model=ProviderLinkCandidatesResponse,
)
async def get_evdc_link_candidates(
    vin: str,
    repo: RepoDep,
    evdc: EvdcDep,
    cost_id: int | None = None,
    start_ts: datetime | None = None,
) -> ProviderLinkCandidatesResponse:
    """EVDC sessions around a session (its record, or its start when seen
    only in the history), best first, with what linking each would change."""
    try:
        found = await find_link_candidates(
            repo, _connected(evdc), vin, cost_id=cost_id, start_ts=start_ts
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EvdcApiError as exc:
        raise _provider_error(exc) from exc
    tiers = {t.id: t for t in await repo.get_price_tiers()}
    return ProviderLinkCandidatesResponse(
        provider=evdc.name,
        candidates=[
            ProviderLinkCandidate(
                session=_session_schema(c.candidate.session),
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
    "/api/vehicles/{vin}/charging-costs/link/evdc",
    response_model=ChargingSessionCostResponse,
)
async def link_evdc_session(
    vin: str, body: ProviderLinkRequest, repo: RepoDep, evdc: EvdcDep
) -> ChargingSessionCostResponse:
    """Link a session to the EVDC session the user picked: its billed values
    are applied (values entered by hand are kept)."""
    try:
        sc = await link_provider_session(
            repo,
            _connected(evdc),
            vin,
            body.external_id,
            cost_id=body.cost_id,
            start_ts=datetime.fromisoformat(body.start_ts) if body.start_ts else None,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EvdcApiError as exc:
        raise _provider_error(exc) from exc
    return await _cost_out(repo, sc)


@router.delete(
    "/api/vehicles/{vin}/charging-costs/{cost_id}/link",
    response_model=ChargingSessionCostResponse,
)
async def unlink_session(
    vin: str, cost_id: int, repo: RepoDep
) -> ChargingSessionCostResponse:
    """Unlink a session from its provider session: energy and cost go back to
    the automatic ones (unless entered by hand), and the automatic import
    won't link it again."""
    try:
        sc = await unlink_provider_record(repo, vin, cost_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await _cost_out(repo, sc)


@router.get("/api/vehicles/{vin}/charging-costs/{cost_id}/receipt")
async def get_session_receipt(
    vin: str, cost_id: int, repo: RepoDep, evdc: EvdcDep
) -> Response:
    """The PDF receipt of a session imported from EVDC."""
    sc = next((c for c in await repo.get_session_costs(vin) if c.id == cost_id), None)
    if sc is None:
        raise HTTPException(status_code=404, detail=f"Session cost {cost_id} not found")
    if sc.external_source != evdc.name or not sc.external_id:
        raise HTTPException(status_code=404, detail="Session not imported from EVDC")
    try:
        filename, content = await _connected(evdc).get_receipt(sc.external_id)
    except EvdcApiError as exc:
        raise _provider_error(exc) from exc
    name = filename or f"evdc-receipt-{sc.external_id}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{name}"'},
    )
