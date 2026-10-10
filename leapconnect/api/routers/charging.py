"""Charging routes: cloud history, consumption stats, tiers, bands, costs."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException

from leapconnect.api.deps import ClientDep, RepoDep, VehicleDep
from leapconnect.api.schemas import (
    CalculateMissingCostsRequest,
    CalculateMissingCostsResponse,
    ChargingHistoryResponse,
    ChargingPriceTierResponse,
    ChargingPriceTierUpdate,
    ChargingSessionCostCreate,
    ChargingSessionCostResponse,
    ChargingSessionCostUpdate,
    ChargingSessionRowSchema,
    ChargingSessionsResponse,
    ChargingTiersFullResponse,
    ChargingTimeBandCreate,
    ChargingTimeBandResponse,
    ChargingTimeBandUpdate,
    ConsumptionBreakdownResponse,
    ConsumptionLastWeekResponse,
    ConsumptionWeeklyRankResponse,
    MergeChargingSessionsRequest,
    MergePreviewGap,
    MergePreviewResponse,
    MergePreviewRun,
    MergePreviewSession,
    MileageEnergyHistoryResponse,
    SkippedSessionSchema,
)
from leapconnect.application.charging_costs import (
    MergeError,
    MissingCostSession,
    calculate_missing_costs,
    list_sessions,
    merge_charge_sessions,
    plan_merge,
)
from leapconnect.application.settings_store import (
    calculate_session_cost,
    load_preferences,
    load_user_timezone,
    price_session,
    recalculate_session,
    resolve_timezone,
)
from leapconnect.domain.charging.models import ChargingSessionCost, ChargingTimeBand
from leapconnect.domain.charging.sessions import (
    MERGE_MAX_GAP_LIMITS,
    MERGE_REASON_LABELS,
    MERGE_SESSION_PROBLEM_LABELS,
    day_range_bounds,
    month_bounds,
    naive_utc,
)
from leapconnect.domain.telemetry.cloud_stats import cloud_window

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


@router.get(
    "/api/vehicles/{vin}/consumption/breakdown",
    response_model=ConsumptionBreakdownResponse,
)
async def get_consumption_breakdown(
    vin: str,
    from_date: date,
    to_date: date,
    client: ClientDep,
    vehicle: VehicleDep,
    repo: RepoDep,
) -> ConsumptionBreakdownResponse:
    """Driving / A/C / other energy split over a range of days (inclusive),
    in the ``timezone`` preference."""
    try:
        start, end = cloud_window(from_date, to_date, await load_user_timezone(repo))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = await client.get_consumption_breakdown(vehicle, start=start, end=end)
    return ConsumptionBreakdownResponse.for_window(result, from_date, to_date)


@router.get(
    "/api/vehicles/{vin}/mileage/daily",
    response_model=MileageEnergyHistoryResponse,
)
async def get_daily_mileage_energy(
    vin: str,
    from_date: date,
    to_date: date,
    client: ClientDep,
    vehicle: VehicleDep,
    repo: RepoDep,
) -> MileageEnergyHistoryResponse:
    """Per-day mileage and energy over a range of days (inclusive), in the
    ``timezone`` preference, plus the cloud's lifetime totals."""
    try:
        start, end = cloud_window(from_date, to_date, await load_user_timezone(repo))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = await client.get_mileage_energy_history(vehicle, start=start, end=end)
    return MileageEnergyHistoryResponse.for_window(result, from_date, to_date)


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


def _iso(ts: datetime | None) -> str | None:
    return ts.isoformat() if ts else None


def _duplicate_fields(container: ChargingSessionCost | None) -> dict:
    if container is None:
        return {}
    return {
        "duplicate_of_id": container.id,
        "duplicate_of_start_ts": _iso(container.start_ts),
        "duplicate_of_end_ts": _iso(container.end_ts),
    }


@router.get(
    "/api/vehicles/{vin}/charging-sessions",
    response_model=ChargingSessionsResponse,
)
async def get_charging_sessions(
    vin: str,
    repo: RepoDep,
    year: int | None = None,
    month: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> ChargingSessionsResponse:
    """Charging sessions of a month (``year`` + ``month``) or of a range of
    days (``from_date`` + ``to_date``, inclusive), newest first.

    Sessions are detected from the vehicle history and paired with the stored
    cost records; months and days are in the ``timezone`` preference. Same
    selection as the month-end cost calculation.
    """
    tz_name = (await load_preferences(repo)).timezone
    tz = resolve_timezone(tz_name)
    if year is not None and month is not None:
        if not 1 <= month <= 12:
            raise HTTPException(status_code=422, detail="'month' must be 1-12")
        start, end = month_bounds(year, month, tz)
    elif from_date is not None and to_date is not None:
        if to_date < from_date:
            raise HTTPException(
                status_code=422, detail="'to_date' must not precede 'from_date'"
            )
        start, end = day_range_bounds(from_date, to_date, tz)
    else:
        raise HTTPException(
            status_code=422,
            detail="Pass either 'year' and 'month' or 'from_date' and 'to_date'",
        )
    rows = await list_sessions(repo, vin, start, end)
    tiers = {t.id: t for t in await repo.get_price_tiers()}
    bands = {b.id: b for b in await repo.get_time_bands("home_grid")}
    sessions = []
    for row in rows:
        base = (
            _cost_response(row.record, tiers, bands).model_dump() if row.record else {}
        )
        base.pop("vin", None)
        lat, lon = row.location or (None, None)
        sessions.append(
            ChargingSessionRowSchema(
                **{
                    **base,
                    "start_ts": row.start_ts.isoformat(),
                    "end_ts": row.end_ts.isoformat() if row.end_ts else None,
                    "energy_kwh": row.energy_kwh,
                    "peak_power_kw": row.peak_power_kw,
                    "detected_end_ts": row.detected_end_ts.isoformat()
                    if row.detected_end_ts
                    else None,
                    "start_soc": row.start_soc,
                    "end_soc": row.end_soc,
                    "latitude": lat,
                    "longitude": lon,
                    "is_dc": row.is_dc,
                    "parts": len(row.parts),
                    **_duplicate_fields(row.duplicate_of),
                }
            )
        )
    return ChargingSessionsResponse(
        timezone=tz_name or "UTC",
        start=start.isoformat(),
        end=end.isoformat(),
        sessions=sessions,
    )


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
    cost = body.cost
    if cost is None and body.energy_kwh is not None:
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
        zone_name=body.zone_name or None,
    )
    sc = await repo.upsert_session_cost(sc)
    return _cost_response(sc, tiers, {})


async def _merge_params(
    body: MergeChargingSessionsRequest, repo
) -> tuple[list[datetime], timedelta, dict]:
    """Validated selection, max pause and the price tiers of a merge request."""
    tiers = {t.id: t for t in await repo.get_price_tiers()}
    if body.tier_id is not None and body.tier_id not in tiers:
        raise HTTPException(status_code=422, detail=f"Unknown tier: {body.tier_id}")
    max_gap = timedelta(minutes=body.max_gap_minutes)
    low, high = MERGE_MAX_GAP_LIMITS
    if not low <= max_gap <= high:
        raise HTTPException(
            status_code=422,
            detail=f"'max_gap_minutes' must be between {low // timedelta(minutes=1)}"
            f" and {high // timedelta(minutes=1)}",
        )
    return [datetime.fromisoformat(ts) for ts in body.start_ts], max_gap, tiers


@router.post(
    "/api/vehicles/{vin}/charging-costs/merge/preview",
    response_model=MergePreviewResponse,
)
async def preview_charging_sessions_merge(
    vin: str, body: MergeChargingSessionsRequest, repo: RepoDep
) -> MergePreviewResponse:
    """What merging the selected sessions would do, without saving anything.

    Lists every session involved (the ones between the selected ones too),
    their charging runs, each pause with its checks (duration, odometer,
    place), the resulting energy/estimated cost and, when the merge isn't
    allowed, why.
    """
    starts, max_gap, _ = await _merge_params(body, repo)
    plan = await plan_merge(repo, vin, starts, tier_id=body.tier_id, max_gap=max_gap)
    selected = {naive_utc(s) for s in starts}
    return MergePreviewResponse(
        sessions=[
            MergePreviewSession(
                id=r.record.id if r.record else None,
                start_ts=r.start_ts.isoformat(),
                end_ts=_iso(r.end_ts),
                energy_kwh=r.energy_kwh,
                parts=len(r.parts),
                selected=r.start_ts in selected,
                tier_id=r.record.tier_id if r.record else None,
                problem=problem,
                problem_message=MERGE_SESSION_PROBLEM_LABELS.get(problem),
            )
            for r, problem in zip(plan.rows, plan.problems, strict=True)
        ],
        runs=[
            MergePreviewRun(
                start_ts=run.start_ts.isoformat(),
                end_ts=_iso(run.end_ts),
                energy_kwh=run.energy_kwh,
                zone_name=place,
            )
            for run, place in zip(plan.runs, plan.places, strict=True)
        ],
        gaps=[
            MergePreviewGap(
                start_ts=g.start_ts.isoformat(),
                end_ts=g.end_ts.isoformat(),
                minutes=g.minutes,
                within_max_gap=g.within_max_gap,
                same_odometer=g.same_odometer,
                same_place=g.same_place,
            )
            for g in plan.gaps
        ],
        tiers=plan.tiers,
        tier_id=plan.tier_id,
        zone_name=plan.zone_name,
        energy_kwh=plan.energy_kwh,
        cost=plan.cost,
        max_gap_minutes=body.max_gap_minutes,
        reason=plan.reason,
        message=MERGE_REASON_LABELS.get(plan.reason) if plan.reason else None,
    )


@router.post(
    "/api/vehicles/{vin}/charging-costs/merge",
    response_model=ChargingSessionCostResponse,
)
async def merge_charging_sessions(
    vin: str, body: MergeChargingSessionsRequest, repo: RepoDep
) -> ChargingSessionCostResponse:
    """Merge consecutive charging sessions into one (charge resumed in place).

    Every session between the first and last selected one is included. Refused
    (422) when a session is ongoing, the vehicle moved or changed place between
    them, or a pause exceeds the limit (see the preview). Deleting the merged
    session splits it back into its charging runs.
    """
    starts, max_gap, tiers = await _merge_params(body, repo)
    try:
        sc = await merge_charge_sessions(
            repo, vin, starts, tier_id=body.tier_id, max_gap=max_gap
        )
    except MergeError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Can't merge: {MERGE_REASON_LABELS.get(exc.reason, exc.reason)}",
        ) from exc
    bands = {b.id: b for b in await repo.get_time_bands("home_grid")}
    return _cost_response(sc, tiers, bands)


@router.post(
    "/api/vehicles/{vin}/charging-costs/calculate-missing",
    response_model=CalculateMissingCostsResponse,
)
async def calculate_missing_charging_costs(
    vin: str, body: CalculateMissingCostsRequest, repo: RepoDep
) -> CalculateMissingCostsResponse:
    """Compute costs for many sessions at once (the month's cost-less rows).

    Sessions detected only from snapshots get their tier inferred from the
    charge location (DC → public_dc, else the tier of the zone they're in);
    when it can't be inferred ``fallback_tier_id`` is used, or the session is
    skipped if none is given.
    """
    if body.fallback_tier_id is not None:
        tiers = {t.id for t in await repo.get_price_tiers()}
        if body.fallback_tier_id not in tiers:
            raise HTTPException(
                status_code=422, detail=f"Unknown tier: {body.fallback_tier_id}"
            )
    result = await calculate_missing_costs(
        repo,
        vin,
        [
            MissingCostSession(
                start_ts=datetime.fromisoformat(s.start_ts),
                end_ts=datetime.fromisoformat(s.end_ts) if s.end_ts else None,
                cost_id=s.cost_id,
            )
            for s in body.sessions
        ],
        fallback_tier_id=body.fallback_tier_id,
        close_orphans=body.close_orphans,
    )
    return CalculateMissingCostsResponse(
        calculated=result.calculated,
        skipped=[
            SkippedSessionSchema(start_ts=s.start_ts.isoformat(), reason=s.reason)
            for s in result.skipped
        ],
    )


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
    if body.zone_name is not None:
        # Empty string clears the zone assignment.
        sc.zone_name = body.zone_name or None
    # Recalculate cost
    if body.cost is not None:
        sc.cost = body.cost
    else:
        sc.cost = await price_session(repo, sc)
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
