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
import secrets
import shutil
import time
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from leapmotor_api import LeapmotorApiClient
from leapmotor_api.async_client import AsyncLeapmotorApiClient
from leapmotor_api.image import CarImagePackage
from leapmotor_api.models import MessageList, Vehicle, VehicleStatus
from pydantic import BaseModel

from models import VehicleSnapshot
from persistence.sqlite_adapter import SQLAlchemyVehicleHistoryRepository
from schemas import (
    AccountSetupResponse,
    AuthLoginResponse,
    CertificateStatusResponse,
    CertificateUploadResponse,
    ConnectionStatusResponse,
    DailySummaryResponse,
    FullVehicleDataResponse,
    LoginResponse,
    MessageListResponse,
    MessageSchema,
    ReconnectResponse,
    SchedulerStatusResponse,
    SetPinResponse,
    SetupStatusResponse,
    SnapshotSchema,
    StatusResponse,
    UnreadCountResponse,
    UserCreateResponse,
    UserInfoResponse,
    UserUpdateResponse,
    VehicleHistoryResponse,
    VehicleListResponse,
    VehicleSchema,
    VehicleStatusResponse,
    VehicleStatusSchema,
)
from services.scheduler import VehicleDataScheduler

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

# Session management — in-memory token store
SESSION_COOKIE_NAME = "leapconnect_session"
SESSION_MAX_AGE = 7 * 24 * 3600  # 7 days
_sessions: dict[str, float] = {}  # token -> expiry timestamp

# Endpoints that do NOT require a session
_PUBLIC_PATHS: set[str] = {
    "/api/setup/status",
    "/api/setup/user",
    "/api/auth/login",
}


def _create_session() -> str:
    """Create a new session token and store it."""
    token = secrets.token_urlsafe(32)
    _sessions[token] = time.time() + SESSION_MAX_AGE
    return token


def _validate_session(token: str | None) -> bool:
    """Check if a session token is valid and not expired."""
    if not token or token not in _sessions:
        return False
    if time.time() > _sessions[token]:
        _sessions.pop(token, None)
        return False
    return True


def _invalidate_session(token: str | None) -> None:
    """Remove a session token."""
    if token:
        _sessions.pop(token, None)


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


@app.middleware("http")
async def session_middleware(request: Request, call_next):
    """Require a valid session cookie for all /api/ routes except public ones."""
    path = request.url.path
    if path.startswith("/api/") and path not in _PUBLIC_PATHS:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if not _validate_session(token):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
            )
    return await call_next(request)


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


@app.get("/api/setup/status", response_model=SetupStatusResponse)
async def setup_status(request: Request) -> SetupStatusResponse:
    """Check if the app is configured (user + certificates + credentials)."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="DB not ready")

    user = await _history_repo.get_user()
    has_user = user is not None

    # Check session authentication
    token = request.cookies.get(SESSION_COOKIE_NAME)
    authenticated = _validate_session(token)

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
    else:
        # Check certs from settings (uploaded but no account yet)
        cert_path = await _history_repo.get_setting("cert_path") or ""
        key_path = await _history_repo.get_setting("key_path") or ""
        if cert_path and key_path:
            has_certs = True
            certs_valid = Path(cert_path).is_file() and Path(key_path).is_file()

    # Detect cert files on disk even if the DB has no record of them
    certs_found_on_disk = (
        not has_certs
        and (CERTS_DIR / "app.crt").is_file()
        and (CERTS_DIR / "app.key").is_file()
    )

    return SetupStatusResponse(
        has_user=has_user,
        has_account=has_account,
        has_certificates=has_certs,
        certificates_valid=certs_valid,
        certs_found_on_disk=certs_found_on_disk,
        authenticated=authenticated,
        connected=_connected,
        vehicles=[VehicleSchema.from_model(v) for v in _vehicles],
    )


@app.post("/api/setup/certificates", response_model=CertificateUploadResponse)
async def upload_certificates(
    cert_file: UploadFile = File(...),  # noqa: B008
    key_file: UploadFile = File(...),  # noqa: B008
) -> CertificateUploadResponse:
    """Upload certificate files (cert + key) for API authentication."""
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

    return CertificateUploadResponse(
        status="ok", cert_path=str(cert_dest), key_path=str(key_dest)
    )


@app.post("/api/setup/certificates/adopt", response_model=CertificateUploadResponse)
async def adopt_certificates() -> CertificateUploadResponse:
    """Adopt certificate files already present on disk without re-uploading."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="DB not ready")

    cert_dest = CERTS_DIR / "app.crt"
    key_dest = CERTS_DIR / "app.key"

    if not cert_dest.is_file() or not key_dest.is_file():
        raise HTTPException(
            status_code=404, detail="Certificate files not found on disk"
        )

    await _history_repo.save_setting("cert_path", str(cert_dest))
    await _history_repo.save_setting("key_path", str(key_dest))

    return CertificateUploadResponse(
        status="ok", cert_path=str(cert_dest), key_path=str(key_dest)
    )


@app.get("/api/setup/certificates", response_model=CertificateStatusResponse)
async def get_certificates() -> CertificateStatusResponse:
    """Check whether certificate files are present."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="DB not ready")

    account = await _history_repo.get_account()
    if account:
        cert_path = account.get("cert_path", "")
        key_path = account.get("key_path", "")
    else:
        cert_path = await _history_repo.get_setting("cert_path") or ""
        key_path = await _history_repo.get_setting("key_path") or ""

    return CertificateStatusResponse(
        cert_exists=bool(cert_path) and Path(cert_path).is_file(),
        key_exists=bool(key_path) and Path(key_path).is_file(),
    )


# ---------------------------------------------------------------------------
# Routes — LeapConnect User
# ---------------------------------------------------------------------------


@app.post("/api/setup/user", response_model=UserCreateResponse)
async def create_user(request: Request) -> Response:
    """Create a LeapConnect application user."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="DB not ready")

    body = await request.json()
    display_name = body.get("display_name", "").strip()
    password = body.get("password", "").strip()

    if not display_name or not password:
        raise HTTPException(
            status_code=422, detail="display_name and password are required"
        )
    if len(password) < 4:
        raise HTTPException(
            status_code=422, detail="Password must be at least 4 characters"
        )

    existing = await _history_repo.get_user()
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")

    user = await _history_repo.create_user(display_name, password)

    # Auto-login: create session for the new user
    token = _create_session()
    resp = JSONResponse(
        content=UserCreateResponse(
            status="ok", display_name=user["display_name"]
        ).model_dump()
    )
    resp.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="strict",
    )
    return resp


# ---------------------------------------------------------------------------
# Routes — Authentication
# ---------------------------------------------------------------------------


@app.post("/api/auth/login", response_model=AuthLoginResponse)
async def auth_login(request: Request) -> Response:
    """Authenticate with the LeapConnect user password."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="DB not ready")

    body = await request.json()
    password = body.get("password", "").strip()

    if not password:
        raise HTTPException(status_code=422, detail="Password is required")

    valid = await _history_repo.verify_user_password(password)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid password")

    user = await _history_repo.get_user()
    token = _create_session()
    resp = JSONResponse(
        content=AuthLoginResponse(
            status="ok",
            display_name=user["display_name"] if user else "",
        ).model_dump()
    )
    resp.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="strict",
    )
    return resp


@app.post("/api/auth/logout", response_model=StatusResponse)
async def auth_logout(request: Request) -> Response:
    """Logout from the LeapConnect session."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    _invalidate_session(token)
    resp = JSONResponse(content=StatusResponse(status="ok").model_dump())
    resp.delete_cookie(key=SESSION_COOKIE_NAME)
    return resp


@app.get("/api/setup/user", response_model=UserInfoResponse)
async def get_user_info() -> UserInfoResponse:
    """Get current LeapConnect user info."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="DB not ready")

    user = await _history_repo.get_user()
    return UserInfoResponse(
        has_user=user is not None,
        display_name=user["display_name"] if user else None,
    )


@app.put("/api/setup/user", response_model=UserUpdateResponse)
async def update_user(request: Request) -> UserUpdateResponse:
    """Update LeapConnect user display name and/or password."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="DB not ready")

    body = await request.json()
    display_name = body.get("display_name")
    password = body.get("password")
    current_password = body.get("current_password", "").strip()

    if not current_password:
        raise HTTPException(status_code=422, detail="current_password is required")

    if not await _history_repo.verify_user_password(current_password):
        raise HTTPException(status_code=403, detail="Current password is incorrect")

    if display_name is not None:
        display_name = display_name.strip()
        if not display_name:
            raise HTTPException(status_code=422, detail="display_name cannot be empty")

    if password is not None:
        password = password.strip()
        if len(password) < 4:
            raise HTTPException(
                status_code=422,
                detail="Password must be at least 4 characters",
            )

    user = await _history_repo.update_user(display_name=display_name, password=password)
    if not user:
        raise HTTPException(status_code=404, detail="No user found")

    return UserUpdateResponse(status="ok", display_name=user["display_name"])


@app.post("/api/setup/account", response_model=AccountSetupResponse)
async def save_account(request: Request) -> AccountSetupResponse:
    """Save account credentials and attempt to connect."""
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

        return AccountSetupResponse(
            status="ok",
            connected=True,
            vehicles=[VehicleSchema.from_model(v) for v in _vehicles],
        )
    except Exception as exc:
        # Credentials saved but connection failed — that's ok, app works offline
        _connected = False
        _sync_client = None
        _client = None
        _vehicles = []
        if _scheduler:
            _scheduler.set_client(None, [])
        return AccountSetupResponse(
            status="ok",
            connected=False,
            connection_error=str(exc),
            vehicles=[],
        )


@app.post("/api/reconnect", response_model=ReconnectResponse)
async def reconnect() -> ReconnectResponse:
    """Reconnect using previously saved credentials."""
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

        return ReconnectResponse(
            status="ok",
            connected=True,
            vehicles=[VehicleSchema.from_model(v) for v in _vehicles],
        )
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


@app.post("/api/login", response_model=LoginResponse)
async def login(request: Request) -> LoginResponse:
    """Authenticate with Leapmotor using email and password."""
    global _sync_client, _client, _vehicles, _connected

    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()

    if not all([username, password]):
        raise HTTPException(status_code=422, detail="Missing email or password")

    if not _history_repo:
        raise HTTPException(status_code=503, detail="DB not ready")

    # Certificate paths from DB (uploaded via /api/setup/certificates)
    account = await _history_repo.get_account()
    if account:
        app_cert_path = account.get("cert_path", "")
        app_key_path = account.get("key_path", "")
        account_p12_password = account.get("p12_password")
    else:
        app_cert_path = await _history_repo.get_setting("cert_path") or ""
        app_key_path = await _history_repo.get_setting("key_path") or ""
        account_p12_password = None

    if not app_cert_path or not app_key_path:
        raise HTTPException(
            status_code=500,
            detail="Certificates not configured. Upload them via setup first.",
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

        return LoginResponse(
            status="ok",
            user_id=_sync_client.user_id,
            vehicles=[VehicleSchema.from_model(v) for v in _vehicles],
        )
    except Exception as exc:
        _connected = False
        _sync_client = None
        _client = None
        _vehicles = []
        if _scheduler:
            _scheduler.set_client(None, [])
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.post("/api/set-pin", response_model=SetPinResponse)
async def set_pin(request: Request) -> SetPinResponse:
    """Set the vehicle operation PIN required for remote controls."""
    if not _sync_client:
        raise HTTPException(status_code=400, detail="Not connected")
    body = await request.json()
    pin = body.get("pin", "").strip()
    if not pin:
        raise HTTPException(status_code=422, detail="PIN is required")
    _sync_client.operation_password = pin
    return SetPinResponse(status="ok", has_pin=True)


@app.post("/api/logout", response_model=StatusResponse)
async def logout() -> StatusResponse:
    """Disconnect from the Leapmotor API and clear session data."""
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
    return StatusResponse(status="ok")


@app.get("/api/status", response_model=ConnectionStatusResponse)
async def connection_status() -> ConnectionStatusResponse:
    """Get current connection status, account info, and vehicle list."""
    has_account = False
    has_user = False
    display_name = None
    leapmotor_email = None
    if _history_repo:
        account = await _history_repo.get_account()
        has_account = account is not None
        leapmotor_email = account["username"] if account else None
        user = await _history_repo.get_user()
        has_user = user is not None
        display_name = user["display_name"] if user else None
    return ConnectionStatusResponse(
        connected=_connected,
        has_account=has_account,
        has_user=has_user,
        user_id=_sync_client.user_id if _sync_client else None,
        leapmotor_email=leapmotor_email,
        display_name=display_name,
        vehicles=[VehicleSchema.from_model(v) for v in _vehicles],
        has_pin=bool(_sync_client and _sync_client.operation_password),
    )


# ---------------------------------------------------------------------------
# Routes — Vehicle Data
# ---------------------------------------------------------------------------


@app.get("/api/vehicles")
async def get_vehicles():
    client = _get_client()
    global _vehicles
    _vehicles = await client.get_vehicle_list()
    return VehicleListResponse(
        vehicles=[VehicleSchema.from_model(v) for v in _vehicles]
    )


@app.get("/api/vehicles/{vin}/status", response_model=VehicleStatusResponse)
async def get_vehicle_status(vin: str) -> VehicleStatusResponse:
    """Get the current real-time status of a vehicle."""
    client = _get_client()
    vehicle = _find_vehicle(vin)
    status = await client.get_vehicle_status(vehicle)

    # Persist snapshot for historical tracking
    if _history_repo and isinstance(status, VehicleStatus):
        snapshot = VehicleSnapshot(
            vin=vin,
            timestamp=status.collect_time or datetime.utcnow(),
            battery_soc=status.battery.soc,
            battery_current=status.battery.battery_current,
            battery_voltage=status.battery.battery_voltage,
            battery_is_charging=status.is_charging,
            battery_dump_energy=status.battery.dump_energy,
            battery_expected_mileage=status.battery.expected_mileage,
            battery_charge_state=status.battery.charge_state.value
            if status.battery.charge_state
            else None,
            drive_is_parked=status.driving.is_parked,
            drive_speed=status.driving.speed,
            drive_total_mileage=status.driving.total_mileage,
            ignition_is_on1=status.ignition.bcm_key_position_on1
            if status.ignition
            else None,
            ignition_is_on2=status.ignition.bcm_key_position_on3
            if status.ignition
            else None,
            vehicle_is_charging=status.is_charging,
            vehicle_is_plugged=status.is_plugged,
            vehicle_is_regening=status.is_regening,
            vehicle_is_parked=status.is_parked,
            vehicle_is_locked=status.is_locked,
            vehicle_latitude=status.location.latitude,
            vehicle_longitude=status.location.longitude,
            climate_outdoor_temp=status.climate.outdoor_temp,
            tire_front_left_pressure=status.tires.front_left_kpa
            if status.tires
            else None,
            tire_front_right_pressure=status.tires.front_right_kpa
            if status.tires
            else None,
            tire_rear_left_pressure=status.tires.rear_left_kpa
            if status.tires
            else None,
            tire_rear_right_pressure=status.tires.rear_right_kpa
            if status.tires
            else None,
        )
        asyncio.create_task(_save_snapshot_safe(snapshot))

    return VehicleStatusResponse(status=VehicleStatusSchema.from_model(status))


async def _save_snapshot_safe(snapshot: VehicleSnapshot) -> None:
    """Fire-and-forget snapshot save; errors are logged, never raised."""
    try:
        await _history_repo.save_snapshot(snapshot)
    except Exception:
        _LOGGER.exception("Failed to save vehicle snapshot")


@app.get("/api/vehicles/{vin}/raw-status")
async def get_vehicle_raw_status(vin: str) -> dict:
    """Get the raw unprocessed status data from the API."""
    client = _get_client()
    vehicle = _find_vehicle(vin)
    raw = await client.get_vehicle_raw_status(vehicle)
    return raw


@app.get("/api/vehicles/{vin}/mileage")
async def get_mileage(vin: str) -> dict:
    """Get mileage and energy consumption details."""
    client = _get_client()
    vehicle = _find_vehicle(vin)
    data = await client.get_mileage_energy_detail(vehicle)
    return data


@app.get("/api/vehicles/{vin}/picture")
async def get_picture(vin: str) -> dict:
    """Get the car picture metadata and download key."""
    client = _get_client()
    vehicle = _find_vehicle(vin)
    data = await client.get_car_picture(vehicle)
    return data


@app.get("/api/vehicles/{vin}/picture/download")
async def download_picture(vin: str, key: str) -> Response:
    """Download the raw car picture ZIP package."""
    client = _get_client()
    data = await client.download_car_picture_package(picture_key=key)
    return Response(content=data, media_type="application/zip")


@app.get("/api/vehicles/{vin}/picture/image")
async def get_picture_image(vin: str) -> Response:
    """Download the car picture ZIP, extract and serve the main image."""
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
async def get_picture_package(vin: str) -> dict[str, str]:
    """Extract all images from the picture ZIP and return as data URIs."""
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
async def get_dynamic_picture(vin: str, charge_frame: int = 0) -> Response:
    """Compose a dynamic car image reflecting current vehicle status."""
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


@app.get("/api/vehicles/{vin}/full", response_model=FullVehicleDataResponse)
async def get_full_vehicle_data(vin: str) -> FullVehicleDataResponse:
    """Fetch status, mileage, and picture data for a vehicle in one call."""
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

    return FullVehicleDataResponse(
        vehicle=VehicleSchema.from_model(vehicle),
        status=VehicleStatusSchema.from_model(status) if status else None,
        mileage=mileage if isinstance(mileage, dict) else None,
        picture=picture if isinstance(picture, dict) else None,
        errors={
            "status": str(results[0]) if isinstance(results[0], Exception) else None,
            "mileage": str(results[1]) if isinstance(results[1], Exception) else None,
            "picture": str(results[2]) if isinstance(results[2], Exception) else None,
        },
        vehicle_raw=vehicle.raw,
        status_raw=status.raw if status else None,
    )


# ---------------------------------------------------------------------------
# Routes — Vehicle History
# ---------------------------------------------------------------------------


@app.get("/api/vehicles/{vin}/history", response_model=VehicleHistoryResponse)
async def get_vehicle_history(vin: str, days: int = 30) -> VehicleHistoryResponse:
    """Get historical vehicle snapshots for a given time period."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="History not available")
    snapshots = await _history_repo.get_history(vin, days=days)
    return VehicleHistoryResponse(
        vin=vin,
        days=days,
        count=len(snapshots),
        snapshots=[
            SnapshotSchema(
                timestamp=s.timestamp.isoformat(),
                battery_soc=s.battery_soc,
                battery_current=s.battery_current,
                battery_voltage=s.battery_voltage,
                battery_charging_power_kw=s.battery_charging_power_kw,
                battery_discharge_power_kw=s.battery_discharge_power_kw,
                battery_is_charging=s.battery_is_charging,
                battery_is_discharging=s.battery_is_discharging,
                battery_dump_energy=s.battery_dump_energy,
                battery_expected_mileage=s.battery_expected_mileage,
                battery_charge_state=s.battery_charge_state,
                drive_is_parked=s.drive_is_parked,
                drive_speed=s.drive_speed,
                drive_total_mileage=s.drive_total_mileage,
                vehicle_is_charging=s.vehicle_is_charging,
                vehicle_is_plugged=s.vehicle_is_plugged,
                vehicle_is_locked=s.vehicle_is_locked,
                vehicle_latitude=s.vehicle_latitude,
                vehicle_longitude=s.vehicle_longitude,
                climate_outdoor_temp=s.climate_outdoor_temp,
                tire_front_left_pressure=s.tire_front_left_pressure,
                tire_front_right_pressure=s.tire_front_right_pressure,
                tire_rear_left_pressure=s.tire_rear_left_pressure,
                tire_rear_right_pressure=s.tire_rear_right_pressure,
            )
            for s in snapshots
        ],
    )


@app.get("/api/vehicles/{vin}/history/daily", response_model=DailySummaryResponse)
async def get_vehicle_daily_summary(vin: str, days: int = 30) -> DailySummaryResponse:
    """Get aggregated daily summaries for charts and statistics."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="History not available")
    summaries = await _history_repo.get_daily_summary(vin, days=days)
    return DailySummaryResponse(
        vin=vin,
        days=days,
        count=len(summaries),
        daily=summaries,
    )


# ---------------------------------------------------------------------------
# Routes — Scheduler Settings
# ---------------------------------------------------------------------------


@app.get("/api/scheduler", response_model=SchedulerStatusResponse)
async def get_scheduler_status() -> SchedulerStatusResponse:
    """Get current background data collection scheduler status."""
    if not _scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not available")
    return _scheduler.status_dict()


@app.put("/api/scheduler", response_model=SchedulerStatusResponse)
async def update_scheduler_settings(request: Request) -> SchedulerStatusResponse:
    """Enable/disable or change the interval of background data collection."""
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
async def lock_vehicle(vin: str) -> dict:
    """Lock the vehicle remotely."""
    client = _get_client()
    return await client.lock_vehicle(vin)


@app.post("/api/vehicles/{vin}/unlock")
async def unlock_vehicle(vin: str) -> dict:
    """Unlock the vehicle remotely."""
    client = _get_client()
    return await client.unlock_vehicle(vin)


@app.post("/api/vehicles/{vin}/trunk/open")
async def open_trunk(vin: str) -> dict:
    """Open the trunk remotely."""
    client = _get_client()
    return await client.open_trunk(vin)


@app.post("/api/vehicles/{vin}/trunk/close")
async def close_trunk(vin: str) -> dict:
    """Close the trunk remotely."""
    client = _get_client()
    return await client.close_trunk(vin)


@app.post("/api/vehicles/{vin}/find")
async def find_vehicle(vin: str) -> dict:
    """Trigger the vehicle finder (flash lights and honk)."""
    client = _get_client()
    return await client.find_vehicle(vin)


class SunshadeRequest(BaseModel):
    value: str = "10"  # "0" (closed) to "10" (fully open)


@app.post("/api/vehicles/{vin}/sunshade")
async def control_sunshade(vin: str, body: SunshadeRequest | None = None) -> dict:
    """Control sunshade remotely with optional position (0-10)."""
    client = _get_client()
    value = body.value if body else "10"
    return await client.control_sunshade(vin, value=value)


@app.post("/api/vehicles/{vin}/sunshade/open")
async def open_sunshade(vin: str, body: SunshadeRequest | None = None) -> dict:
    """Open the sunshade remotely (optionally to a specific level)."""
    client = _get_client()
    value = body.value if body else None
    return await client.open_sunshade(vin, value=value)


@app.post("/api/vehicles/{vin}/sunshade/close")
async def close_sunshade(vin: str, body: SunshadeRequest | None = None) -> dict:
    """Close the sunshade remotely (optionally to a specific level)."""
    client = _get_client()
    value = body.value if body else None
    return await client.close_sunshade(vin, value=value)


@app.post("/api/vehicles/{vin}/battery-preheat")
async def battery_preheat(vin: str) -> dict:
    """Start battery preheating remotely."""
    client = _get_client()
    return await client.battery_preheat(vin)


class WindowsRequest(BaseModel):
    value: str = "100"  # "0" (closed) to "100" (fully open)


@app.post("/api/vehicles/{vin}/windows")
async def control_windows(vin: str, body: WindowsRequest | None = None) -> dict:
    """Control windows remotely with optional position (0-100)."""
    client = _get_client()
    value = body.value if body else "100"
    return await client.windows(vin, value=value)


@app.post("/api/vehicles/{vin}/windows/open")
async def open_windows(vin: str, body: WindowsRequest | None = None) -> dict:
    """Open all windows remotely (optionally to a specific percentage)."""
    client = _get_client()
    value = body.value if body else None
    return await client.open_windows(vin, value=value)


@app.post("/api/vehicles/{vin}/windows/close")
async def close_windows(vin: str, body: WindowsRequest | None = None) -> dict:
    """Close all windows remotely (optionally to a specific percentage)."""
    client = _get_client()
    value = body.value if body else None
    return await client.close_windows(vin, value=value)


class ClimateRequest(BaseModel):
    circle: str | None = None  # "in" or "out"
    mode: str | None = None  # "cold", "hot", "nohotcold"
    operate: str | None = None  # "manual" or "auto"
    position: str | None = None  # "all"
    temperature: str | None = None  # e.g. "24"
    windlevel: str | None = None  # e.g. "4"
    wshld: str | None = None  # "1" (normal) or "2" (defrost)


@app.post("/api/vehicles/{vin}/ac")
async def ac_switch(vin: str, body: ClimateRequest | None = None) -> dict:
    """Toggle the air conditioning on/off with optional parameters."""
    client = _get_client()
    params = {
        k: v for k, v in (body.model_dump() if body else {}).items() if v is not None
    } or None
    return await client.ac_switch(vin, params=params)


@app.post("/api/vehicles/{vin}/quick-cool")
async def quick_cool(vin: str, body: ClimateRequest | None = None) -> dict:
    """Activate quick cooling mode with optional parameter overrides."""
    client = _get_client()
    params = {
        k: v for k, v in (body.model_dump() if body else {}).items() if v is not None
    } or None
    return await client.quick_cool(vin, params=params)


@app.post("/api/vehicles/{vin}/quick-heat")
async def quick_heat(vin: str, body: ClimateRequest | None = None) -> dict:
    """Activate quick heating mode with optional parameter overrides."""
    client = _get_client()
    params = {
        k: v for k, v in (body.model_dump() if body else {}).items() if v is not None
    } or None
    return await client.quick_heat(vin, params=params)


@app.post("/api/vehicles/{vin}/defrost")
async def windshield_defrost(vin: str, body: ClimateRequest | None = None) -> dict:
    """Activate windshield defrost with optional parameter overrides."""
    client = _get_client()
    params = {
        k: v for k, v in (body.model_dump() if body else {}).items() if v is not None
    } or None
    return await client.windshield_defrost(vin, params=params)


@app.post("/api/vehicles/{vin}/charge-limit")
async def set_charge_limit(vin: str, request: Request) -> dict:
    """Set the maximum charge level (20–100%)."""
    client = _get_client()
    body = await request.json()
    limit = body.get("limit")
    if limit is None or not (20 <= int(limit) <= 100):
        raise HTTPException(
            status_code=422, detail="Charge limit must be between 20 and 100"
        )
    return await client.set_charge_limit(vin, int(limit))


@app.post("/api/vehicles/{vin}/send-destination")
async def send_destination(vin: str, request: Request) -> dict:
    """Send a navigation destination to the vehicle's infotainment system."""
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


@app.get("/api/messages", response_model=MessageListResponse)
async def get_messages(page_no: int = 1, page_size: int = 20) -> MessageListResponse:
    """Get paginated notification messages from the account."""
    client = _get_client()
    msg_list: MessageList = await client.get_message_list(
        page_no=page_no, page_size=page_size
    )
    return MessageListResponse(
        count=msg_list.count,
        page_no=page_no,
        page_size=page_size,
        messages=[MessageSchema.from_model(m) for m in msg_list.messages],
    )


@app.get("/api/messages/unread-count", response_model=UnreadCountResponse)
async def get_unread_message_count() -> UnreadCountResponse:
    """Get the number of unread notification messages."""
    client = _get_client()
    count = await client.get_unread_message_count()
    return UnreadCountResponse(unread=count)


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
