"""Leapmotor Vehicle Dashboard — FastAPI backend.

Exposes the full Leapmotor API client through a REST interface and serves
the Vue.js SPA frontend in production.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import sys
import zipfile
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

# Load .env from the webapp directory
load_dotenv(Path(__file__).resolve().parent / ".env")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

# Allow importing the leapmotor_api package from the project src/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from leapmotor_api import LeapmotorApiClient  # noqa: E402
from leapmotor_api.async_client import AsyncLeapmotorApiClient  # noqa: E402
from leapmotor_api.models import Vehicle, VehicleStatus  # noqa: E402

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
_sync_client: LeapmotorApiClient | None = None
_client: AsyncLeapmotorApiClient | None = None
_vehicles: list[Vehicle] = []
_connected: bool = False


def _get_client() -> AsyncLeapmotorApiClient:
    if _client is None:
        raise HTTPException(status_code=400, detail="Not connected. Please login first.")
    return _client


def _find_vehicle(vin: str) -> Vehicle:
    for v in _vehicles:
        if v.vin == vin:
            return v
    raise HTTPException(status_code=404, detail=f"Vehicle {vin} not found")


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    if _sync_client:
        _sync_client.close()


app = FastAPI(title="Leapmotor Dashboard", lifespan=lifespan)

# CORS — allow Vue dev server during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Serve Vue SPA in production (built files in frontend/dist)
# ---------------------------------------------------------------------------
FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


# ---------------------------------------------------------------------------
# Routes — Authentication
# ---------------------------------------------------------------------------

@app.post("/api/login")
async def login(request: Request):
    global _sync_client, _client, _vehicles, _connected

    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()

    if not all([username, password]):
        raise HTTPException(status_code=422, detail="Missing email or password")

    # Certificate paths from .env
    app_cert_path = os.environ.get("APP_CERT_PATH", "").strip()
    app_key_path = os.environ.get("APP_KEY_PATH", "").strip()
    account_p12_password = os.environ.get("ACCOUNT_P12_PASSWORD", "").strip() or None

    if not app_cert_path or not app_key_path:
        raise HTTPException(
            status_code=500,
            detail="Server misconfigured: APP_CERT_PATH and APP_KEY_PATH must be set in .env",
        )
    if not Path(app_cert_path).is_file():
        raise HTTPException(status_code=500, detail=f"App cert not found: {app_cert_path}")
    if not Path(app_key_path).is_file():
        raise HTTPException(status_code=500, detail=f"App key not found: {app_key_path}")

    # Close existing client
    if _sync_client:
        _sync_client.close()

    try:
        _sync_client = LeapmotorApiClient(
            username=username,
            password=password,
            app_cert_path=app_cert_path,
            app_key_path=app_key_path,
            account_p12_password=account_p12_password,
        )
        _client = AsyncLeapmotorApiClient(_sync_client)
        await _client.login()
        _vehicles = await _client.get_vehicle_list()
        _connected = True
        return {
            "status": "ok",
            "user_id": _sync_client.user_id,
            "vehicles": [_vehicle_to_dict(v) for v in _vehicles],
        }
    except Exception as exc:
        _connected = False
        _sync_client = None
        _client = None
        _vehicles = []
        raise HTTPException(status_code=401, detail=str(exc))


@app.post("/api/set-pin")
async def set_pin(request: Request):
    """Set the vehicle operation PIN after login."""
    if not _sync_client:
        raise HTTPException(status_code=400, detail="Not connected")
    body = await request.json()
    pin = body.get("pin", "").strip()
    if not pin:
        raise HTTPException(status_code=422, detail="PIN is required")
    _sync_client.operation_password = pin
    return {"status": "ok", "has_pin": True}


@app.post("/api/logout")
async def logout():
    global _sync_client, _client, _vehicles, _connected
    if _sync_client:
        _sync_client.close()
    _sync_client = None
    _client = None
    _vehicles = []
    _connected = False
    return {"status": "ok"}


@app.get("/api/status")
async def connection_status():
    return {
        "connected": _connected,
        "user_id": _sync_client.user_id if _sync_client else None,
        "vehicles": [_vehicle_to_dict(v) for v in _vehicles],
        "has_pin": bool(_sync_client and _sync_client.operation_password),
    }


# ---------------------------------------------------------------------------
# Routes — Vehicle Data
# ---------------------------------------------------------------------------

@app.get("/api/vehicles")
async def get_vehicles():
    client = _get_client()
    global _vehicles
    _vehicles = await client.get_vehicle_list()
    return {"vehicles": [_vehicle_to_dict(v) for v in _vehicles]}


@app.get("/api/vehicles/{vin}/status")
async def get_vehicle_status(vin: str):
    client = _get_client()
    vehicle = _find_vehicle(vin)
    status = await client.get_vehicle_status(vehicle)
    return {"status": _vehicle_status_to_dict(status)}


@app.get("/api/vehicles/{vin}/raw-status")
async def get_vehicle_raw_status(vin: str):
    client = _get_client()
    vehicle = _find_vehicle(vin)
    raw = await client.get_vehicle_raw_status(vehicle)
    return raw


@app.get("/api/vehicles/{vin}/mileage")
async def get_mileage(vin: str):
    client = _get_client()
    vehicle = _find_vehicle(vin)
    data = await client.get_mileage_energy_detail(vehicle)
    return data


@app.get("/api/vehicles/{vin}/picture")
async def get_picture(vin: str):
    client = _get_client()
    vehicle = _find_vehicle(vin)
    data = await client.get_car_picture(vehicle)
    return data


@app.get("/api/vehicles/{vin}/picture/download")
async def download_picture(vin: str, key: str):
    client = _get_client()
    data = await client.download_car_picture_package(picture_key=key)
    return Response(content=data, media_type="application/zip")


@app.get("/api/vehicles/{vin}/picture/image")
async def get_picture_image(vin: str):
    """Get car picture key, download the ZIP package, extract and serve the PNG."""
    client = _get_client()
    vehicle = _find_vehicle(vin)
    picture_data = await client.get_car_picture(vehicle)
    key = (picture_data.get("data") or {}).get("key")
    if not key:
        raise HTTPException(status_code=404, detail="No picture key available")

    zip_bytes = await client.download_car_picture_package(picture_key=key)

    # Extract first image from the ZIP
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            image_names = [
                n for n in zf.namelist()
                if n.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
            ]
            if not image_names:
                raise HTTPException(status_code=404, detail=f"No image found in package. Contents: {zf.namelist()}")
            img_name = image_names[0]
            img_data = zf.read(img_name)
    except zipfile.BadZipFile:
        # Not a ZIP — maybe the response is already a raw image
        img_data = zip_bytes
        img_name = "image.png"

    ext = img_name.rsplit(".", 1)[-1].lower()
    media_types = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
    media_type = media_types.get(ext, "image/png")

    return Response(content=img_data, media_type=media_type, headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/vehicles/{vin}/full")
async def get_full_vehicle_data(vin: str):
    """Fetch all data for a vehicle in one call."""
    client = _get_client()
    vehicle = _find_vehicle(vin)

    status_task = client.get_vehicle_status(vehicle)
    mileage_task = client.get_mileage_energy_detail(vehicle)
    picture_task = client.get_car_picture(vehicle)

    results = await asyncio.gather(
        status_task,
        mileage_task,
        picture_task,
        return_exceptions=True,
    )

    status = results[0] if not isinstance(results[0], Exception) else None
    mileage = results[1] if not isinstance(results[1], Exception) else None
    picture = results[2] if not isinstance(results[2], Exception) else None

    return {
        "vehicle": _vehicle_to_dict(vehicle),
        "status": _vehicle_status_to_dict(status) if status else None,
        "mileage": mileage if isinstance(mileage, dict) else None,
        "picture": picture if isinstance(picture, dict) else None,
        "errors": {
            "status": str(results[0]) if isinstance(results[0], Exception) else None,
            "mileage": str(results[1]) if isinstance(results[1], Exception) else None,
            "picture": str(results[2]) if isinstance(results[2], Exception) else None,
        },
    }


# ---------------------------------------------------------------------------
# Routes — Remote Control
# ---------------------------------------------------------------------------

@app.post("/api/vehicles/{vin}/lock")
async def lock_vehicle(vin: str):
    client = _get_client()
    return await client.lock_vehicle(vin)


@app.post("/api/vehicles/{vin}/unlock")
async def unlock_vehicle(vin: str):
    client = _get_client()
    return await client.unlock_vehicle(vin)


@app.post("/api/vehicles/{vin}/trunk/open")
async def open_trunk(vin: str):
    client = _get_client()
    return await client.open_trunk(vin)


@app.post("/api/vehicles/{vin}/trunk/close")
async def close_trunk(vin: str):
    client = _get_client()
    return await client.close_trunk(vin)


@app.post("/api/vehicles/{vin}/find")
async def find_vehicle(vin: str):
    client = _get_client()
    return await client.find_vehicle(vin)


@app.post("/api/vehicles/{vin}/sunshade/open")
async def open_sunshade(vin: str):
    client = _get_client()
    return await client.open_sunshade(vin)


@app.post("/api/vehicles/{vin}/sunshade/close")
async def close_sunshade(vin: str):
    client = _get_client()
    return await client.close_sunshade(vin)


@app.post("/api/vehicles/{vin}/battery-preheat")
async def battery_preheat(vin: str):
    client = _get_client()
    return await client.battery_preheat(vin)


@app.post("/api/vehicles/{vin}/windows/open")
async def open_windows(vin: str):
    client = _get_client()
    return await client.open_windows(vin)


@app.post("/api/vehicles/{vin}/windows/close")
async def close_windows(vin: str):
    client = _get_client()
    return await client.close_windows(vin)


@app.post("/api/vehicles/{vin}/ac")
async def ac_switch(vin: str):
    client = _get_client()
    return await client.ac_switch(vin)


@app.post("/api/vehicles/{vin}/quick-cool")
async def quick_cool(vin: str):
    client = _get_client()
    return await client.quick_cool(vin)


@app.post("/api/vehicles/{vin}/quick-heat")
async def quick_heat(vin: str):
    client = _get_client()
    return await client.quick_heat(vin)


@app.post("/api/vehicles/{vin}/defrost")
async def windshield_defrost(vin: str):
    client = _get_client()
    return await client.windshield_defrost(vin)


@app.post("/api/vehicles/{vin}/charge-limit")
async def set_charge_limit(vin: str, request: Request):
    client = _get_client()
    body = await request.json()
    limit = body.get("limit")
    if limit is None or not (20 <= int(limit) <= 100):
        raise HTTPException(status_code=422, detail="Charge limit must be between 20 and 100")
    return await client.set_charge_limit(vin, int(limit))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _vehicle_to_dict(v: Vehicle) -> dict[str, Any]:
    return {
        "vin": v.vin,
        "car_id": v.car_id,
        "car_type": v.car_type,
        "nickname": v.nickname,
        "is_shared": v.is_shared,
        "year": v.year,
        "abilities": v.abilities or [],
    }


def _vehicle_status_to_dict(status: VehicleStatus) -> dict[str, Any]:
    return {
        "battery": {
            "soc": status.battery.soc,
            "is_charging": status.battery.is_charging,
            "charge_state": status.battery.charge_state,
            "charge_remain_time": status.battery.charge_remain_time,
            "charge_soc_setting": status.battery.charge_soc_setting,
            "expected_mileage": status.battery.expected_mileage,
            "dump_energy": status.battery.dump_energy,
            "battery_current": status.battery.battery_current,
            "battery_voltage": status.battery.battery_voltage,
        },
        "driving": {
            "speed": status.driving.speed,
            "total_mileage": status.driving.total_mileage,
            "gear_status": status.driving.gear_status,
            "is_parked": status.driving.is_parked,
        },
        "location": {
            "latitude": status.location.latitude,
            "longitude": status.location.longitude,
        },
        "climate": {
            "ac_switch": status.climate.ac_switch,
            "ac_setting": status.climate.ac_setting,
            "ac_air_volume": status.climate.ac_air_volume,
            "outdoor_temp": status.climate.outdoor_temp,
            "ac_cooling_and_heating": status.climate.ac_cooling_and_heating,
            "ac_circle_mode": status.climate.ac_circle_mode,
        },
        "doors": {
            "is_locked": status.doors.is_locked,
            "driver_door": status.doors.lbcm_driver_door_status,
            "passenger_door": status.doors.rbcm_driver_door_status,
            "left_rear": status.doors.lbcm_left_rear_door_status,
            "right_rear": status.doors.rbcm_right_rear_door_status,
            "trunk": status.doors.bbcm_back_door_status,
        },
        "windows": {
            "left_front_percent": status.windows.left_front_window_percent,
            "right_front_percent": status.windows.right_front_window_percent,
            "left_rear_percent": status.windows.left_rear_window_percent,
            "right_rear_percent": status.windows.right_rear_window_percent,
            "sun_shade": status.windows.sun_shade,
        },
        "tires": status.tires.all_bar,
        "connectivity": {
            "bluetooth": status.connectivity.bluetooth_state,
            "hotspot": status.connectivity.hotspot_state,
        },
        "ignition": {
            "on1": status.ignition.bcm_key_position_on1,
            "on3": status.ignition.bcm_key_position_on3,
        },
        "timestamps": {
            "collect_time": status.collect_time.isoformat() if status.collect_time else None,
            "create_time": status.create_time.isoformat() if status.create_time else None,
        },
    }


# ---------------------------------------------------------------------------
# SPA Fallback — must be last
# ---------------------------------------------------------------------------

if FRONTEND_DIST.is_dir():
    @app.get("/{path:path}")
    async def serve_spa_fallback(path: str):
        """Serve Vue SPA for any non-API route (client-side routing)."""
        file = FRONTEND_DIST / path
        if file.is_file():
            return FileResponse(str(file))
        return FileResponse(str(FRONTEND_DIST / "index.html"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8099)
