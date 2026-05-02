"""Leapmotor Vehicle Dashboard — FastAPI backend.

Exposes the full Leapmotor API client through a REST interface and serves
the Vue.js SPA frontend in production.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import shutil
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from leapmotor_api import LeapmotorApiClient
from leapmotor_api.async_client import AsyncLeapmotorApiClient
from leapmotor_api.image import CarImagePackage
from leapmotor_api.models import MessageList, Vehicle, VehicleStatus

from models import VehicleSnapshot
from persistence.scheduler import VehicleDataScheduler
from persistence.sqlite_adapter import SQLAlchemyVehicleHistoryRepository
from schemas import MessageSchema, VehicleSchema, VehicleStatusSchema

# Load .env from the webapp directory
load_dotenv(Path(__file__).resolve().parent / ".env")

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)

# Data directory — mounted from host for persistence across container restarts
DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).parent / "data")))
CERTS_DIR = DATA_DIR / "certs"

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
_sync_client: LeapmotorApiClient | None = None
_client: AsyncLeapmotorApiClient | None = None
_vehicles: list[Vehicle] = []
_connected: bool = False
_picture_cache: dict[str, dict[str, str]] = {}  # vin -> {filename: data-URI}
_image_packages: dict[str, CarImagePackage] = {}  # vin -> CarImagePackage
_history_repo: SQLAlchemyVehicleHistoryRepository | None = None
_scheduler: VehicleDataScheduler | None = None


def _get_client() -> AsyncLeapmotorApiClient:
    if _client is None:
        raise HTTPException(
            status_code=400, detail="Not connected. Please login first."
        )
    return _client


def _find_vehicle(vin: str) -> Vehicle:
    for v in _vehicles:
        if v.vin == vin:
            return v
    raise HTTPException(status_code=404, detail=f"Vehicle {vin} not found")


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


async def _auto_connect() -> None:
    """Try to connect using saved credentials at startup."""
    global _sync_client, _client, _vehicles, _connected

    if not _history_repo:
        return

    account = await _history_repo.get_account()
    if not account:
        _LOGGER.info("Auto-connect: no saved account, skipping")
        return

    cert_path = account["cert_path"]
    key_path = account["key_path"]
    if not Path(cert_path).is_file() or not Path(key_path).is_file():
        _LOGGER.warning("Auto-connect: certificate files missing, skipping")
        return

    try:
        _sync_client = LeapmotorApiClient(
            username=account["username"],
            password=account["password"],
            app_cert_path=cert_path,
            app_key_path=key_path,
            account_p12_password=account.get("p12_password"),
        )
        _client = AsyncLeapmotorApiClient(_sync_client)
        await _client.login()
        _vehicles = await _client.get_vehicle_list()
        _connected = True
        _LOGGER.info("Auto-connect: success, %d vehicle(s)", len(_vehicles))

        # Start scheduler with the connected client
        if _scheduler:
            _scheduler.set_client(_client, _vehicles)
            _scheduler.start()
    except Exception as exc:
        _LOGGER.warning("Auto-connect: failed (%s), app will run offline", exc)
        _connected = False
        _sync_client = None
        _client = None
        _vehicles = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _history_repo, _scheduler
    db_path = os.environ.get(
        "HISTORY_DB_PATH", str(Path(__file__).parent / "history.db")
    )
    db_url = f"sqlite+aiosqlite:///{db_path}"
    _history_repo = SQLAlchemyVehicleHistoryRepository(db_url)
    await _history_repo.init_db()
    _LOGGER.info("History DB initialised at %s", db_path)

    # Restore scheduler settings from DB
    _scheduler = VehicleDataScheduler(_history_repo)
    saved = await _history_repo.load_scheduler_settings()
    _scheduler.update_settings(
        enabled=saved.enabled, interval_minutes=saved.interval_minutes
    )
    _LOGGER.info(
        "Scheduler settings loaded: enabled=%s, interval=%d min",
        saved.enabled,
        saved.interval_minutes,
    )

    # Auto-connect using saved credentials
    await _auto_connect()

    yield

    if _scheduler:
        await _scheduler.stop()
    if _history_repo:
        await _history_repo.close()
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
    app.mount(
        "/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets"
    )


# ---------------------------------------------------------------------------
# Routes — Setup (certificates & credentials)
# ---------------------------------------------------------------------------


@app.get("/api/setup/status")
async def setup_status():
    """Check if the app is configured (certificates + credentials saved)."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="DB not ready")

    account = await _history_repo.get_account()
    has_account = account is not None
    has_certs = False
    certs_valid = False

    if account:
        has_certs = bool(account.get("cert_path") and account.get("key_path"))
        certs_valid = (
            has_certs
            and Path(account["cert_path"]).is_file()
            and Path(account["key_path"]).is_file()
        )

    return {
        "has_account": has_account,
        "has_certificates": has_certs,
        "certificates_valid": certs_valid,
        "connected": _connected,
        "vehicles": [VehicleSchema.from_model(v).model_dump() for v in _vehicles],
    }


@app.post("/api/setup/certificates")
async def upload_certificates(
    cert_file: UploadFile = File(...),  # noqa: B008
    key_file: UploadFile = File(...),  # noqa: B008
):
    """Upload certificate files (cert + key). Saved to DATA_DIR/certs/."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="DB not ready")

    CERTS_DIR.mkdir(parents=True, exist_ok=True)

    cert_dest = CERTS_DIR / "app.crt"
    key_dest = CERTS_DIR / "app.key"

    try:
        with open(cert_dest, "wb") as f:
            shutil.copyfileobj(cert_file.file, f)
        with open(key_dest, "wb") as f:
            shutil.copyfileobj(key_file.file, f)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to save files: {exc}"
        ) from exc

    # Restrict permissions on the key file
    key_dest.chmod(0o600)

    await _history_repo.save_setting("cert_path", str(cert_dest))
    await _history_repo.save_setting("key_path", str(key_dest))

    return {"status": "ok", "cert_path": str(cert_dest), "key_path": str(key_dest)}


@app.get("/api/setup/certificates")
async def get_certificates():
    """Return current certificate status."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="DB not ready")

    account = await _history_repo.get_account()
    if account:
        cert_path = account.get("cert_path", "")
        key_path = account.get("key_path", "")
    else:
        cert_path = await _history_repo.get_setting("cert_path") or ""
        key_path = await _history_repo.get_setting("key_path") or ""

    return {
        "cert_exists": bool(cert_path) and Path(cert_path).is_file(),
        "key_exists": bool(key_path) and Path(key_path).is_file(),
    }


@app.post("/api/setup/account")
async def save_account(request: Request):
    """Save Leapmotor account credentials and attempt connection."""
    global _sync_client, _client, _vehicles, _connected

    if not _history_repo:
        raise HTTPException(status_code=503, detail="DB not ready")

    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    p12_password = body.get("p12_password", "").strip() or None

    if not all([username, password]):
        raise HTTPException(
            status_code=422, detail="username and password are required"
        )

    # Resolve cert paths from previously uploaded files
    cert_path = await _history_repo.get_setting("cert_path") or ""
    key_path = await _history_repo.get_setting("key_path") or ""

    if not cert_path or not key_path:
        raise HTTPException(status_code=422, detail="Certificates not uploaded yet")
    if not Path(cert_path).is_file():
        raise HTTPException(
            status_code=400, detail=f"Certificate file not found: {cert_path}"
        )
    if not Path(key_path).is_file():
        raise HTTPException(status_code=400, detail=f"Key file not found: {key_path}")

    # Save credentials to DB
    await _history_repo.save_account(
        username=username,
        password=password,
        cert_path=cert_path,
        key_path=key_path,
        p12_password=p12_password,
    )

    # Attempt connection
    if _sync_client:
        _sync_client.close()

    try:
        _sync_client = LeapmotorApiClient(
            username=username,
            password=password,
            app_cert_path=cert_path,
            app_key_path=key_path,
            account_p12_password=p12_password,
        )
        _client = AsyncLeapmotorApiClient(_sync_client)
        await _client.login()
        _vehicles = await _client.get_vehicle_list()
        _connected = True

        if _scheduler:
            _scheduler.set_client(_client, _vehicles)
            _scheduler.start()

        return {
            "status": "ok",
            "connected": True,
            "vehicles": [VehicleSchema.from_model(v).model_dump() for v in _vehicles],
        }
    except Exception as exc:
        # Credentials saved but connection failed — that's ok, app works offline
        _connected = False
        _sync_client = None
        _client = None
        _vehicles = []
        if _scheduler:
            _scheduler.set_client(None, [])
        return {
            "status": "ok",
            "connected": False,
            "connection_error": str(exc),
            "vehicles": [],
        }


@app.post("/api/reconnect")
async def reconnect():
    """Try to reconnect using saved credentials."""
    global _sync_client, _client, _vehicles, _connected

    if not _history_repo:
        raise HTTPException(status_code=503, detail="DB not ready")

    account = await _history_repo.get_account()
    if not account:
        raise HTTPException(status_code=400, detail="No account configured")

    if _sync_client:
        _sync_client.close()

    try:
        _sync_client = LeapmotorApiClient(
            username=account["username"],
            password=account["password"],
            app_cert_path=account["cert_path"],
            app_key_path=account["key_path"],
            account_p12_password=account.get("p12_password"),
        )
        _client = AsyncLeapmotorApiClient(_sync_client)
        await _client.login()
        _vehicles = await _client.get_vehicle_list()
        _connected = True

        if _scheduler:
            _scheduler.set_client(_client, _vehicles)
            _scheduler.start()

        return {
            "status": "ok",
            "connected": True,
            "vehicles": [VehicleSchema.from_model(v).model_dump() for v in _vehicles],
        }
    except Exception as exc:
        _connected = False
        _sync_client = None
        _client = None
        _vehicles = []
        raise HTTPException(
            status_code=502, detail=f"Connection failed: {exc}"
        ) from exc


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
            detail=(
                "Server misconfigured: "
                "APP_CERT_PATH and APP_KEY_PATH must be set in .env"
            ),
        )
    if not Path(app_cert_path).is_file():
        raise HTTPException(
            status_code=500, detail=f"App cert not found: {app_cert_path}"
        )
    if not Path(app_key_path).is_file():
        raise HTTPException(
            status_code=500, detail=f"App key not found: {app_key_path}"
        )

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

        # Inject client into scheduler so it can poll autonomously
        if _scheduler:
            _scheduler.set_client(_client, _vehicles)
            _scheduler.start()

        return {
            "status": "ok",
            "user_id": _sync_client.user_id,
            "vehicles": [VehicleSchema.from_model(v).model_dump() for v in _vehicles],
        }
    except Exception as exc:
        _connected = False
        _sync_client = None
        _client = None
        _vehicles = []
        if _scheduler:
            _scheduler.set_client(None, [])
        raise HTTPException(status_code=401, detail=str(exc)) from exc


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
    if _scheduler:
        _scheduler.set_client(None, [])
    if _sync_client:
        _sync_client.close()
    _sync_client = None
    _client = None
    _vehicles = []
    _connected = False
    _picture_cache.clear()
    _image_packages.clear()
    return {"status": "ok"}


@app.get("/api/status")
async def connection_status():
    has_account = False
    if _history_repo:
        account = await _history_repo.get_account()
        has_account = account is not None
    return {
        "connected": _connected,
        "has_account": has_account,
        "user_id": _sync_client.user_id if _sync_client else None,
        "vehicles": [VehicleSchema.from_model(v).model_dump() for v in _vehicles],
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
    return {"vehicles": [VehicleSchema.from_model(v).model_dump() for v in _vehicles]}


@app.get("/api/vehicles/{vin}/status")
async def get_vehicle_status(vin: str):
    client = _get_client()
    vehicle = _find_vehicle(vin)
    status = await client.get_vehicle_status(vehicle)

    # Persist snapshot for historical tracking
    if _history_repo and isinstance(status, VehicleStatus):
        snapshot = VehicleSnapshot(
            vin=vin,
            timestamp=status.collect_time or datetime.utcnow(),
            battery_soc=status.battery.soc,
            expected_mileage=status.battery.expected_mileage,
            total_mileage=status.driving.total_mileage,
            energy_kwh=status.battery.dump_energy_kwh,
            outdoor_temp=status.climate.outdoor_temp,
            is_charging=status.is_charging,
            latitude=status.location.latitude,
            longitude=status.location.longitude,
            charge_state=status.battery.charge_state.value
            if status.battery.charge_state
            else None,
            speed=status.driving.speed,
        )
        asyncio.create_task(_save_snapshot_safe(snapshot))

    return {"status": VehicleStatusSchema.from_model(status).model_dump()}


async def _save_snapshot_safe(snapshot: VehicleSnapshot) -> None:
    """Fire-and-forget snapshot save; errors are logged, never raised."""
    try:
        await _history_repo.save_snapshot(snapshot)
    except Exception:
        _LOGGER.exception("Failed to save vehicle snapshot")


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

    # Extract the tripsum (complete car) image, fallback to first image
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            image_names = [
                n
                for n in zf.namelist()
                if n.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
            ]
            if not image_names:
                raise HTTPException(
                    status_code=404,
                    detail=f"No image found in package. Contents: {zf.namelist()}",
                )
            # Prefer carpic_for_tripsum (complete car) over body-only
            tripsum = [n for n in image_names if "tripsum" in n.lower()]
            img_name = tripsum[0] if tripsum else image_names[0]
            img_data = zf.read(img_name)
    except zipfile.BadZipFile:
        # Not a ZIP — maybe the response is already a raw image
        img_data = zip_bytes
        img_name = "image.png"

    ext = img_name.rsplit(".", 1)[-1].lower()
    media_types = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
    }
    media_type = media_types.get(ext, "image/png")

    return Response(
        content=img_data,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/api/vehicles/{vin}/picture/package")
async def get_picture_package(vin: str):
    """Download the picture ZIP, extract all images, and return as {name: dataURI}.

    Cached per VIN for the lifetime of the session.
    """
    if vin in _picture_cache:
        return _picture_cache[vin]

    client = _get_client()
    vehicle = _find_vehicle(vin)
    picture_data = await client.get_car_picture(vehicle)
    key = (picture_data.get("data") or {}).get("key")
    if not key:
        raise HTTPException(status_code=404, detail="No picture key available")

    zip_bytes = await client.download_car_picture_package(picture_key=key)

    images: dict[str, str] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for entry in zf.namelist():
                lower = entry.lower()
                if not lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
                    continue
                # Use the bare filename without directory prefix
                basename = entry.rsplit("/", 1)[-1]
                raw = zf.read(entry)
                ext = basename.rsplit(".", 1)[-1].lower()
                mime = {
                    "png": "image/png",
                    "jpg": "image/jpeg",
                    "jpeg": "image/jpeg",
                    "webp": "image/webp",
                }.get(ext, "image/png")
                images[basename] = (
                    f"data:{mime};base64,{base64.b64encode(raw).decode()}"
                )
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=500, detail="Invalid picture package") from exc

    _picture_cache[vin] = images
    return images


async def _get_image_package(vin: str) -> CarImagePackage:
    """Get or create a cached CarImagePackage for the given VIN."""
    if vin in _image_packages:
        return _image_packages[vin]

    client = _get_client()
    vehicle = _find_vehicle(vin)
    picture_data = await client.get_car_picture(vehicle)
    key = (picture_data.get("data") or {}).get("key")
    if not key:
        raise HTTPException(status_code=404, detail="No picture key available")

    zip_bytes = await client.download_car_picture_package(picture_key=key)
    pkg = await asyncio.to_thread(CarImagePackage.from_zip, zip_bytes)
    _image_packages[vin] = pkg
    return pkg


@app.get("/api/vehicles/{vin}/picture/dynamic")
async def get_dynamic_picture(vin: str, charge_frame: int = 0):
    """Compose and return the car image based on current vehicle status.

    Each frame is a lossless PNG — the frontend handles animation by
    cycling ``charge_frame`` (1-15) when the vehicle is charging.
    Pass ``charge_frame=0`` (default) to get the image without the
    animated charge-level overlay (charge port still shown if charging).
    """
    client = _get_client()
    vehicle = _find_vehicle(vin)

    pkg, status_raw = await asyncio.gather(
        _get_image_package(vin),
        client.get_vehicle_status(vehicle),
    )

    status = status_raw if isinstance(status_raw, VehicleStatus) else None
    img_bytes = await asyncio.to_thread(
        pkg.compose, status, charge_frame=charge_frame, format="PNG"
    )

    return Response(
        content=img_bytes,
        media_type="image/png",
        headers={"Cache-Control": "no-cache"},
    )


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
        "vehicle": VehicleSchema.from_model(vehicle).model_dump(),
        "status": VehicleStatusSchema.from_model(status).model_dump()
        if status
        else None,
        "mileage": mileage if isinstance(mileage, dict) else None,
        "picture": picture if isinstance(picture, dict) else None,
        "errors": {
            "status": str(results[0]) if isinstance(results[0], Exception) else None,
            "mileage": str(results[1]) if isinstance(results[1], Exception) else None,
            "picture": str(results[2]) if isinstance(results[2], Exception) else None,
        },
    }


# ---------------------------------------------------------------------------
# Routes — Vehicle History
# ---------------------------------------------------------------------------


@app.get("/api/vehicles/{vin}/history")
async def get_vehicle_history(vin: str, days: int = 30):
    """Return raw snapshots for the given VIN."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="History not available")
    snapshots = await _history_repo.get_history(vin, days=days)
    return {
        "vin": vin,
        "days": days,
        "count": len(snapshots),
        "snapshots": [
            {
                "timestamp": s.timestamp.isoformat(),
                "battery_soc": s.battery_soc,
                "expected_mileage": s.expected_mileage,
                "total_mileage": s.total_mileage,
                "energy_kwh": s.energy_kwh,
                "outdoor_temp": s.outdoor_temp,
                "is_charging": s.is_charging,
                "latitude": s.latitude,
                "longitude": s.longitude,
                "speed": s.speed,
            }
            for s in snapshots
        ],
    }


@app.get("/api/vehicles/{vin}/history/daily")
async def get_vehicle_daily_summary(vin: str, days: int = 30):
    """Return aggregated daily summaries for charts."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="History not available")
    summaries = await _history_repo.get_daily_summary(vin, days=days)
    return {
        "vin": vin,
        "days": days,
        "count": len(summaries),
        "daily": summaries,
    }


# ---------------------------------------------------------------------------
# Routes — Scheduler Settings
# ---------------------------------------------------------------------------


@app.get("/api/scheduler")
async def get_scheduler_status():
    """Return current scheduler status and settings."""
    if not _scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not available")
    return _scheduler.status_dict()


@app.put("/api/scheduler")
async def update_scheduler_settings(request: Request):
    """Update scheduler settings (enabled, interval_minutes)."""
    if not _scheduler or not _history_repo:
        raise HTTPException(status_code=503, detail="Scheduler not available")

    body = await request.json()
    enabled = body.get("enabled")
    interval = body.get("interval_minutes")

    if enabled is not None and not isinstance(enabled, bool):
        raise HTTPException(status_code=422, detail="'enabled' must be a boolean")
    if interval is not None:
        try:
            interval = int(interval)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail="'interval_minutes' must be an integer",
            ) from exc

    settings = _scheduler.update_settings(enabled=enabled, interval_minutes=interval)

    # Persist to DB
    await _history_repo.save_scheduler_settings(settings)

    return _scheduler.status_dict()


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
        raise HTTPException(
            status_code=422, detail="Charge limit must be between 20 and 100"
        )
    return await client.set_charge_limit(vin, int(limit))


@app.post("/api/vehicles/{vin}/send-destination")
async def send_destination(vin: str, request: Request):
    """Send a navigation destination to the vehicle."""
    client = _get_client()
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


# ---------------------------------------------------------------------------
# Routes — Messages
# ---------------------------------------------------------------------------


@app.get("/api/messages")
async def get_messages(page_no: int = 1, page_size: int = 20):
    """Fetch paginated notification messages."""
    client = _get_client()
    msg_list: MessageList = await client.get_message_list(
        page_no=page_no, page_size=page_size
    )
    return {
        "count": msg_list.count,
        "page_no": page_no,
        "page_size": page_size,
        "messages": [
            MessageSchema.from_model(m).model_dump() for m in msg_list.messages
        ],
    }


@app.get("/api/messages/unread-count")
async def get_unread_message_count():
    """Get the number of unread messages."""
    client = _get_client()
    count = await client.get_unread_message_count()
    return {"unread": count}


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
