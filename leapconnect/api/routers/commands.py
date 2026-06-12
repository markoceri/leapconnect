"""Remote-control routes: locks, climate, charging, schedules, FOTA, media."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from leapconnect.api.deps import ClientDep

router = APIRouter()


@router.post("/api/vehicles/{vin}/lock")
async def lock_vehicle(vin: str, client: ClientDep) -> dict:
    """Lock the vehicle remotely."""
    return await client.lock_vehicle(vin)


@router.post("/api/vehicles/{vin}/unlock")
async def unlock_vehicle(vin: str, client: ClientDep) -> dict:
    """Unlock the vehicle remotely."""
    return await client.unlock_vehicle(vin)


@router.post("/api/vehicles/{vin}/trunk/open")
async def open_trunk(vin: str, client: ClientDep) -> dict:
    """Open the trunk remotely."""
    return await client.open_trunk(vin)


@router.post("/api/vehicles/{vin}/trunk/close")
async def close_trunk(vin: str, client: ClientDep) -> dict:
    """Close the trunk remotely."""
    return await client.close_trunk(vin)


@router.post("/api/vehicles/{vin}/find")
async def find_vehicle(vin: str, client: ClientDep) -> dict:
    """Trigger the vehicle finder (flash lights and honk)."""
    return await client.find_vehicle(vin)


class SunshadeRequest(BaseModel):
    value: str = "10"  # "0" (closed) to "10" (fully open)


@router.post("/api/vehicles/{vin}/sunshade")
async def control_sunshade(
    vin: str, client: ClientDep, body: SunshadeRequest | None = None
) -> dict:
    """Control sunshade remotely with optional position (0-10)."""
    value = body.value if body else "10"
    return await client.control_sunshade(vin, value=value)


@router.post("/api/vehicles/{vin}/sunshade/open")
async def open_sunshade(
    vin: str, client: ClientDep, body: SunshadeRequest | None = None
) -> dict:
    """Open the sunshade remotely (optionally to a specific level)."""
    value = body.value if body else None
    return await client.open_sunshade(vin, value=value)


@router.post("/api/vehicles/{vin}/sunshade/close")
async def close_sunshade(
    vin: str, client: ClientDep, body: SunshadeRequest | None = None
) -> dict:
    """Close the sunshade remotely (optionally to a specific level)."""
    value = body.value if body else None
    return await client.close_sunshade(vin, value=value)


@router.post("/api/vehicles/{vin}/battery-preheat")
async def battery_preheat(vin: str, client: ClientDep) -> dict:
    """Start battery preheating remotely."""
    return await client.battery_preheat(vin)


class WindowsRequest(BaseModel):
    value: str = "100"  # "0" (closed) to "100" (fully open)


@router.post("/api/vehicles/{vin}/windows")
async def control_windows(
    vin: str, client: ClientDep, body: WindowsRequest | None = None
) -> dict:
    """Control windows remotely with optional position (0-100)."""
    value = body.value if body else "100"
    return await client.windows(vin, value=value)


@router.post("/api/vehicles/{vin}/windows/open")
async def open_windows(
    vin: str, client: ClientDep, body: WindowsRequest | None = None
) -> dict:
    """Open all windows remotely (optionally to a specific percentage)."""
    value = body.value if body else None
    return await client.open_windows(vin, value=value)


@router.post("/api/vehicles/{vin}/windows/close")
async def close_windows(
    vin: str, client: ClientDep, body: WindowsRequest | None = None
) -> dict:
    """Close all windows remotely (optionally to a specific percentage)."""
    value = body.value if body else None
    return await client.close_windows(vin, value=value)


class ClimateRequest(BaseModel):
    circle: str | None = None  # "in" or "out"
    mode: str | None = None  # "cold", "hot", "wind"
    operate: str | None = None  # "manual", "auto", or "close"
    position: str | None = None  # "all"
    temperature: str | None = None  # e.g. "26"
    windlevel: int | None = None  # 1–7
    wshld: str | None = None  # "0" (off) or "1" (defrost on)


def _climate_params(body: ClimateRequest | None) -> dict | None:
    return {
        k: v for k, v in (body.model_dump() if body else {}).items() if v is not None
    } or None


@router.post("/api/vehicles/{vin}/ac")
async def ac_switch(
    vin: str, client: ClientDep, body: ClimateRequest | None = None
) -> dict:
    """Turn on the air conditioning with optional parameters."""
    return await client.ac_on(vin, params=_climate_params(body))


@router.post("/api/vehicles/{vin}/ac-off")
async def ac_off(vin: str, client: ClientDep) -> dict:
    """Turn off the air conditioning."""
    return await client.ac_off(vin)


@router.post("/api/vehicles/{vin}/quick-cool")
async def quick_cool(
    vin: str, client: ClientDep, body: ClimateRequest | None = None
) -> dict:
    """Activate quick cooling mode with optional parameter overrides."""
    return await client.quick_cool(vin, params=_climate_params(body))


@router.post("/api/vehicles/{vin}/quick-heat")
async def quick_heat(
    vin: str, client: ClientDep, body: ClimateRequest | None = None
) -> dict:
    """Activate quick heating mode with optional parameter overrides."""
    return await client.quick_heat(vin, params=_climate_params(body))


@router.post("/api/vehicles/{vin}/defrost")
async def windshield_defrost(
    vin: str, client: ClientDep, body: ClimateRequest | None = None
) -> dict:
    """Activate windshield defrost with optional parameter overrides."""
    return await client.windshield_defrost(vin, params=_climate_params(body))


@router.post("/api/vehicles/{vin}/charge-limit")
async def set_charge_limit(vin: str, request: Request, client: ClientDep) -> dict:
    """Set the maximum charge level (20–100%)."""
    body = await request.json()
    limit = body.get("limit")
    if limit is None or not (20 <= int(limit) <= 100):
        raise HTTPException(
            status_code=422, detail="Charge limit must be between 20 and 100"
        )
    return await client.set_charge_limit(vin, int(limit))


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


@router.post("/api/vehicles/{vin}/charge-schedule")
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


@router.post("/api/vehicles/{vin}/ac-schedule")
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


@router.post("/api/vehicles/{vin}/send-destination")
async def send_destination(vin: str, request: Request, client: ClientDep) -> dict:
    """Send a navigation destination to the vehicle's infotainment system."""
    body = await request.json()
    address = body.get("address", "").strip()
    address_name = body.get("address_name", "").strip()
    latitude = body.get("latitude")
    longitude = body.get("longitude")
    if not address or latitude is None or longitude is None:
        raise HTTPException(
            status_code=422, detail="address, latitude, and longitude are required"
        )
    return await client.send_destination(
        vin,
        address=address,
        address_name=address_name or address,
        latitude=float(latitude),
        longitude=float(longitude),
    )


@router.post("/api/vehicles/{vin}/battery-preheat-off")
async def battery_preheat_off(vin: str, client: ClientDep) -> dict:
    """Stop battery preheating remotely."""
    return await client.battery_preheat_off(vin)


@router.post("/api/vehicles/{vin}/sentry-mode/on")
async def sentry_mode_on(vin: str, client: ClientDep) -> dict:
    """Activate sentry mode (dashcam/sentinel)."""
    return await client.sentry_mode_on(vin)


@router.post("/api/vehicles/{vin}/sentry-mode/off")
async def sentry_mode_off(vin: str, client: ClientDep) -> dict:
    """Deactivate sentry mode."""
    return await client.sentry_mode_off(vin)


@router.post("/api/vehicles/{vin}/charging/start")
async def start_charging(vin: str, client: ClientDep) -> dict:
    """Start charging the vehicle."""
    return await client.start_charging(vin)


@router.post("/api/vehicles/{vin}/charging/stop")
async def stop_charging(vin: str, client: ClientDep) -> dict:
    """Stop charging the vehicle."""
    return await client.stop_charging(vin)


@router.post("/api/vehicles/{vin}/steering-wheel-heat/on")
async def steering_wheel_heat_on(vin: str, client: ClientDep) -> dict:
    """Turn on steering wheel heating."""
    return await client.steering_wheel_heat_on(vin)


@router.post("/api/vehicles/{vin}/steering-wheel-heat/off")
async def steering_wheel_heat_off(vin: str, client: ClientDep) -> dict:
    """Turn off steering wheel heating."""
    return await client.steering_wheel_heat_off(vin)


@router.post("/api/vehicles/{vin}/fuel-heating/on")
async def fuel_heating_on(vin: str, client: ClientDep) -> dict:
    """Turn on fuel heating."""
    return await client.fuel_heating_on(vin)


@router.post("/api/vehicles/{vin}/fuel-heating/off")
async def fuel_heating_off(vin: str, client: ClientDep) -> dict:
    """Turn off fuel heating."""
    return await client.fuel_heating_off(vin)


@router.post("/api/vehicles/{vin}/rearview-mirror-heat/on")
async def rearview_mirror_heat_on(vin: str, client: ClientDep) -> dict:
    """Turn on rearview mirror heating."""
    return await client.rearview_mirror_heat_on(vin)


@router.post("/api/vehicles/{vin}/rearview-mirror-heat/off")
async def rearview_mirror_heat_off(vin: str, client: ClientDep) -> dict:
    """Turn off rearview mirror heating."""
    return await client.rearview_mirror_heat_off(vin)


@router.post("/api/vehicles/{vin}/healthy-charging/on")
async def healthy_charging_on(vin: str, client: ClientDep) -> dict:
    """Enable healthy charging."""
    return await client.healthy_charging_on(vin)


@router.post("/api/vehicles/{vin}/healthy-charging/off")
async def healthy_charging_off(vin: str, client: ClientDep) -> dict:
    """Disable healthy charging."""
    return await client.healthy_charging_off(vin)


@router.post("/api/vehicles/{vin}/on3/on")
async def on3_on(vin: str, client: ClientDep) -> dict:
    """Activate ON3 (ignition)."""
    return await client.on3_on(vin)


@router.post("/api/vehicles/{vin}/on3/off")
async def on3_off(vin: str, client: ClientDep) -> dict:
    """Deactivate ON3 (ignition)."""
    return await client.on3_off(vin)


@router.post("/api/vehicles/{vin}/ble-key-restart")
async def ble_key_restart(vin: str, client: ClientDep) -> dict:
    """Restart BLE key module."""
    return await client.ble_key_restart(vin)


@router.post("/api/vehicles/{vin}/sunroof/open")
async def open_sunroof(vin: str, client: ClientDep) -> dict:
    """Open the sunroof."""
    return await client.open_sunroof(vin)


@router.post("/api/vehicles/{vin}/sunroof/close")
async def close_sunroof(vin: str, client: ClientDep) -> dict:
    """Close the sunroof."""
    return await client.close_sunroof(vin)


@router.post("/api/vehicles/{vin}/unlock-charger")
async def unlock_charger(vin: str, client: ClientDep) -> dict:
    """Unlock the charging connector."""
    return await client.unlock_charger(vin)


@router.post("/api/vehicles/{vin}/hotspot")
async def toggle_hotspot(vin: str, client: ClientDep) -> dict:
    """Toggle vehicle WiFi hotspot."""
    return await client.hotspot(vin)


@router.post("/api/vehicles/{vin}/autopark")
async def autopark(vin: str, client: ClientDep) -> dict:
    """Trigger autopark."""
    return await client.autopark(vin)


# -- Parameterized commands --


class SeatHeatRequest(BaseModel):
    position: int  # 1–6
    level: int  # 0–3


@router.post("/api/vehicles/{vin}/seat-heat")
async def seat_heat(vin: str, body: SeatHeatRequest, client: ClientDep) -> dict:
    """Control seat heating (position 1-6, level 0-3)."""
    return await client.seat_heat(vin, position=body.position, level=body.level)


class SeatVentilationRequest(BaseModel):
    position: int  # 1–6
    level: int  # 0–3


@router.post("/api/vehicles/{vin}/seat-ventilation")
async def seat_ventilation(
    vin: str, body: SeatVentilationRequest, client: ClientDep
) -> dict:
    """Control seat ventilation (position 1-6, level 0-3)."""
    return await client.seat_ventilation(vin, position=body.position, level=body.level)


class SpeedLimitRequest(BaseModel):
    value: str  # km/h as string


@router.post("/api/vehicles/{vin}/speed-limit")
async def set_speed_limit(vin: str, body: SpeedLimitRequest, client: ClientDep) -> dict:
    """Set the vehicle speed limit."""
    return await client.set_speed_limit(vin, value=body.value)


class MediaRequest(BaseModel):
    operation: str  # "play", "pause", "next", "previous"


@router.post("/api/vehicles/{vin}/music")
async def music(vin: str, body: MediaRequest, client: ClientDep) -> dict:
    """Control music playback."""
    return await client.music(vin, operation=body.operation)


@router.post("/api/vehicles/{vin}/video")
async def video(vin: str, body: MediaRequest, client: ClientDep) -> dict:
    """Control video playback."""
    return await client.video(vin, operation=body.operation)


@router.get("/api/vehicles/{vin}/ptc-heating-schedule")
async def get_ptc_heating_schedule(vin: str, client: ClientDep) -> list[dict]:
    """Retrieve PTC battery heating schedules from the cloud."""
    return await client.get_ptc_heating_schedule(vin)


@router.get("/api/vehicles/{vin}/prepare-car-schedule")
async def get_prepare_car_schedule(vin: str, client: ClientDep) -> list[dict]:
    """Retrieve prepare-car pre-conditioning schedules from the cloud."""
    return await client.get_prepare_car_schedule(vin)


class FotaRequest(BaseModel):
    task_id: int


@router.post("/api/vehicles/{vin}/fota/download")
async def fota_download(vin: str, body: FotaRequest, client: ClientDep) -> dict:
    """Start FOTA firmware download."""
    return await client.fota_download(vin, task_id=body.task_id)


@router.post("/api/vehicles/{vin}/fota/install")
async def fota_install(vin: str, body: FotaRequest, client: ClientDep) -> dict:
    """Start FOTA firmware installation."""
    return await client.fota_install(vin, task_id=body.task_id)


class FotaScheduleRequest(BaseModel):
    task_id: int
    schedule_time: str


@router.get("/api/vehicles/{vin}/fota/schedule")
async def get_fota_schedule(vin: str, client: ClientDep) -> list[dict]:
    """Retrieve active FOTA install schedules from the cloud."""
    return await client.get_fota_schedule(vin)


@router.post("/api/vehicles/{vin}/fota/schedule")
async def fota_schedule(vin: str, body: FotaScheduleRequest, client: ClientDep) -> dict:
    """Schedule a FOTA firmware installation."""
    return await client.fota_schedule(
        vin, task_id=body.task_id, schedule_time=body.schedule_time
    )


class RearSeatsRequest(BaseModel):
    seat_info: str


@router.post("/api/vehicles/{vin}/rear-seats")
async def rear_seats(vin: str, body: RearSeatsRequest, client: ClientDep) -> dict:
    """Control rear seats (C16 only)."""
    return await client.rear_seats(vin, seat_info=body.seat_info)


@router.post("/api/vehicles/{vin}/prepare-car")
async def prepare_car(vin: str, request: Request, client: ClientDep) -> dict:
    """Prepare car command (C10/B10)."""
    body = await request.json()
    return await client.prepare_car(vin, params=body)


@router.post("/api/vehicles/{vin}/seat-adjust")
async def seat_adjust(vin: str, request: Request, client: ClientDep) -> dict:
    """Adjust seat position (C10/C16)."""
    body = await request.json()
    return await client.seat_adjust(vin, params=body)


@router.post("/api/vehicles/{vin}/piloted-parking")
async def piloted_parking(vin: str, request: Request, client: ClientDep) -> dict:
    """Trigger piloted parking (C10/C16)."""
    body = await request.json()
    return await client.piloted_parking(vin, params=body)
