"""Charging routes: cloud history, consumption stats, tiers, bands, costs."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, HTTPException

from leapconnect.api.deps import ClientDep, RepoDep, VehicleDep
from leapconnect.api.schemas import (
    ChargingHistoryResponse,
    ChargingPriceTierResponse,
    ChargingPriceTierUpdate,
    ChargingSessionCostCreate,
    ChargingSessionCostResponse,
    ChargingSessionCostUpdate,
    ChargingTiersFullResponse,
    ChargingTimeBandCreate,
    ChargingTimeBandResponse,
    ChargingTimeBandUpdate,
    ConsumptionLastWeekResponse,
    ConsumptionWeeklyRankResponse,
)
from leapconnect.application.settings_store import (
    calculate_session_cost,
    load_preferences,
    recalculate_session,
)
from leapconnect.domain.charging.models import ChargingSessionCost, ChargingTimeBand

router = APIRouter(tags=["charging"])


# ---------------------------------------------------------------------------
# Cloud data
# ---------------------------------------------------------------------------


@router.get(
    "/api/vehicles/{vin}/charging-history", response_model=ChargingHistoryResponse
)
async def get_charging_history(
    vin: str,
    client: ClientDep,
    start: str | None = None,
    end: str | None = None,
    timezone: str = "GMT+00:00",
    page: int = 1,
    size: int = 10,
) -> ChargingHistoryResponse:
    """Get paginated charging session history."""
    today = date.today()
    start_date = date.fromisoformat(start) if start else today.replace(day=1)
    end_date = date.fromisoformat(end) if end else today
    result = await client.get_charging_daily_detail(
        vin,
        start_time=start_date,
        end_time=end_date,
        timezone=timezone,
        page_num=page,
        page_size=size,
    )
    return ChargingHistoryResponse.from_result(result.records, page, size)


@router.get(
    "/api/vehicles/{vin}/consumption/weekly-rank",
    response_model=ConsumptionWeeklyRankResponse,
)
async def get_consumption_weekly_rank(
    vin: str, client: ClientDep, vehicle: VehicleDep
) -> ConsumptionWeeklyRankResponse:
    """Get weekly energy consumption ranking."""
    result = await client.get_consumption_weekly_rank(vehicle)
    return ConsumptionWeeklyRankResponse.from_model(result)


@router.get(
    "/api/vehicles/{vin}/consumption/last-week",
    response_model=ConsumptionLastWeekResponse,
)
async def get_consumption_last_week(
    vin: str, client: ClientDep, vehicle: VehicleDep
) -> ConsumptionLastWeekResponse:
    """Get last week energy consumption breakdown."""
    result = await client.get_consumption_last_week_breakdown(vehicle)
    return ConsumptionLastWeekResponse.from_model(result)


# ---------------------------------------------------------------------------
# Price tiers & time bands
# ---------------------------------------------------------------------------


def _band_response(b: ChargingTimeBand) -> ChargingTimeBandResponse:
    return ChargingTimeBandResponse(
        id=b.id,
        tier_id=b.tier_id,
        name=b.name,
        price_kwh=b.price_kwh,
        schedule=b.schedule,
        color=b.color,
        position=b.position,
    )


@router.get("/api/charging/tiers", response_model=ChargingTiersFullResponse)
async def get_charging_tiers(repo: RepoDep) -> ChargingTiersFullResponse:
    """Get all charging price tiers and time bands."""
    prefs = await load_preferences(repo)
    tiers = await repo.get_price_tiers()
    # Hide home_solar if user has no solar panels
    if not prefs.has_solar_panels:
        tiers = [t for t in tiers if t.id != "home_solar"]
    bands = await repo.get_time_bands("home_grid")
    return ChargingTiersFullResponse(
        tiers=[
            ChargingPriceTierResponse(
                id=t.id, label=t.label, price_kwh=t.price_kwh, enabled=t.enabled
            )
            for t in tiers
        ],
        time_bands=[_band_response(b) for b in bands],
        home_pricing_mode=prefs.home_pricing_mode,
    )


@router.put("/api/charging/tiers/{tier_id}", response_model=ChargingPriceTierResponse)
async def update_charging_tier(
    tier_id: str, body: ChargingPriceTierUpdate, repo: RepoDep
) -> ChargingPriceTierResponse:
    """Update a charging price tier."""
    tiers = await repo.get_price_tiers()
    tier = next((t for t in tiers if t.id == tier_id), None)
    if not tier:
        raise HTTPException(status_code=404, detail=f"Tier '{tier_id}' not found")
    if body.label is not None:
        tier.label = body.label
    if body.price_kwh is not None:
        if body.price_kwh < 0:
            raise HTTPException(status_code=422, detail="price_kwh must be >= 0")
        tier.price_kwh = body.price_kwh
    if body.enabled is not None:
        tier.enabled = body.enabled
    await repo.upsert_price_tier(tier)
    return ChargingPriceTierResponse(
        id=tier.id, label=tier.label, price_kwh=tier.price_kwh, enabled=tier.enabled
    )


@router.get("/api/charging/time-bands", response_model=list[ChargingTimeBandResponse])
async def get_time_bands(repo: RepoDep) -> list[ChargingTimeBandResponse]:
    """Get all time-of-use bands."""
    bands = await repo.get_time_bands("home_grid")
    return [_band_response(b) for b in bands]


@router.post(
    "/api/charging/time-bands",
    response_model=ChargingTimeBandResponse,
    status_code=201,
)
async def create_time_band(
    body: ChargingTimeBandCreate, repo: RepoDep
) -> ChargingTimeBandResponse:
    """Create a new time-of-use band."""
    # Determine position (append at end)
    existing = await repo.get_time_bands("home_grid")
    position = (
        body.position
        if body.position is not None
        else (max((b.position for b in existing), default=0) + 1)
    )
    band = ChargingTimeBand(
        tier_id="home_grid",
        name=body.name,
        price_kwh=body.price_kwh,
        schedule=[s.model_dump() for s in body.schedule],
        color=body.color,
        position=position,
    )
    band = await repo.upsert_time_band(band)
    return _band_response(band)


@router.put(
    "/api/charging/time-bands/{band_id}", response_model=ChargingTimeBandResponse
)
async def update_time_band(
    band_id: int, body: ChargingTimeBandUpdate, repo: RepoDep
) -> ChargingTimeBandResponse:
    """Update a time-of-use band."""
    bands = await repo.get_time_bands("home_grid")
    band = next((b for b in bands if b.id == band_id), None)
    if not band:
        raise HTTPException(status_code=404, detail=f"Time band {band_id} not found")
    if body.name is not None:
        band.name = body.name
    if body.price_kwh is not None:
        if body.price_kwh < 0:
            raise HTTPException(status_code=422, detail="price_kwh must be >= 0")
        band.price_kwh = body.price_kwh
    if body.schedule is not None:
        band.schedule = [s.model_dump() for s in body.schedule]
    if body.color is not None:
        band.color = body.color
    if body.position is not None:
        band.position = body.position
    await repo.upsert_time_band(band)
    return _band_response(band)


@router.delete("/api/charging/time-bands/{band_id}")
async def delete_time_band_endpoint(band_id: int, repo: RepoDep):
    """Delete a time-of-use band."""
    deleted = await repo.delete_time_band(band_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Time band {band_id} not found")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Session costs
# ---------------------------------------------------------------------------


def _cost_response(
    sc: ChargingSessionCost, tiers: dict, bands: dict
) -> ChargingSessionCostResponse:
    tier = tiers.get(sc.tier_id)
    return ChargingSessionCostResponse(
        id=sc.id,
        vin=sc.vin,
        start_ts=sc.start_ts.isoformat() if sc.start_ts else "",
        end_ts=sc.end_ts.isoformat() if sc.end_ts else None,
        tier_id=sc.tier_id,
        tier_label=tier.label if tier else None,
        time_band_id=sc.time_band_id,
        time_band_name=bands[sc.time_band_id].name
        if sc.time_band_id and sc.time_band_id in bands
        else None,
        energy_kwh=sc.energy_kwh,
        peak_power_kw=sc.peak_power_kw,
        cost=sc.cost,
        note=sc.note,
        zone_name=sc.zone_name,
    )


@router.get(
    "/api/vehicles/{vin}/charging-costs",
    response_model=list[ChargingSessionCostResponse],
)
async def get_charging_costs(
    vin: str, repo: RepoDep, start: str | None = None, end: str | None = None
):
    """Get charging session costs for a vehicle."""
    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None
    costs = await repo.get_session_costs(vin, start=start_dt, end=end_dt)
    # Enrich with tier/band labels
    tiers = {t.id: t for t in await repo.get_price_tiers()}
    bands = {b.id: b for b in await repo.get_time_bands("home_grid")}
    return [_cost_response(c, tiers, bands) for c in costs]


@router.post(
    "/api/vehicles/{vin}/charging-costs",
    response_model=ChargingSessionCostResponse,
    status_code=201,
)
async def create_charging_cost(
    vin: str, body: ChargingSessionCostCreate, repo: RepoDep
):
    """Assign a cost tier to a charging session."""
    start_ts = datetime.fromisoformat(body.start_ts)
    end_ts = datetime.fromisoformat(body.end_ts) if body.end_ts else None
    # Validate tier exists
    tiers = {t.id: t for t in await repo.get_price_tiers()}
    if body.tier_id not in tiers:
        raise HTTPException(status_code=422, detail=f"Unknown tier: {body.tier_id}")
    # Calculate cost
    cost = None
    if body.energy_kwh is not None:
        cost = await calculate_session_cost(
            repo, body.tier_id, body.energy_kwh, start_ts, end_ts
        )
    sc = ChargingSessionCost(
        vin=vin,
        start_ts=start_ts,
        end_ts=end_ts,
        tier_id=body.tier_id,
        energy_kwh=body.energy_kwh,
        peak_power_kw=body.peak_power_kw,
        cost=cost,
        note=body.note,
    )
    sc = await repo.upsert_session_cost(sc)
    return _cost_response(sc, tiers, {})


@router.put(
    "/api/vehicles/{vin}/charging-costs/{cost_id}",
    response_model=ChargingSessionCostResponse,
)
async def update_charging_cost(
    vin: str, cost_id: int, body: ChargingSessionCostUpdate, repo: RepoDep
):
    """Update a charging session cost (change tier, energy, etc.)."""
    costs = await repo.get_session_costs(vin)
    sc = next((c for c in costs if c.id == cost_id), None)
    if not sc:
        raise HTTPException(status_code=404, detail=f"Session cost {cost_id} not found")
    if body.tier_id is not None:
        tiers = {t.id: t for t in await repo.get_price_tiers()}
        if body.tier_id not in tiers:
            raise HTTPException(status_code=422, detail=f"Unknown tier: {body.tier_id}")
        sc.tier_id = body.tier_id
    if body.end_ts is not None:
        sc.end_ts = datetime.fromisoformat(body.end_ts)
    if body.energy_kwh is not None:
        sc.energy_kwh = body.energy_kwh
    if body.peak_power_kw is not None:
        sc.peak_power_kw = body.peak_power_kw
    if body.note is not None:
        sc.note = body.note
    # Recalculate cost
    if sc.energy_kwh is not None:
        sc.cost = await calculate_session_cost(
            repo, sc.tier_id, sc.energy_kwh, sc.start_ts, sc.end_ts
        )
    await repo.upsert_session_cost(sc)
    tiers = {t.id: t for t in await repo.get_price_tiers()}
    bands = {b.id: b for b in await repo.get_time_bands("home_grid")}
    return _cost_response(sc, tiers, bands)


@router.post(
    "/api/vehicles/{vin}/charging-costs/{cost_id}/recalculate",
    response_model=ChargingSessionCostResponse,
)
async def recalculate_charging_cost(vin: str, cost_id: int, repo: RepoDep):
    """Re-measure a session's total energy and cost from current data.

    Re-reads the session's energy from the stored snapshots and recomputes the
    cost with the tier's current price. Useful when the cost was first computed
    mid-session, before the full energy and final pricing were known.
    """
    costs = await repo.get_session_costs(vin)
    sc = next((c for c in costs if c.id == cost_id), None)
    if not sc:
        raise HTTPException(status_code=404, detail=f"Session cost {cost_id} not found")
    await recalculate_session(repo, sc)
    await repo.upsert_session_cost(sc)
    tiers = {t.id: t for t in await repo.get_price_tiers()}
    bands = {b.id: b for b in await repo.get_time_bands("home_grid")}
    return _cost_response(sc, tiers, bands)


@router.delete("/api/vehicles/{vin}/charging-costs/{cost_id}")
async def delete_charging_cost(vin: str, cost_id: int, repo: RepoDep):
    """Delete a charging session cost."""
    deleted = await repo.delete_session_cost(cost_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session cost {cost_id} not found")
    return {"status": "ok"}
