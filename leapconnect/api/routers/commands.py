"""Remote-control routes: the generic command endpoint + schedule resources.

Individual per-command routes were replaced by
``POST /api/vehicles/{vin}/commands/{command}`` backed by the registry in
:mod:`leapconnect.application.commands` (shared with Telegram and MQTT).
Cloud schedules (charge, climate, FOTA) remain dedicated REST resources.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ValidationError

from leapconnect.api.deps import ClientDep, VehicleDep
from leapconnect.application.commands import (
    COMMANDS,
    normalize_command,
    public_name,
    vehicle_has_right,
)

router = APIRouter(tags=["commands"])


# ---------------------------------------------------------------------------
# Generic command endpoint
# ---------------------------------------------------------------------------


@router.get("/api/vehicles/{vin}/commands")
async def list_commands(vin: str, vehicle: VehicleDep) -> list[dict]:
    """List every remote command with its availability for this vehicle.

    ``available`` reflects the vehicle's rights/abilities; unavailable
    commands are listed too so the UI can offer them on explicit request.
    """
    return [
        {
            "command": public_name(name),
            "available": vehicle_has_right(vehicle, spec.right),
            "right": spec.right,
            "has_params": spec.params is not None or spec.raw_params,
            "requires_params": spec.requires_params or spec.raw_params,
        }
        for name, spec in sorted(COMMANDS.items())
    ]


@router.post("/api/vehicles/{vin}/commands/{command}")
async def execute_command(
    vin: str, command: str, request: Request, client: ClientDep
) -> dict:
    """Execute a remote command with an optional JSON parameter body.

    Vehicle rights are currently NOT enforced here (pass-through, matching
    the historical per-command routes); the registry carries the ``right``
    per command, so switching to a 403 is a deliberate follow-up once the
    rights map is field-validated.
    """
    spec = COMMANDS.get(normalize_command(command))
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown command: {command}")

    raw = await request.body()
    try:
        body = json.loads(raw) if raw else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid JSON body") from exc

    params: BaseModel | dict | None = None
    if spec.raw_params:
        params = body or {}
    elif spec.params is not None:
        try:
            params = spec.params.model_validate(body or {})
        except ValidationError as exc:
            raise HTTPException(
                status_code=422, detail=exc.errors(include_url=False)
            ) from exc

    return await spec.invoke(client, vin, params)


# ---------------------------------------------------------------------------
# Cloud schedules (REST resources, not commands)
# ---------------------------------------------------------------------------


class ChargeScheduleRequest(BaseModel):
    enabled: bool
    soc_limit: int = 80
    start_time: str
    end_time: str
    cycles: str
    circulation: int = 0
    recharge: int = 0


@router.get("/api/vehicles/{vin}/charge-schedule")
async def get_charge_schedule(vin: str, client: ClientDep) -> dict:
    """Retrieve the current charge schedule from the cloud."""
    return await client.get_charge_schedule(vin)


@router.put("/api/vehicles/{vin}/charge-schedule")
async def set_charge_schedule(
    vin: str, body: ChargeScheduleRequest, client: ClientDep
) -> dict:
    """Set the full charging schedule (start/end time, days, SOC limit)."""
    if not (20 <= body.soc_limit <= 100):
        raise HTTPException(
            status_code=422, detail="SOC limit must be between 20 and 100"
        )
    return await client.set_charge_schedule(
        vin,
        enabled=body.enabled,
        soc_limit=body.soc_limit,
        start_time=body.start_time,
        end_time=body.end_time,
        cycles=body.cycles,
        circulation=body.circulation,
        recharge=body.recharge,
    )


class ClimateScheduleEntry(BaseModel):
    mode: str = "wind"
    on: str = "1"
    operate: str = "manual"
    set_id: str
    start_time: str  # "yyyy-MM-dd HH:mm:00"
    temperature: str = "26"
    update_time: str
    windlevel: str = "3"
    days: list[int] = []
    circle: str | None = "out"
    position: str = "all"
    wshld: str = "0"


class ClimateScheduleRequest(BaseModel):
    controls: list[ClimateScheduleEntry]


@router.get("/api/vehicles/{vin}/ac-schedule")
async def get_climate_schedule(vin: str, client: ClientDep) -> list[dict]:
    """Retrieve active climate schedules from the cloud."""
    return await client.get_climate_schedule(vin)


@router.put("/api/vehicles/{vin}/ac-schedule")
async def set_climate_schedule(
    vin: str, body: ClimateScheduleRequest, client: ClientDep
) -> dict:
    """Set climate schedules via cloud (cmd_id=171, full-state replacement)."""
    controls = [entry.model_dump() for entry in body.controls]
    return await client.set_climate_schedule(vin, controls=controls)


@router.delete("/api/vehicles/{vin}/ac-schedule")
async def cancel_climate_schedule(vin: str, client: ClientDep) -> dict:
    """Cancel all climate schedules (sends empty controls array)."""
    return await client.cancel_climate_schedule(vin)


@router.get("/api/vehicles/{vin}/ptc-heating-schedule")
async def get_ptc_heating_schedule(vin: str, client: ClientDep) -> list[dict]:
    """Retrieve PTC battery heating schedules from the cloud."""
    return await client.get_ptc_heating_schedule(vin)


@router.get("/api/vehicles/{vin}/prepare-car-schedule")
async def get_prepare_car_schedule(vin: str, client: ClientDep) -> list[dict]:
    """Retrieve prepare-car pre-conditioning schedules from the cloud."""
    return await client.get_prepare_car_schedule(vin)


class FotaScheduleRequest(BaseModel):
    task_id: int
    schedule_time: str


@router.get("/api/vehicles/{vin}/fota/schedule")
async def get_fota_schedule(vin: str, client: ClientDep) -> list[dict]:
    """Retrieve active FOTA install schedules from the cloud."""
    return await client.get_fota_schedule(vin)


@router.put("/api/vehicles/{vin}/fota/schedule")
async def fota_schedule(vin: str, body: FotaScheduleRequest, client: ClientDep) -> dict:
    """Schedule a FOTA firmware installation."""
    return await client.fota_schedule(
        vin, task_id=body.task_id, schedule_time=body.schedule_time
    )
