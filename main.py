"""Leapmotor Vehicle Dashboard — FastAPI backend.

Exposes the full Leapmotor API client through a REST interface and serves
the Vue.js SPA frontend in production.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import math
import os
import secrets
import shutil
import time
import tomllib
import zipfile
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from leapmotor_api import LeapmotorApiClient
from leapmotor_api.async_client import AsyncLeapmotorApiClient
from leapmotor_api.exceptions import LeapmotorApiError
from leapmotor_api.image import CarImagePackage
from leapmotor_api.models import MessageList, Vehicle, VehicleStatus
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect

from models import (
    Geofence,
    MqttSettings,
    NotificationChannel,
    NotificationPreference,
    UserPreferences,
    VehicleSnapshot,
)
from persistence.sqlite_adapter import SQLAlchemyVehicleHistoryRepository
from schemas import (
    AbrpStatusResponse,
    AccountSetupResponse,
    AccountTestResponse,
    AuthLoginResponse,
    CertificateFetchResponse,
    CertificateStatusResponse,
    CertificateUploadResponse,
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
    ConnectionStatusResponse,
    ConsumptionLastWeekResponse,
    ConsumptionWeeklyRankResponse,
    DailySummaryResponse,
    DatabaseSizeResponse,
    FullVehicleDataResponse,
    GeofenceCreate,
    GeofenceResponse,
    GeofenceUpdate,
    LiveRefreshStatusResponse,
    LoginResponse,
    MaintenanceAlertResponse,
    MaintenanceCostSummary,
    MaintenanceCustomItemCreate,
    MaintenanceLibraryItem,
    MaintenanceLibraryResponse,
    MaintenanceOverviewResponse,
    MaintenancePackImportRequest,
    MaintenancePackResponse,
    MaintenancePlanImportRequest,
    MaintenancePlanImportResult,
    MaintenancePlanItemResponse,
    MaintenancePlanItemUpdate,
    MaintenanceRecordCreate,
    MaintenanceRecordResponse,
    MaintenanceRecordUpdate,
    MaintenanceRepoCreate,
    MaintenanceRepoResponse,
    MessageListResponse,
    MessageSchema,
    MqttStatusResponse,
    MqttTestResponse,
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationChannelUpdate,
    NotificationEventStatus,
    NotificationPreferencesUpdate,
    PreferencesResponse,
    ReconnectResponse,
    SchedulerStatusResponse,
    SetPinResponse,
    SetupStatusResponse,
    StatusResponse,
    TelegramLinkTokenResponse,
    TelegramUserResponse,
    UnreadCountResponse,
    UserCreateResponse,
    UserInfoResponse,
    UserUpdateResponse,
    VehicleHistoryResponse,
    VehicleListResponse,
    VehicleSchema,
    VehicleSnapshotSchema,
    VehicleStatusResponse,
    VehicleStatusSchema,
)
from services.abrp import AbrpService
from services.maintenance_community import (
    CommunityError,
    discover_repo,
    fetch_pack_file,
    fetch_pack_url,
)
from services.maintenance_resolver import resolve_model
from services.maintenance_service import (
    OFFICIAL_REPO_URL,
    PACK_SCHEMA,
    compute_alerts,
    compute_cost_summary,
    due_soon_alerts,
    ensure_plan_generated,
    factory_items_for_model,
    normalize_pack,
    official_pack_for_model,
    pack_applies_to_model,
    summarize,
)
from services.mqtt_ha import HomeAssistantMqttService
from services.notification_dispatcher import (
    EVENT_CATALOG,
    NotificationDispatcher,
)
from services.scheduler import VehicleDataScheduler
from services.vehicle_cache import VehicleStatusCache

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)


def _migrate_legacy_db(target_path: str) -> None:
    """Auto-rename legacy history.db → leapconnect.db if needed."""
    if os.path.isfile(target_path):
        return  # Target already exists, nothing to do

    parent = os.path.dirname(target_path)
    legacy_path = os.path.join(parent, "history.db")
    if os.path.isfile(legacy_path):
        _LOGGER.info("Migrating legacy DB: %s → %s", legacy_path, target_path)
        os.rename(legacy_path, target_path)
        _LOGGER.info("Legacy DB migrated successfully")


# ---------------------------------------------------------------------------
# In-memory ring-buffer log handler for frontend log viewer
# ---------------------------------------------------------------------------
class _RingBufferHandler(logging.Handler):
    """Keeps the last N log records in memory and notifies WebSocket clients."""

    def __init__(self, capacity: int = 2000) -> None:
        super().__init__()
        from collections import deque

        self._buffer: deque[dict] = deque(maxlen=capacity)
        self._ws_clients: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Store reference to the main asyncio event loop."""
        self._loop = loop

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "ts": datetime.fromtimestamp(record.created).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "name": record.name,
            "message": self.format(record),
        }
        self._buffer.append(entry)
        # Schedule broadcast to connected WS clients
        loop = self._loop
        if not loop or not self._ws_clients:
            return
        for ws in list(self._ws_clients):
            try:
                loop.call_soon_threadsafe(loop.create_task, ws.send_json(entry))
            except Exception:
                self._ws_clients.discard(ws)

    def get_entries(self, limit: int = 200) -> list[dict]:
        """Return the last *limit* log entries."""
        entries = list(self._buffer)
        return entries[-limit:]

    def register_ws(self, ws: WebSocket) -> None:
        self._ws_clients.add(ws)

    def unregister_ws(self, ws: WebSocket) -> None:
        self._ws_clients.discard(ws)


_log_handler = _RingBufferHandler()
_log_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
_log_handler.setLevel(logging.DEBUG)
logging.getLogger().addHandler(_log_handler)


try:
    _APP_VERSION = tomllib.loads(
        (Path(__file__).parent / "pyproject.toml").read_text()
    )["project"]["version"]
except Exception:
    _APP_VERSION = "dev"

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

# On-disk cache for the static vehicle image, so it is fetched from the
# Leapmotor cloud only once per vehicle and then served from local storage.
_VEHICLE_IMAGE_DIR = DATA_DIR / "vehicle_images"
_IMAGE_MEDIA_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def _cached_vehicle_image(vin: str) -> Path | None:
    """Return the locally-cached image file for a VIN, or None if not cached."""
    if _VEHICLE_IMAGE_DIR.is_dir():
        for path in _VEHICLE_IMAGE_DIR.glob(f"{vin}.*"):
            if path.is_file():
                return path
    return None


_history_repo: SQLAlchemyVehicleHistoryRepository | None = None
_scheduler: VehicleDataScheduler | None = None
_mqtt_service: HomeAssistantMqttService | None = None
_abrp_service: AbrpService | None = None
_vehicle_cache: VehicleStatusCache | None = None
_notification_dispatcher: NotificationDispatcher | None = None

# Live refresh — periodic cache refresh for VINs with active WebSocket clients
_live_refresh_task: asyncio.Task | None = None
_live_refresh_interval: int = 30  # default 30s, 0 = disabled
_live_refresh_stop: asyncio.Event | None = None

# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------
_ws_connections: dict[str, set[WebSocket]] = {}  # vin -> set of WebSocket


async def _ws_broadcast(vin: str, data: dict) -> None:
    """Send a JSON message to all WebSocket clients subscribed to a VIN."""
    clients = _ws_connections.get(vin, set())
    dead: list[WebSocket] = []
    for ws in clients:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


async def _on_cache_update(
    vin: str,
    status: VehicleStatus,
    cache_age: float,
) -> None:
    """Called by VehicleStatusCache when fresh data is fetched from API."""
    payload = {
        "type": "status_update",
        "vin": vin,
        "status": VehicleStatusSchema.from_model(status).model_dump(
            mode="json",
        ),
        "cache_age_seconds": round(cache_age, 1),
    }
    await _ws_broadcast(vin, payload)


# ---------------------------------------------------------------------------
# Live refresh — pushes fresh data to connected WebSocket clients
# ---------------------------------------------------------------------------


async def _live_refresh_loop() -> None:
    """Periodically refresh vehicle cache for VINs with active WS clients."""
    global _live_refresh_interval
    _LOGGER.info("Live refresh started (interval=%d sec)", _live_refresh_interval)
    try:
        while _live_refresh_interval > 0:
            await asyncio.sleep(_live_refresh_interval)
            if _live_refresh_stop and _live_refresh_stop.is_set():
                break
            if not _vehicle_cache or not _vehicles:
                continue
            # Only refresh VINs with active WebSocket connections
            active_vins = {vin for vin, conns in _ws_connections.items() if conns}
            if not active_vins:
                continue
            for vehicle in _vehicles:
                if vehicle.vin in active_vins:
                    try:
                        await _vehicle_cache.get(vehicle)
                    except Exception as exc:
                        _LOGGER.debug(
                            "Live refresh failed for %s: %s", vehicle.vin, exc
                        )
    except asyncio.CancelledError:
        pass
    finally:
        _LOGGER.info("Live refresh loop stopped")


def _start_live_refresh() -> None:
    """Start (or restart) the live refresh background task."""
    global _live_refresh_task, _live_refresh_stop
    _stop_live_refresh()
    if _live_refresh_interval <= 0:
        return
    _live_refresh_stop = asyncio.Event()
    _live_refresh_task = asyncio.create_task(_live_refresh_loop(), name="live-refresh")


def _stop_live_refresh() -> None:
    """Stop the live refresh background task if running."""
    global _live_refresh_task, _live_refresh_stop
    if _live_refresh_stop:
        _live_refresh_stop.set()
    if _live_refresh_task and not _live_refresh_task.done():
        _live_refresh_task.cancel()
    _live_refresh_task = None
    _live_refresh_stop = None


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

        # Restore saved vehicle PIN for MQTT commands
        if _history_repo:
            saved_pin = await _history_repo.get_setting("mqtt_vehicle_pin")
            if saved_pin and _sync_client:
                _sync_client.operation_password = saved_pin
                _LOGGER.info("Auto-connect: vehicle PIN restored from DB")

        # Start scheduler with the connected client
        if _scheduler:
            _scheduler.set_client(_client, _vehicles)
            _scheduler.start()

        # Wire ABRP service to vehicle cache
        if _abrp_service:
            _abrp_service.set_vehicles(_vehicles, _vehicle_cache)
    except Exception as exc:
        _LOGGER.warning("Auto-connect: failed (%s), app will run offline", exc)
        _connected = False
        _sync_client = None
        _client = None
        _vehicles = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global \
        _history_repo, \
        _scheduler, \
        _mqtt_service, \
        _vehicle_cache, \
        _notification_dispatcher
    # Capture the running event loop for thread-safe log broadcasting
    _log_handler.set_loop(asyncio.get_running_loop())

    db_path = os.environ.get(
        "HISTORY_DB_PATH", str(Path(__file__).parent / "leapconnect.db")
    )

    # Auto-migrate from legacy history.db to leapconnect.db
    _migrate_legacy_db(db_path)

    db_url = f"sqlite+aiosqlite:///{db_path}"
    _history_repo = SQLAlchemyVehicleHistoryRepository(db_url)
    await _history_repo.init_db()
    _LOGGER.info("History DB initialised at %s", db_path)

    # Restore scheduler settings from DB
    saved = await _history_repo.load_scheduler_settings()

    # Initialize shared vehicle status cache
    _vehicle_cache = VehicleStatusCache(rate_limit_seconds=saved.rate_limit_seconds)
    _vehicle_cache.set_on_update(_on_cache_update)

    # Initialize notification dispatcher
    _notification_dispatcher = NotificationDispatcher(
        repo=_history_repo,
        image_composer=_compose_notification_image,
        vehicle_cache=_vehicle_cache,
        command_executor=_execute_vehicle_command,
        rights_checker=_check_command_right,
        pin_checker=lambda: bool(_sync_client and _sync_client.operation_password),
        pin_setter=_set_vehicle_pin,
    )
    await _notification_dispatcher.reload_config()

    _scheduler = VehicleDataScheduler(
        _history_repo,
        cache=_vehicle_cache,
        notification_dispatcher=_notification_dispatcher,
    )
    _scheduler.update_settings(
        enabled=saved.enabled,
        interval_minutes=saved.interval_minutes,
        mqtt_interval_seconds=saved.mqtt_interval_seconds,
        rate_limit_seconds=saved.rate_limit_seconds,
        transition_detection_enabled=saved.transition_detection_enabled,
        transition_poll_interval_seconds=saved.transition_poll_interval_seconds,
        transition_min_event_interval_seconds=saved.transition_min_event_interval_seconds,
    )
    _LOGGER.info(
        "Scheduler settings loaded: enabled=%s, history=%d min,"
        " mqtt=%d sec, rate_limit=%d sec, transition=%s (poll=%ds, dedup=%ds)",
        saved.enabled,
        saved.interval_minutes,
        saved.mqtt_interval_seconds,
        saved.rate_limit_seconds,
        saved.transition_detection_enabled,
        saved.transition_poll_interval_seconds,
        saved.transition_min_event_interval_seconds,
    )

    # Initialize MQTT Home Assistant service
    _mqtt_service = HomeAssistantMqttService()
    _mqtt_service.set_command_callback(_handle_mqtt_command)
    _mqtt_service.set_settings_callback(_handle_mqtt_settings)
    mqtt_settings = await _load_mqtt_settings()
    _mqtt_service.update_settings(
        enabled=mqtt_settings.enabled,
        broker=mqtt_settings.broker,
        port=mqtt_settings.port,
        username=mqtt_settings.username,
        password=mqtt_settings.password,
        use_tls=mqtt_settings.use_tls,
        discovery_prefix=mqtt_settings.discovery_prefix,
        topic_prefix=mqtt_settings.topic_prefix,
    )
    _LOGGER.info("MQTT HA service initialised: enabled=%s", mqtt_settings.enabled)

    # Sync the MQTT polling interval so discovery publishes the correct value
    _mqtt_service._mqtt_interval_seconds = saved.mqtt_interval_seconds

    # Wire scheduler → MQTT publishing
    async def _on_scheduler_status(vehicle, status):
        if _mqtt_service and _mqtt_service.is_connected:
            image_pkg = _image_packages.get(vehicle.vin)
            if not image_pkg:
                with suppress(Exception):
                    image_pkg = await _get_image_package(vehicle.vin)
            await _mqtt_service.publish_vehicle_status(vehicle, status, image_pkg)

            # Publish cloud stats (consumption rank + weekly breakdown)
            try:
                client = _get_client()
                cloud_stats: dict = {}
                with suppress(Exception):
                    rank_result = await client.get_consumption_weekly_rank(vehicle)
                    if rank_result and rank_result.rank:
                        cloud_stats["consumption_rank"] = rank_result.rank.rank
                        cloud_stats["consumption_kwh_100km"] = (
                            rank_result.rank.hundred_km_ec
                        )
                with suppress(Exception):
                    breakdown = await client.get_consumption_last_week_breakdown(
                        vehicle
                    )
                    if breakdown:
                        cloud_stats["weekly_total_ec"] = breakdown.total_ec
                        cloud_stats["weekly_driver_ec"] = breakdown.driver_ec
                        cloud_stats["weekly_ac_ec"] = breakdown.ac_ec
                        cloud_stats["weekly_other_ec"] = breakdown.other_ec
                if cloud_stats:
                    await _mqtt_service.publish_cloud_stats(vehicle.vin, cloud_stats)
            except Exception as exc:
                _LOGGER.debug("Cloud stats MQTT publish skipped: %s", exc)

    _scheduler.set_on_status_callback(_on_scheduler_status)

    # Initialize ABRP telemetry service
    global _abrp_service
    _abrp_service = AbrpService()
    abrp_settings = await _load_abrp_settings()
    _abrp_service.update_settings(
        enabled=abrp_settings.enabled,
        user_token=abrp_settings.user_token,
    )
    _LOGGER.info("ABRP service initialised: enabled=%s", abrp_settings.enabled)

    # Initialize live refresh from saved setting
    global _live_refresh_interval
    live_raw = await _history_repo.get_setting("live_refresh_interval")
    _live_refresh_interval = int(live_raw) if live_raw else 30
    _LOGGER.info("Live refresh interval: %d sec", _live_refresh_interval)

    # Auto-connect using saved credentials
    await _auto_connect()

    # Start live refresh if configured (needs client from auto-connect)
    if _live_refresh_interval > 0 and _connected:
        _start_live_refresh()

    yield

    _stop_live_refresh()
    if _abrp_service:
        await _abrp_service.stop()
    if _mqtt_service:
        await _mqtt_service.stop()
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


@app.exception_handler(LeapmotorApiError)
async def leapmotor_api_error_handler(request: Request, exc: LeapmotorApiError):
    """Return a proper JSON 502 response for any unhandled LeapmotorApiError."""
    _LOGGER.warning(
        "LeapmotorApiError on %s %s: %s", request.method, request.url.path, exc
    )
    return JSONResponse(status_code=502, content={"detail": str(exc)})


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
        display_name=user.get("display_name") if user else None,
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


GITHUB_CERTS_REPO = "markoceri/leapmotor-certs"
GITHUB_CERTS_URL = f"https://github.com/{GITHUB_CERTS_REPO}"
GITHUB_CERTS_API = f"https://api.github.com/repos/{GITHUB_CERTS_REPO}/releases/latest"
GITHUB_UA = "LeapConnect"
GITHUB_ACCEPT_JSON = "application/vnd.github+json"

# Expected certificate filenames in the GitHub release assets
_CERT_ASSET_NAMES = {
    "app_cert.pem",
    "app.crt",
    "app_cert.crt",
}
_KEY_ASSET_NAMES = {
    "app_key.pem",
    "app.key",
    "app_key.key",
}


@app.post(
    "/api/setup/certificates/fetch",
    response_model=CertificateFetchResponse,
)
async def fetch_certificates_from_github() -> CertificateFetchResponse:
    """Download certificates from the leapmotor-certs GitHub release."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="DB not ready")

    CERTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            # Fetch the latest release metadata
            release_resp = await client.get(
                GITHUB_CERTS_API,
                headers={
                    "User-Agent": GITHUB_UA,
                    "Accept": GITHUB_ACCEPT_JSON,
                },
            )
            release_resp.raise_for_status()
            release = release_resp.json()

            tag = release.get("tag_name", "unknown")
            assets = release.get("assets", [])
            if not assets:
                raise HTTPException(
                    status_code=502,
                    detail="No assets found in GitHub release",
                )

            # Find cert and key assets by filename
            cert_url = None
            key_url = None
            for asset in assets:
                name = asset.get("name", "").lower()
                url = asset.get("browser_download_url")
                if name in _CERT_ASSET_NAMES and not cert_url:
                    cert_url = url
                elif name in _KEY_ASSET_NAMES and not key_url:
                    key_url = url

            if not cert_url:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Certificate asset not found in release. "
                        f"Expected one of: {', '.join(sorted(_CERT_ASSET_NAMES))}"
                    ),
                )
            if not key_url:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Private key asset not found in release. "
                        f"Expected one of: {', '.join(sorted(_KEY_ASSET_NAMES))}"
                    ),
                )

            # Download both files (GitHub redirects to SAS URLs)
            cert_resp = await client.get(cert_url, follow_redirects=True)
            cert_resp.raise_for_status()

            key_resp = await client.get(key_url, follow_redirects=True)
            key_resp.raise_for_status()

            cert_dest = CERTS_DIR / "app.crt"
            key_dest = CERTS_DIR / "app.key"

            cert_dest.write_bytes(cert_resp.content)
            key_dest.write_bytes(key_resp.content)
            key_dest.chmod(0o600)

            await _history_repo.save_setting("cert_path", str(cert_dest))
            await _history_repo.save_setting("key_path", str(key_dest))

            _LOGGER.info(
                "Certificates fetched from GitHub release %s",
                tag,
            )
            return CertificateFetchResponse(
                status="ok",
                cert_path=str(cert_dest),
                key_path=str(key_dest),
                source=f"{GITHUB_CERTS_URL}/releases/tag/{tag}",
            )

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"GitHub request failed: {exc}",
        ) from exc


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

        if _abrp_service:
            _abrp_service.set_vehicles(_vehicles, _vehicle_cache)

        # Start live refresh if configured
        if _live_refresh_interval > 0:
            _start_live_refresh()

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


@app.post("/api/setup/account/test", response_model=AccountTestResponse)
async def test_account(request: Request) -> AccountTestResponse:
    """Test Leapmotor credentials without saving them."""
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

    # Attempt a temporary connection (do NOT affect the global client)
    test_sync = None
    test_async = None
    try:
        test_sync = LeapmotorApiClient(
            username=username,
            password=password,
            app_cert_path=cert_path,
            app_key_path=key_path,
            account_p12_password=p12_password,
        )
        test_async = AsyncLeapmotorApiClient(test_sync)
        await test_async.login()
        test_vehicles = await test_async.get_vehicle_list()

        return AccountTestResponse(
            status="ok",
            connected=True,
            vehicles=[VehicleSchema.from_model(v) for v in test_vehicles],
        )
    except Exception as exc:
        return AccountTestResponse(
            status="ok",
            connected=False,
            connection_error=str(exc),
            vehicles=[],
        )
    finally:
        # Always clean up the temporary client
        if test_sync:
            with suppress(Exception):
                test_sync.close()


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

        if _abrp_service:
            _abrp_service.set_vehicles(_vehicles, _vehicle_cache)

        # Start live refresh if configured
        if _live_refresh_interval > 0:
            _start_live_refresh()

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


@app.post("/api/disconnect", response_model=StatusResponse)
async def disconnect() -> StatusResponse:
    """Disconnect from the Leapmotor cloud without clearing session."""
    global _sync_client, _client, _connected
    _stop_live_refresh()
    if _scheduler:
        _scheduler.set_client(None, [])
    if _abrp_service:
        _abrp_service.set_vehicles([], None)
    if _sync_client:
        _sync_client.close()
    _sync_client = None
    _client = None
    _connected = False
    return StatusResponse(status="ok")


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

        # Start live refresh if configured
        if _live_refresh_interval > 0:
            _start_live_refresh()

        return LoginResponse(
            status="ok",
            user_id=_sync_client.user_id,
            vehicles=[VehicleSchema.from_model(v) for v in _vehicles],
            display_name=(
                (await _history_repo.get_user() or {}).get("display_name")
                if _history_repo
                else None
            ),
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
    # Also persist for HA / auto-connect
    await _save_mqtt_vehicle_pin(pin)
    return SetPinResponse(status="ok", has_pin=True)


@app.get("/api/vehicle-pin")
async def get_vehicle_pin() -> dict:
    """Get the saved vehicle PIN status and masked value."""
    saved_pin = None
    if _history_repo:
        saved_pin = await _history_repo.get_setting("mqtt_vehicle_pin")
    runtime_pin = _sync_client.operation_password if _sync_client else None
    pin = saved_pin or runtime_pin
    return {
        "has_pin": bool(pin),
        "pin": pin or "",
    }


@app.put("/api/vehicle-pin")
async def update_vehicle_pin(request: Request) -> dict:
    """Save or clear the vehicle operation PIN."""
    body = await request.json()
    pin = str(body.get("pin", "")).strip()
    await _save_mqtt_vehicle_pin(pin)
    if _sync_client and pin:
        _sync_client.operation_password = pin
    return {"has_pin": bool(pin), "pin": pin}


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
        app_version=_APP_VERSION,
    )


# ---------------------------------------------------------------------------
# WebSocket — real-time vehicle status push
# ---------------------------------------------------------------------------


@app.websocket("/ws/vehicle/{vin}")
async def ws_vehicle_status(websocket: WebSocket, vin: str) -> None:
    """Push real-time status updates to the frontend for a vehicle."""
    # Validate session from query param or cookie
    token = websocket.query_params.get(
        "token",
    ) or websocket.cookies.get(SESSION_COOKIE_NAME)
    if not _validate_session(token):
        await websocket.close(code=4401, reason="Unauthorized")
        return

    await websocket.accept()

    # Register this connection
    if vin not in _ws_connections:
        _ws_connections[vin] = set()
    _ws_connections[vin].add(websocket)

    _LOGGER.info("WebSocket connected for VIN %s", vin)
    try:
        # Keep connection alive — read messages (pings / close)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_connections.get(vin, set()).discard(websocket)
        _LOGGER.info("WebSocket disconnected for VIN %s", vin)


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

    # Use shared cache if available (respects rate limit + single-flight)
    if _vehicle_cache:
        status = await _vehicle_cache.get(vehicle)
    else:
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

    # Publish to MQTT / Home Assistant
    if (
        _mqtt_service
        and _mqtt_service.is_connected
        and isinstance(status, VehicleStatus)
    ):
        asyncio.create_task(_mqtt_publish_status(vin, status))

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
async def get_picture_image(vin: str, refresh: bool = False) -> Response:
    """Serve the main car image, caching it on the server's local disk.

    The image is downloaded from the Leapmotor cloud only on the first request
    per vehicle (or when ``refresh=1``); afterwards it is served from local
    storage without contacting the cloud.
    """
    vehicle = _find_vehicle(vin)

    # Serve from local disk if already cached.
    if not refresh:
        cached = _cached_vehicle_image(vin)
        if cached is not None:
            media_type = _IMAGE_MEDIA_TYPES.get(
                cached.suffix.lstrip(".").lower(), "image/png"
            )
            return Response(
                content=cached.read_bytes(),
                media_type=media_type,
                headers={"Cache-Control": "public, max-age=86400"},
            )

    # Cache miss — fetch from the cloud once.
    client = _get_client()
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
    if ext not in _IMAGE_MEDIA_TYPES:
        ext = "png"
    media_type = _IMAGE_MEDIA_TYPES[ext]

    # Persist to local disk for subsequent requests (best-effort).
    try:
        _VEHICLE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        for stale in _VEHICLE_IMAGE_DIR.glob(f"{vin}.*"):
            stale.unlink()
        (_VEHICLE_IMAGE_DIR / f"{vin}.{ext}").write_bytes(img_data)
    except OSError as exc:
        _LOGGER.warning("Could not cache vehicle image for %s: %s", vin, exc)

    return Response(
        content=img_data,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
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


async def _compose_notification_image(vin: str) -> bytes | None:
    """Compose a dynamic vehicle image for notifications."""
    try:
        pkg = await _get_image_package(vin)
        vehicle = _find_vehicle(vin)
        if _vehicle_cache:
            status = await _vehicle_cache.get(vehicle)
        else:
            client = _get_client()
            status = await client.get_vehicle_status(vehicle)
        return await asyncio.to_thread(
            pkg.compose, status, charge_frame=0, format="PNG"
        )
    except Exception as exc:
        _LOGGER.warning("Failed to compose notification image for %s: %s", vin, exc)
        return None


# Command-to-right mapping (same as MQTT HA service)
_COMMAND_RIGHTS: dict[str, int | None] = {
    "lock": 110,
    "unlock": 110,
    "trunk_open": 130,
    "trunk_close": 130,
    "find": 120,
    "windows_open": 230,
    "windows_close": 230,
    "charging_start": 193,
    "charging_stop": 193,
    "battery_preheat": 190,
    "battery_preheat_off": 190,
    "unlock_charger": 192,
    "sunroof_open": 160,
    "sunroof_close": 160,
    "defrost": 170,
    "ac_on": None,
    "ac_off": None,
    "sentry_mode_on": None,
    "sentry_mode_off": None,
    "steering_wheel_heat_on": None,
    "steering_wheel_heat_off": None,
}

# Ability → Rights mapping (mirrors mqtt_ha)
_ABILITY_TO_RIGHTS: dict[int, list[int]] = {
    1: [110],
    2: [120],
    3: [130],
    4: [150],
    6: [170],
    9: [171],
    10: [190],
    11: [161],
    12: [230],
    14: [301],
    15: [320],
    17: [170, 171],
    18: [460],
    24: [130],
    25: [160],
    30: [180],
    34: [510],
    35: [340],
    36: [230],
    38: [360, 361],
    40: [380],
    42: [370],
    43: [370],
    48: [192],
    50: [220],
    52: [180],
}
_RIGHTS_WITH_ABILITY: set[int] = set()
for _rl in _ABILITY_TO_RIGHTS.values():
    _RIGHTS_WITH_ABILITY.update(_rl)


def _vehicle_has_right(vehicle: Vehicle, right: int | None) -> bool:
    """Check if a vehicle has the required right+ability permission."""
    if right is None:
        return True
    user_rights = {r.value if hasattr(r, "value") else int(r) for r in vehicle.rights}
    if right not in user_rights:
        return False
    if right in _RIGHTS_WITH_ABILITY:
        hw_rights: set[int] = set()
        for a in vehicle.abilities:
            a_val = a.value if hasattr(a, "value") else int(a)
            mapped = _ABILITY_TO_RIGHTS.get(a_val, [])
            hw_rights.update(mapped)
        if right not in hw_rights:
            return False
    return True


def _check_command_right(vin: str, command: str) -> bool:
    """Check if a command is permitted for the vehicle.

    Sync helper for menu filtering.
    """
    try:
        vehicle = _find_vehicle(vin)
    except Exception:
        return False
    required_right = _COMMAND_RIGHTS.get(command)
    return _vehicle_has_right(vehicle, required_right)


async def _execute_vehicle_command(vin: str, command: str) -> dict | None:
    """Execute a vehicle command by name. Used by Telegram bot handler.

    Checks vehicle rights/abilities before executing.
    Raises PermissionError if the command is not allowed.
    Returns None if the command is unknown.
    """
    if not _client:
        return None

    # Check permissions
    try:
        vehicle = _find_vehicle(vin)
    except Exception:
        return None

    required_right = _COMMAND_RIGHTS.get(command)
    if command in _COMMAND_RIGHTS and not _vehicle_has_right(vehicle, required_right):
        raise PermissionError(f"Command '{command}' not available for this vehicle")

    command_map = {
        "lock": _client.lock_vehicle,
        "unlock": _client.unlock_vehicle,
        "trunk_open": _client.open_trunk,
        "trunk_close": _client.close_trunk,
        "find": _client.find_vehicle,
        "windows_open": _client.open_windows,
        "windows_close": _client.close_windows,
        "charging_start": _client.start_charging,
        "charging_stop": _client.stop_charging,
        "battery_preheat": _client.battery_preheat,
        "battery_preheat_off": _client.battery_preheat_off,
        "unlock_charger": _client.unlock_charger,
        "sunroof_open": _client.open_sunroof,
        "sunroof_close": _client.close_sunroof,
        "defrost": _client.windshield_defrost,
        "ac_on": _client.ac_on,
        "ac_off": _client.ac_off,
        "sentry_mode_on": _client.sentry_mode_on,
        "sentry_mode_off": _client.sentry_mode_off,
        "steering_wheel_heat_on": _client.steering_wheel_heat_on,
        "steering_wheel_heat_off": _client.steering_wheel_heat_off,
    }
    fn = command_map.get(command)
    if not fn:
        return None
    return await fn(vin)


@app.get("/api/vehicles/{vin}/picture/dynamic")
async def get_dynamic_picture(vin: str, charge_frame: int = 0) -> Response:
    """Compose a dynamic car image reflecting current vehicle status."""
    client = _get_client()
    vehicle = _find_vehicle(vin)

    try:
        if _vehicle_cache:
            pkg, status_raw = await asyncio.gather(
                _get_image_package(vin),
                _vehicle_cache.get(vehicle),
            )
        else:
            pkg, status_raw = await asyncio.gather(
                _get_image_package(vin),
                client.get_vehicle_status(vehicle),
            )
    except LeapmotorApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

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

    status_task = (
        _vehicle_cache.get(vehicle)
        if _vehicle_cache
        else client.get_vehicle_status(vehicle)
    )
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
        cache_age_seconds=_vehicle_cache.cache_age(vin) if _vehicle_cache else None,
    )


# ---------------------------------------------------------------------------
# Routes — Maintenance: model resolution
# ---------------------------------------------------------------------------


async def _resolve_maintenance_model(vin: str, vehicle) -> dict:
    """Resolve the vehicle model, applying any persisted C10 variant override."""
    model_info = resolve_model(vehicle)
    if model_info.get("needs_confirmation") and _history_repo:
        override = await _history_repo.get_setting(f"c10_variant_{vin}")
        if override in ("bev", "reev"):
            model_info["model_key"] = "C10_REEV" if override == "reev" else "C10"
            model_info["variant"] = override
            model_info["confidence"] = "manual"
            model_info["needs_confirmation"] = False
    return model_info


async def _current_mileage_cached(vehicle) -> int | None:
    """Best-effort current odometer reading from the status cache."""
    if not _vehicle_cache:
        return None
    try:
        status = await _vehicle_cache.get(vehicle)
        return status.driving.total_mileage if (status and status.driving) else None
    except Exception:
        return None


async def _ensure_official_packs() -> list:
    """Return the official factory packs, registering the official repo on first use.

    The factory maintenance schedule lives in the community repo (no embedded
    catalog). This lazily registers and caches it. On any network/parse failure
    it logs and returns whatever is cached (possibly empty) so the app degrades
    gracefully instead of erroring.
    """
    if not _history_repo:
        return []
    repo = await _history_repo.get_maintenance_repo_by_url(OFFICIAL_REPO_URL)
    if repo is None:
        from models import MaintenanceRepo

        try:
            discovered = await discover_repo(OFFICIAL_REPO_URL)
        except CommunityError as exc:
            _LOGGER.warning("Official maintenance repo unavailable: %s", exc)
            return []
        repo = MaintenanceRepo(
            type=discovered["type"],
            url=discovered["url"],
            name=discovered["name"],
            author=discovered["author"],
            description=discovered.get("description"),
            branch=discovered["branch"],
            added_at=datetime.now(UTC),
            last_fetched_at=datetime.now(UTC),
            status="ok",
            manifest=discovered["packs"],
        )
        repo = await _history_repo.save_maintenance_repo(repo)
        await _cache_repo_packs(repo)
    return await _history_repo.list_maintenance_packs(repo.id)


async def _factory_items(model_key: str) -> list[dict]:
    """Return the factory service items for a model from the official packs."""
    return factory_items_for_model(await _ensure_official_packs(), model_key)


@app.get("/api/vehicles/{vin}/maintenance/model")
async def get_vehicle_maintenance_model(vin: str) -> dict:
    """Resolve the vehicle model for maintenance purposes.

    Returns the canonical model key, display name, variant (if C10),
    confidence level, and whether the user needs to confirm the C10 variant.
    """
    vehicle = _find_vehicle(vin)
    result = resolve_model(vehicle)
    return result


@app.post("/api/vehicles/{vin}/maintenance/model")
async def set_vehicle_maintenance_model(vin: str, body: dict) -> dict:
    """Override the C10 variant choice for a vehicle.

    Accepts JSON body: {"variant": "bev" | "reev"}
    Persisted per VIN via app settings.
    """
    variant = body.get("variant")
    if variant not in ("bev", "reev"):
        raise HTTPException(status_code=400, detail="variant must be 'bev' or 'reev'")

    vehicle = _find_vehicle(vin)
    # Persist the override
    if _history_repo:
        await _history_repo.save_setting(f"c10_variant_{vin}", variant)

    # Re-resolve with the override applied
    base = resolve_model(vehicle)
    if variant == "reev":
        base["model_key"] = "C10_REEV"
        base["display_name"] = "Leapmotor C10 REEV"
        base["variant"] = "reev"
    else:
        base["model_key"] = "C10"
        base["display_name"] = "Leapmotor C10"
        base["variant"] = "bev"
    base["confidence"] = "manual"
    base["needs_confirmation"] = False
    base["detection_reason"] = "user_override"
    return base


@app.get("/api/vehicles/{vin}/maintenance/rules")
async def get_vehicle_maintenance_rules(vin: str) -> dict:
    """Return the official factory maintenance schedule applicable to this vehicle."""
    vehicle = _find_vehicle(vin)
    model_info = await _resolve_maintenance_model(vin, vehicle)

    model_key = model_info.get("model_key", "unknown")
    pack = official_pack_for_model(await _ensure_official_packs(), model_key)

    if pack is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No official factory schedule found for model '{model_key}'. "
                "The official maintenance repository may be unreachable."
            ),
        )

    return {
        "model": model_info,
        "rules": pack.payload,
    }


# ---------------------------------------------------------------------------
# Routes — Maintenance Plan (CRUD)
# ---------------------------------------------------------------------------


@app.get("/api/vehicles/{vin}/maintenance/plan")
async def get_maintenance_plan(vin: str) -> list:
    """Get the maintenance plan for a vehicle. Auto-generates from catalog if empty."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")

    vehicle = _find_vehicle(vin)
    model_info = await _resolve_maintenance_model(vin, vehicle)
    model_key = model_info.get("model_key", "unknown")
    factory = await _factory_items(model_key)
    items = await ensure_plan_generated(_history_repo, vin, factory)

    return [MaintenancePlanItemResponse(**item.__dict__) for item in items]


@app.put("/api/vehicles/{vin}/maintenance/plan/{service_type}")
async def update_maintenance_plan_item(
    vin: str, service_type: str, body: MaintenancePlanItemUpdate
):
    """Update a single maintenance plan item."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")

    from models import MaintenancePlanItem

    item = MaintenancePlanItem(
        vin=vin,
        service_type=service_type,
        label="",
        enabled=body.enabled,
        interval_km=body.interval_km,
        interval_months=body.interval_months,
        trigger_mode=body.trigger_mode,
        priority=body.priority,
        last_done_km=body.last_done_km,
        last_done_date=body.last_done_date,
        notes=body.notes,
    )
    await _history_repo.upsert_maintenance_plan_item(vin, item)

    # Return the updated item
    plan = await _history_repo.get_maintenance_plan(vin)
    for p in plan:
        if p.service_type == service_type:
            return MaintenancePlanItemResponse(**p.__dict__)

    raise HTTPException(status_code=404, detail="Plan item not found after upsert")


# ---------------------------------------------------------------------------
# Routes — Maintenance Records (CRUD)
# ---------------------------------------------------------------------------


@app.get("/api/vehicles/{vin}/maintenance/records")
async def get_maintenance_records(
    vin: str, service_type: str | None = None, limit: int = 20
) -> list:
    """Get completed maintenance records for a vehicle."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")

    records = await _history_repo.get_maintenance_records(
        vin, service_type=service_type, limit=limit
    )
    return [MaintenanceRecordResponse(**r.__dict__) for r in records]


@app.post("/api/vehicles/{vin}/maintenance/records")
async def create_maintenance_record(vin: str, body: MaintenanceRecordCreate):
    """Log a completed maintenance intervention.

    If update_plan_item is True (default), the corresponding plan item's
    last_done_km and last_done_date are updated automatically.
    """
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")

    from models import MaintenanceRecord

    record = MaintenanceRecord(
        vin=vin,
        service_type=body.service_type,
        label=body.label or body.service_type,
        timestamp=body.timestamp or datetime.now(UTC),
        mileage_km=body.mileage_km,
        cost=body.cost,
        provider=body.provider,
        notes=body.notes,
    )
    await _history_repo.save_maintenance_record(record)

    # Auto-update plan item's last-done fields
    if body.update_plan_item and _history_repo:
        from models import MaintenancePlanItem

        update = MaintenancePlanItem(
            vin=vin,
            service_type=body.service_type,
            label="",
            last_done_km=body.mileage_km,
            last_done_date=record.timestamp,
        )
        await _history_repo.upsert_maintenance_plan_item(vin, update)

    return MaintenanceRecordResponse(**record.__dict__)


async def _recalc_plan_last_done(vin: str, service_type: str) -> None:
    """Set the plan item's last_done to its most recent remaining record.

    Uses ``set_plan_item_last_done`` (not upsert) so last_done is cleared to
    NULL when no records remain.
    """
    remaining = await _history_repo.get_maintenance_records(
        vin, service_type=service_type, limit=1
    )
    latest = remaining[0] if remaining else None
    await _history_repo.set_plan_item_last_done(
        vin,
        service_type,
        last_done_km=latest.mileage_km if latest else None,
        last_done_date=latest.timestamp if latest else None,
    )


@app.put("/api/vehicles/{vin}/maintenance/records/{record_id}")
async def edit_maintenance_record(
    vin: str, record_id: int, body: MaintenanceRecordUpdate
):
    """Update a maintenance record and recalculate the plan item's last-done."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")

    existing = await _history_repo.get_maintenance_record(record_id)
    if existing is None or existing.vin != vin:
        raise HTTPException(status_code=404, detail="Record not found")

    updated = await _history_repo.update_maintenance_record(
        record_id,
        timestamp=body.timestamp,
        mileage_km=body.mileage_km,
        cost=body.cost,
        provider=body.provider,
        notes=body.notes,
    )
    await _recalc_plan_last_done(vin, existing.service_type)
    return MaintenanceRecordResponse(**updated.__dict__)


@app.delete("/api/vehicles/{vin}/maintenance/records/{record_id}")
async def delete_maintenance_record(vin: str, record_id: int) -> dict:
    """Delete a maintenance record and recalculate the plan item's last-done."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")

    existing = await _history_repo.get_maintenance_record(record_id)
    if existing is None or existing.vin != vin:
        raise HTTPException(status_code=404, detail="Record not found")

    await _history_repo.delete_maintenance_record(record_id)
    await _recalc_plan_last_done(vin, existing.service_type)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Routes — Maintenance Overview
# ---------------------------------------------------------------------------


@app.get("/api/vehicles/{vin}/maintenance/overview")
async def get_maintenance_overview(vin: str):
    """Get a summary overview: model, plan, upcoming/overdue counts, next action."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")

    vehicle = _find_vehicle(vin)
    model_info = await _resolve_maintenance_model(vin, vehicle)
    model_key = model_info.get("model_key", "unknown")
    factory = await _factory_items(model_key)
    plan = await ensure_plan_generated(_history_repo, vin, factory)
    # All records (newest first): used for cost aggregation; first 5 are "recent".
    records = await _history_repo.get_maintenance_records(vin, limit=None)

    now_utc = datetime.now(UTC).replace(tzinfo=None)  # naive UTC for DB comparison
    current_km = await _current_mileage_cached(vehicle)
    costs = compute_cost_summary(records, plan, now_utc)

    alerts = compute_alerts(plan, current_km, now_utc)
    counts = summarize(alerts)
    shortlist = due_soon_alerts(alerts)
    next_item = None
    if shortlist:
        next_st = shortlist[0].service_type
        next_item = next(
            (
                MaintenancePlanItemResponse(**i.__dict__)
                for i in plan
                if i.service_type == next_st
            ),
            None,
        )

    return MaintenanceOverviewResponse(
        model_key=model_key,
        display_name=model_info.get("display_name", "Unknown"),
        variant=model_info.get("variant"),
        current_km=current_km,
        total_items=len([i for i in plan if i.enabled]),
        upcoming_count=counts["upcoming"],
        overdue_count=counts["overdue"],
        critical_count=counts["critical"],
        next_item=next_item,
        due_soon=[MaintenanceAlertResponse(**a.__dict__) for a in shortlist],
        costs=MaintenanceCostSummary(**costs),
        plan=[MaintenancePlanItemResponse(**item.__dict__) for item in plan],
        recent_records=[MaintenanceRecordResponse(**r.__dict__) for r in records[:5]],
    )


@app.get("/api/vehicles/{vin}/maintenance/current-mileage")
async def get_current_mileage(vin: str) -> dict:
    """Return the vehicle's current odometer reading (km),
    fetched fresh from the API."""
    client = _get_client()
    vehicle = _find_vehicle(vin)

    try:
        status = await client.get_vehicle_status(vehicle)
        mileage = status.driving.total_mileage if (status and status.driving) else None
    except LeapmotorApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"vin": vin, "mileage_km": mileage}


# ---------------------------------------------------------------------------
# Routes — Maintenance Library (catalog + local + community packs)
# ---------------------------------------------------------------------------


def _pack_to_response(pack, in_plan_types: set[str], model_key: str):
    """Build a MaintenancePackResponse from a cached MaintenancePack."""
    payload = pack.payload or {}
    items = []
    for it in payload.get("items", []):
        items.append(
            MaintenanceLibraryItem(
                **{
                    k: it.get(k) for k in MaintenanceLibraryItem.model_fields if k in it
                },
                origin="repo",
                origin_ref=pack.slug,
                in_plan=it.get("service_type") in in_plan_types,
            )
        )
    return MaintenancePackResponse(
        id=pack.id,
        repo_id=pack.repo_id,
        slug=pack.slug,
        name=pack.name or pack.slug,
        author=pack.author,
        version=pack.version,
        description=payload.get("description"),
        model_compat=pack.model_compat,
        items=items,
        applies=pack_applies_to_model(payload, model_key),
    )


@app.get("/api/vehicles/{vin}/maintenance/library")
async def get_maintenance_library(vin: str) -> MaintenanceLibraryResponse:
    """Aggregated browse surface: catalog + local items + community packs.

    Each item is flagged ``in_plan`` so the UI knows what's already imported.
    """
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")

    vehicle = _find_vehicle(vin)
    model_info = await _resolve_maintenance_model(vin, vehicle)
    model_key = model_info.get("model_key", "unknown")

    factory = await _factory_items(model_key)
    plan = await ensure_plan_generated(_history_repo, vin, factory)
    in_plan_types = {i.service_type for i in plan}

    # Catalog items: the official factory schedule for the vehicle's model.
    catalog: list[MaintenanceLibraryItem] = []
    for r in factory:
        catalog.append(
            MaintenanceLibraryItem(
                service_type=r["service_type"],
                label=r["label"],
                category=r.get("category", "other"),
                interval_km=r.get("interval_km"),
                interval_months=r.get("interval_months"),
                trigger_mode=r.get("trigger_mode", "or"),
                priority=r.get("priority", "routine"),
                origin="catalog",
                in_plan=r["service_type"] in in_plan_types,
            )
        )

    # Local items: user-created plan items.
    local = [
        MaintenanceLibraryItem(
            service_type=i.service_type,
            label=i.label,
            category=i.category,
            interval_km=i.interval_km,
            interval_months=i.interval_months,
            trigger_mode=i.trigger_mode,
            priority=i.priority,
            notes=i.notes,
            origin="local",
            in_plan=True,
        )
        for i in plan
        if i.source == "local"
    ]

    # The official repo (factory schedule source) is listed like any other,
    # flagged is_official so the UI can mark it and prevent its removal.
    repos = await _history_repo.list_maintenance_repos()
    all_packs = await _history_repo.list_maintenance_packs()
    packs_by_repo: dict[int | None, int] = {}
    for p in all_packs:
        packs_by_repo[p.repo_id] = packs_by_repo.get(p.repo_id, 0) + 1

    repo_responses = [
        MaintenanceRepoResponse(
            id=r.id,
            type=r.type,
            url=r.url,
            name=r.name,
            author=r.author,
            description=r.description,
            branch=r.branch,
            added_at=r.added_at,
            last_fetched_at=r.last_fetched_at,
            status=r.status,
            pack_count=packs_by_repo.get(r.id, 0),
            is_official=r.url == OFFICIAL_REPO_URL,
        )
        for r in repos
    ]

    pack_responses = [_pack_to_response(p, in_plan_types, model_key) for p in all_packs]

    return MaintenanceLibraryResponse(
        model_key=model_key,
        display_name=model_info.get("display_name", "Unknown"),
        variant=model_info.get("variant"),
        catalog=catalog,
        local=local,
        repos=repo_responses,
        packs=pack_responses,
    )


@app.post("/api/vehicles/{vin}/maintenance/plan/import")
async def import_maintenance_plan_items(
    vin: str, body: MaintenancePlanImportRequest
) -> MaintenancePlanImportResult:
    """Explicitly import service items into the vehicle's plan.

    Honours a per-item or request-level conflict strategy when a
    ``service_type`` already exists: ``update`` | ``variant`` | ``skip``.
    """
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")
    from models import MaintenancePlanItem

    existing = {i.service_type for i in await _history_repo.get_maintenance_plan(vin)}
    result = MaintenancePlanImportResult()

    for entry in body.items:
        strategy = entry.conflict or body.on_conflict
        service_type = entry.service_type
        conflict = service_type in existing

        if conflict and strategy == "skip":
            result.skipped.append(service_type)
            continue

        outcome = "imported"
        if conflict and strategy == "variant":
            n = 2
            while f"{service_type}_v{n}" in existing:
                n += 1
            service_type = f"{service_type}_v{n}"
            outcome = "variant"
        elif conflict:
            outcome = "updated"

        item = MaintenancePlanItem(
            vin=vin,
            service_type=service_type,
            label=entry.label,
            category=entry.category,
            interval_km=entry.interval_km,
            interval_months=entry.interval_months,
            trigger_mode=entry.trigger_mode,
            priority=entry.priority,
            notes=entry.notes,
            enabled=True,
            source=body.source,
            source_ref=body.source_ref,
        )
        await _history_repo.upsert_maintenance_plan_item(vin, item)
        existing.add(service_type)

        bucket = {
            "imported": result.imported,
            "updated": result.updated,
            "variant": result.variants,
        }[outcome]
        bucket.append(service_type)

    return result


@app.post("/api/vehicles/{vin}/maintenance/plan")
async def create_maintenance_custom_item(
    vin: str, body: MaintenanceCustomItemCreate
) -> MaintenancePlanItemResponse:
    """Create a user-defined (local) maintenance item in the plan."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")
    from models import MaintenancePlanItem

    existing = {i.service_type for i in await _history_repo.get_maintenance_plan(vin)}
    if body.service_type in existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A plan item with service_type '{body.service_type}' already exists"
            ),
        )

    item = MaintenancePlanItem(
        vin=vin,
        service_type=body.service_type,
        label=body.label,
        category=body.category,
        interval_km=body.interval_km,
        interval_months=body.interval_months,
        trigger_mode=body.trigger_mode,
        priority=body.priority,
        last_done_km=body.last_done_km,
        last_done_date=body.last_done_date,
        notes=body.notes,
        enabled=True,
        source="local",
    )
    await _history_repo.upsert_maintenance_plan_item(vin, item)
    for p in await _history_repo.get_maintenance_plan(vin):
        if p.service_type == body.service_type:
            return MaintenancePlanItemResponse(**p.__dict__)
    raise HTTPException(status_code=500, detail="Item not found after create")


@app.delete("/api/vehicles/{vin}/maintenance/plan/{service_type}")
async def delete_maintenance_plan_item(vin: str, service_type: str) -> dict:
    """Remove a plan item (un-import a community item or delete a custom one)."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")
    await _history_repo.delete_maintenance_plan_item(vin, service_type)
    return {"deleted": service_type}


@app.get("/api/vehicles/{vin}/maintenance/export")
async def export_local_maintenance(vin: str) -> Response:
    """Export the vehicle's local (user-defined) items as a shareable pack."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")

    plan = await _history_repo.get_maintenance_plan(vin)
    vehicle = _find_vehicle(vin)
    model_info = await _resolve_maintenance_model(vin, vehicle)

    items = [
        {
            "service_type": i.service_type,
            "label": i.label,
            "category": i.category,
            "interval_km": i.interval_km,
            "interval_months": i.interval_months,
            "trigger_mode": i.trigger_mode,
            "priority": i.priority,
            "notes": i.notes,
        }
        for i in plan
        if i.source == "local"
    ]
    pack = {
        "schema": PACK_SCHEMA,
        "name": f"{model_info.get('display_name', 'Vehicle')} — custom maintenance",
        "version": 1,
        "model_compat": [model_info.get("model_key", "unknown")],
        "items": items,
    }
    body = json.dumps(pack, indent=2, default=str)
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; "
            "filename=leapconnect-maintenance-local.json"
        },
    )


# ---------------------------------------------------------------------------
# Routes — Maintenance Community Repositories & Packs
# ---------------------------------------------------------------------------


async def _cache_repo_packs(repo) -> int:
    """Fetch every pack listed in a repo's manifest and cache it. Returns count."""
    from models import MaintenancePack

    count = 0
    for entry in repo.manifest or []:
        try:
            payload = await fetch_pack_file(repo.url, repo.branch, entry["file"])
        except (CommunityError, KeyError) as exc:
            _LOGGER.warning("Skipping pack %s in %s: %s", entry, repo.url, exc)
            continue
        pack = MaintenancePack(
            repo_id=repo.id,
            slug=entry.get("slug") or payload.get("name"),
            name=payload.get("name"),
            version=payload.get("version"),
            author=payload.get("author"),
            model_compat=payload.get("model_compat"),
            payload=payload,
        )
        await _history_repo.save_maintenance_pack(pack)
        count += 1
    return count


@app.get("/api/maintenance/repos")
async def list_maintenance_repos() -> list[MaintenanceRepoResponse]:
    """List all maintenance repositories, including the official one."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")
    repos = await _history_repo.list_maintenance_repos()
    packs = await _history_repo.list_maintenance_packs()
    counts: dict[int | None, int] = {}
    for p in packs:
        counts[p.repo_id] = counts.get(p.repo_id, 0) + 1
    return [
        MaintenanceRepoResponse(
            id=r.id,
            type=r.type,
            url=r.url,
            name=r.name,
            author=r.author,
            description=r.description,
            branch=r.branch,
            added_at=r.added_at,
            last_fetched_at=r.last_fetched_at,
            status=r.status,
            pack_count=counts.get(r.id, 0),
            is_official=r.url == OFFICIAL_REPO_URL,
        )
        for r in repos
    ]


@app.post("/api/maintenance/repos")
async def add_maintenance_repo(
    body: MaintenanceRepoCreate,
) -> MaintenanceRepoResponse:
    """Add a community repository: discover and cache its packs."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")
    from models import MaintenanceRepo

    try:
        discovered = await discover_repo(body.url)
    except CommunityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing = await _history_repo.get_maintenance_repo_by_url(discovered["url"])
    if existing:
        raise HTTPException(status_code=409, detail="Repository already added")

    repo = MaintenanceRepo(
        type=discovered["type"],
        url=discovered["url"],
        name=discovered["name"],
        author=discovered["author"],
        description=discovered.get("description"),
        branch=discovered["branch"],
        added_at=datetime.now(UTC),
        last_fetched_at=datetime.now(UTC),
        status="ok",
        manifest=discovered["packs"],
    )
    repo = await _history_repo.save_maintenance_repo(repo)
    count = await _cache_repo_packs(repo)

    return MaintenanceRepoResponse(
        id=repo.id,
        type=repo.type,
        url=repo.url,
        name=repo.name,
        author=repo.author,
        description=repo.description,
        branch=repo.branch,
        added_at=repo.added_at,
        last_fetched_at=repo.last_fetched_at,
        status=repo.status,
        pack_count=count,
        is_official=repo.url == OFFICIAL_REPO_URL,
    )


@app.post("/api/maintenance/repos/{repo_id}/refresh")
async def refresh_maintenance_repo(repo_id: int) -> MaintenanceRepoResponse:
    """Re-discover a repository's manifest and re-cache its packs."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")
    repo = await _history_repo.get_maintenance_repo(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    try:
        discovered = await discover_repo(repo.url)
    except CommunityError as exc:
        repo.status = "error"
        await _history_repo.save_maintenance_repo(repo)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    repo.name = discovered["name"]
    repo.author = discovered["author"]
    repo.description = discovered.get("description")
    repo.branch = discovered["branch"]
    repo.manifest = discovered["packs"]
    repo.last_fetched_at = datetime.now(UTC)
    repo.status = "ok"
    repo = await _history_repo.save_maintenance_repo(repo)

    # Drop old cached packs for this repo, then re-cache.
    for p in await _history_repo.list_maintenance_packs(repo_id):
        await _history_repo.delete_maintenance_pack(p.id)
    count = await _cache_repo_packs(repo)

    return MaintenanceRepoResponse(
        id=repo.id,
        type=repo.type,
        url=repo.url,
        name=repo.name,
        author=repo.author,
        description=repo.description,
        branch=repo.branch,
        added_at=repo.added_at,
        last_fetched_at=repo.last_fetched_at,
        status=repo.status,
        pack_count=count,
        is_official=repo.url == OFFICIAL_REPO_URL,
    )


@app.delete("/api/maintenance/repos/{repo_id}")
async def delete_maintenance_repo(repo_id: int) -> dict:
    """Remove a repository and all packs cached from it."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")
    existing = await _history_repo.get_maintenance_repo(repo_id)
    if existing and existing.url == OFFICIAL_REPO_URL:
        raise HTTPException(
            status_code=403,
            detail="The official factory repository cannot be removed",
        )
    await _history_repo.delete_maintenance_repo(repo_id)
    return {"deleted": repo_id}


@app.get("/api/maintenance/repos/{repo_id}/packs")
async def list_repo_packs(repo_id: int) -> list[MaintenancePackResponse]:
    """List the packs cached from a repository."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")
    packs = await _history_repo.list_maintenance_packs(repo_id)
    return [_pack_to_response(p, set(), "unknown") for p in packs]


@app.post("/api/maintenance/packs/import")
async def import_maintenance_pack(
    body: MaintenancePackImportRequest,
) -> MaintenancePackResponse:
    """Fetch/cache a standalone pack from a raw URL or inline JSON.

    For (repo_id + slug) the already-cached pack is returned.
    """
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")
    from models import MaintenancePack

    if body.repo_id is not None and body.slug:
        for p in await _history_repo.list_maintenance_packs(body.repo_id):
            if p.slug == body.slug:
                return _pack_to_response(p, set(), "unknown")
        raise HTTPException(status_code=404, detail="Pack not found in repository")

    try:
        if body.url:
            payload = await fetch_pack_url(body.url)
            slug = body.url.rstrip("/").split("/")[-1].replace(".json", "")
        elif body.inline is not None:
            payload = normalize_pack(body.inline)
            slug = (payload.get("name") or "imported").lower().replace(" ", "-")
        else:
            raise HTTPException(
                status_code=400,
                detail="Provide one of: repo_id+slug, url, or inline",
            )
    except CommunityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    pack = MaintenancePack(
        repo_id=None,
        slug=slug,
        name=payload.get("name"),
        version=payload.get("version"),
        author=payload.get("author"),
        model_compat=payload.get("model_compat"),
        payload=payload,
    )
    pack = await _history_repo.save_maintenance_pack(pack)
    return _pack_to_response(pack, set(), "unknown")


@app.post("/api/maintenance/upload")
async def upload_maintenance_pack(
    file: UploadFile = File(...),  # noqa: B008
) -> MaintenancePackResponse:
    """Upload a maintenance pack JSON file and cache it as a standalone pack."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="Persistence not available")
    from models import MaintenancePack

    raw = await file.read()
    try:
        payload = normalize_pack(json.loads(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid pack: {exc}") from exc

    slug = (file.filename or payload.get("name") or "uploaded").rsplit("/", 1)[-1]
    slug = slug.replace(".json", "")
    pack = MaintenancePack(
        repo_id=None,
        slug=slug,
        name=payload.get("name"),
        version=payload.get("version"),
        author=payload.get("author"),
        model_compat=payload.get("model_compat"),
        payload=payload,
    )
    pack = await _history_repo.save_maintenance_pack(pack)
    return _pack_to_response(pack, set(), "unknown")


# ---------------------------------------------------------------------------
# Routes — Vehicle History
# ---------------------------------------------------------------------------


@app.get("/api/vehicles/{vin}/history", response_model=VehicleHistoryResponse)
async def get_vehicle_history(
    vin: str,
    days: int = 30,
    from_date: str | None = None,
    to_date: str | None = None,
    max_points: int | None = None,
) -> VehicleHistoryResponse:
    """Get historical vehicle snapshots for a given time period."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="History not available")
    snapshots = await _history_repo.get_history(
        vin, days=days, from_date=from_date, to_date=to_date, max_points=max_points
    )
    return VehicleHistoryResponse(
        vin=vin,
        days=days,
        count=len(snapshots),
        snapshots=[
            VehicleSnapshotSchema(
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
                ignition_is_on1=s.ignition_is_on1,
                ignition_is_on2=s.ignition_is_on2,
                vehicle_is_charging=s.vehicle_is_charging,
                vehicle_is_plugged=s.vehicle_is_plugged,
                vehicle_is_regening=s.vehicle_is_regening,
                vehicle_is_parked=s.vehicle_is_parked,
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


@app.get("/api/vehicles/{vin}/events")
async def get_vehicle_events(vin: str, days: int = 30, event_type: str | None = None):
    """Get state-transition events for analytics and duration tracking."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="History not available")
    events = await _history_repo.get_events(vin, days=days, event_type=event_type)
    return {
        "vin": vin,
        "days": days,
        "count": len(events),
        "events": [
            {
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type,
                "field_name": e.field_name,
                "old_value": e.old_value,
                "new_value": e.new_value,
            }
            for e in events
        ],
    }


# ---------------------------------------------------------------------------
# Routes — User Preferences
# ---------------------------------------------------------------------------


@app.get("/api/preferences", response_model=PreferencesResponse)
async def get_preferences() -> PreferencesResponse:
    """Get user preferences (electricity price, etc.)."""
    prefs = await _load_preferences()
    return PreferencesResponse(
        electricity_price_kwh=prefs.electricity_price_kwh,
        theme=prefs.theme,
        downsampling_enabled=prefs.downsampling_enabled,
        downsampling_max_points=prefs.downsampling_max_points,
        has_solar_panels=prefs.has_solar_panels,
        home_pricing_mode=prefs.home_pricing_mode,
    )


@app.put("/api/preferences", response_model=PreferencesResponse)
async def update_preferences(request: Request) -> PreferencesResponse:
    """Update user preferences."""
    body = await request.json()
    price = body.get("electricity_price_kwh")
    if price is not None:
        try:
            price = float(price)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422, detail="'electricity_price_kwh' must be a number"
            ) from exc
        if price < 0:
            raise HTTPException(
                status_code=422, detail="'electricity_price_kwh' must be >= 0"
            )
        await _history_repo.save_setting("electricity_price_kwh", str(price))
    theme = body.get("theme")
    if theme is not None:
        if theme not in ("dark", "light"):
            raise HTTPException(
                status_code=422, detail="'theme' must be 'dark' or 'light'"
            )
        await _history_repo.save_setting("theme", theme)
    ds_enabled = body.get("downsampling_enabled")
    if ds_enabled is not None:
        if not isinstance(ds_enabled, bool):
            raise HTTPException(
                status_code=422, detail="'downsampling_enabled' must be a boolean"
            )
        await _history_repo.save_setting(
            "downsampling_enabled", str(ds_enabled).lower()
        )
    ds_max_points = body.get("downsampling_max_points")
    if ds_max_points is not None:
        try:
            ds_max_points = int(ds_max_points)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422, detail="'downsampling_max_points' must be an integer"
            ) from exc
        if ds_max_points < 100 or ds_max_points > 50000:
            raise HTTPException(
                status_code=422,
                detail="'downsampling_max_points' must be between 100 and 50000",
            )
        await _history_repo.save_setting("downsampling_max_points", str(ds_max_points))
    # -- solar panels toggle --
    has_solar = body.get("has_solar_panels")
    if has_solar is not None:
        if not isinstance(has_solar, bool):
            raise HTTPException(
                status_code=422, detail="'has_solar_panels' must be a boolean"
            )
        await _history_repo.save_setting(
            "has_solar_panels", "true" if has_solar else "false"
        )
        # Enable/disable home_solar tier
        from models import ChargingPriceTier

        tiers = await _history_repo.get_price_tiers()
        solar_tier = next((t for t in tiers if t.id == "home_solar"), None)
        if has_solar:
            if solar_tier:
                solar_tier.enabled = True
                await _history_repo.upsert_price_tier(solar_tier)
            else:
                await _history_repo.upsert_price_tier(
                    ChargingPriceTier(
                        id="home_solar",
                        label="Home (solar)",
                        price_kwh=0.0,
                        enabled=True,
                    )
                )
        elif solar_tier:
            solar_tier.enabled = False
            await _history_repo.upsert_price_tier(solar_tier)
    # -- home pricing mode --
    pricing_mode = body.get("home_pricing_mode")
    if pricing_mode is not None:
        if pricing_mode not in ("flat", "time_of_use"):
            raise HTTPException(
                status_code=422,
                detail="'home_pricing_mode' must be 'flat' or 'time_of_use'",
            )
        await _history_repo.save_setting("home_pricing_mode", pricing_mode)
    prefs = await _load_preferences()
    return PreferencesResponse(
        electricity_price_kwh=prefs.electricity_price_kwh,
        theme=prefs.theme,
        downsampling_enabled=prefs.downsampling_enabled,
        downsampling_max_points=prefs.downsampling_max_points,
        has_solar_panels=prefs.has_solar_panels,
        home_pricing_mode=prefs.home_pricing_mode,
    )


async def _load_preferences() -> UserPreferences:
    """Load user preferences from DB, falling back to defaults."""
    raw = await _history_repo.get_setting("electricity_price_kwh")
    theme_raw = await _history_repo.get_setting("theme")
    ds_enabled_raw = await _history_repo.get_setting("downsampling_enabled")
    ds_max_points_raw = await _history_repo.get_setting("downsampling_max_points")
    solar_raw = await _history_repo.get_setting("has_solar_panels")
    pricing_mode_raw = await _history_repo.get_setting("home_pricing_mode")
    return UserPreferences(
        electricity_price_kwh=float(raw) if raw else 0.25,
        theme=theme_raw if theme_raw in ("dark", "light") else "dark",
        downsampling_enabled=ds_enabled_raw != "false" if ds_enabled_raw else True,
        downsampling_max_points=int(ds_max_points_raw) if ds_max_points_raw else 2000,
        has_solar_panels=solar_raw == "true" if solar_raw else False,
        home_pricing_mode=pricing_mode_raw
        if pricing_mode_raw in ("flat", "time_of_use")
        else "flat",
    )


# ---------------------------------------------------------------------------
# Routes — Charging Price Tiers & Session Costs
# ---------------------------------------------------------------------------


@app.get("/api/charging-tiers", response_model=ChargingTiersFullResponse)
async def get_charging_tiers() -> ChargingTiersFullResponse:
    """Get all charging price tiers and time bands."""
    prefs = await _load_preferences()
    tiers = await _history_repo.get_price_tiers()
    # Hide home_solar if user has no solar panels
    if not prefs.has_solar_panels:
        tiers = [t for t in tiers if t.id != "home_solar"]
    bands = await _history_repo.get_time_bands("home_grid")
    return ChargingTiersFullResponse(
        tiers=[
            ChargingPriceTierResponse(
                id=t.id, label=t.label, price_kwh=t.price_kwh, enabled=t.enabled
            )
            for t in tiers
        ],
        time_bands=[
            ChargingTimeBandResponse(
                id=b.id,
                tier_id=b.tier_id,
                name=b.name,
                price_kwh=b.price_kwh,
                schedule=b.schedule,
                color=b.color,
                position=b.position,
            )
            for b in bands
        ],
        home_pricing_mode=prefs.home_pricing_mode,
    )


@app.put("/api/charging-tiers/{tier_id}", response_model=ChargingPriceTierResponse)
async def update_charging_tier(
    tier_id: str, body: ChargingPriceTierUpdate
) -> ChargingPriceTierResponse:
    """Update a charging price tier."""
    tiers = await _history_repo.get_price_tiers()
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
    await _history_repo.upsert_price_tier(tier)
    return ChargingPriceTierResponse(
        id=tier.id, label=tier.label, price_kwh=tier.price_kwh, enabled=tier.enabled
    )


@app.get(
    "/api/charging-tiers/time-bands", response_model=list[ChargingTimeBandResponse]
)
async def get_time_bands() -> list[ChargingTimeBandResponse]:
    """Get all time-of-use bands."""
    bands = await _history_repo.get_time_bands("home_grid")
    return [
        ChargingTimeBandResponse(
            id=b.id,
            tier_id=b.tier_id,
            name=b.name,
            price_kwh=b.price_kwh,
            schedule=b.schedule,
            color=b.color,
            position=b.position,
        )
        for b in bands
    ]


@app.post(
    "/api/charging-tiers/time-bands",
    response_model=ChargingTimeBandResponse,
    status_code=201,
)
async def create_time_band(body: ChargingTimeBandCreate) -> ChargingTimeBandResponse:
    """Create a new time-of-use band."""
    from models import ChargingTimeBand

    # Determine position (append at end)
    existing = await _history_repo.get_time_bands("home_grid")
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
    band = await _history_repo.upsert_time_band(band)
    return ChargingTimeBandResponse(
        id=band.id,
        tier_id=band.tier_id,
        name=band.name,
        price_kwh=band.price_kwh,
        schedule=band.schedule,
        color=band.color,
        position=band.position,
    )


@app.put(
    "/api/charging-tiers/time-bands/{band_id}", response_model=ChargingTimeBandResponse
)
async def update_time_band(
    band_id: int, body: ChargingTimeBandUpdate
) -> ChargingTimeBandResponse:
    """Update a time-of-use band."""
    bands = await _history_repo.get_time_bands("home_grid")
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
    await _history_repo.upsert_time_band(band)
    return ChargingTimeBandResponse(
        id=band.id,
        tier_id=band.tier_id,
        name=band.name,
        price_kwh=band.price_kwh,
        schedule=band.schedule,
        color=band.color,
        position=band.position,
    )


@app.delete("/api/charging-tiers/time-bands/{band_id}")
async def delete_time_band_endpoint(band_id: int):
    """Delete a time-of-use band."""
    deleted = await _history_repo.delete_time_band(band_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Time band {band_id} not found")
    return {"status": "ok"}


@app.get(
    "/api/vehicles/{vin}/charging-costs",
    response_model=list[ChargingSessionCostResponse],
)
async def get_charging_costs(
    vin: str, start: str | None = None, end: str | None = None
):
    """Get charging session costs for a vehicle."""
    from datetime import datetime as dt

    start_dt = dt.fromisoformat(start) if start else None
    end_dt = dt.fromisoformat(end) if end else None
    costs = await _history_repo.get_session_costs(vin, start=start_dt, end=end_dt)
    # Enrich with tier/band labels
    tiers = {t.id: t for t in await _history_repo.get_price_tiers()}
    bands = {b.id: b for b in await _history_repo.get_time_bands("home_grid")}
    return [
        ChargingSessionCostResponse(
            id=c.id,
            vin=c.vin,
            start_ts=c.start_ts.isoformat() if c.start_ts else "",
            end_ts=c.end_ts.isoformat() if c.end_ts else None,
            tier_id=c.tier_id,
            tier_label=tiers[c.tier_id].label if c.tier_id in tiers else None,
            time_band_id=c.time_band_id,
            time_band_name=bands[c.time_band_id].name
            if c.time_band_id and c.time_band_id in bands
            else None,
            energy_kwh=c.energy_kwh,
            peak_power_kw=c.peak_power_kw,
            cost=c.cost,
            note=c.note,
        )
        for c in costs
    ]


@app.post(
    "/api/vehicles/{vin}/charging-costs",
    response_model=ChargingSessionCostResponse,
    status_code=201,
)
async def create_charging_cost(vin: str, body: ChargingSessionCostCreate):
    """Assign a cost tier to a charging session."""
    from datetime import datetime as dt

    from models import ChargingSessionCost

    start_ts = dt.fromisoformat(body.start_ts)
    end_ts = dt.fromisoformat(body.end_ts) if body.end_ts else None
    # Validate tier exists
    tiers = {t.id: t for t in await _history_repo.get_price_tiers()}
    if body.tier_id not in tiers:
        raise HTTPException(status_code=422, detail=f"Unknown tier: {body.tier_id}")
    # Calculate cost
    cost = None
    if body.energy_kwh is not None:
        cost = await _calculate_session_cost(
            body.tier_id, body.energy_kwh, start_ts, end_ts
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
    sc = await _history_repo.upsert_session_cost(sc)
    tier = tiers.get(sc.tier_id)
    return ChargingSessionCostResponse(
        id=sc.id,
        vin=sc.vin,
        start_ts=sc.start_ts.isoformat() if sc.start_ts else "",
        end_ts=sc.end_ts.isoformat() if sc.end_ts else None,
        tier_id=sc.tier_id,
        tier_label=tier.label if tier else None,
        time_band_id=sc.time_band_id,
        energy_kwh=sc.energy_kwh,
        peak_power_kw=sc.peak_power_kw,
        cost=sc.cost,
        note=sc.note,
    )


@app.put(
    "/api/vehicles/{vin}/charging-costs/{cost_id}",
    response_model=ChargingSessionCostResponse,
)
async def update_charging_cost(vin: str, cost_id: int, body: ChargingSessionCostUpdate):
    """Update a charging session cost (change tier, energy, etc.)."""
    from datetime import datetime as dt

    costs = await _history_repo.get_session_costs(vin)
    sc = next((c for c in costs if c.id == cost_id), None)
    if not sc:
        raise HTTPException(status_code=404, detail=f"Session cost {cost_id} not found")
    if body.tier_id is not None:
        tiers = {t.id: t for t in await _history_repo.get_price_tiers()}
        if body.tier_id not in tiers:
            raise HTTPException(status_code=422, detail=f"Unknown tier: {body.tier_id}")
        sc.tier_id = body.tier_id
    if body.end_ts is not None:
        sc.end_ts = dt.fromisoformat(body.end_ts)
    if body.energy_kwh is not None:
        sc.energy_kwh = body.energy_kwh
    if body.peak_power_kw is not None:
        sc.peak_power_kw = body.peak_power_kw
    if body.note is not None:
        sc.note = body.note
    # Recalculate cost
    if sc.energy_kwh is not None:
        sc.cost = await _calculate_session_cost(
            sc.tier_id, sc.energy_kwh, sc.start_ts, sc.end_ts
        )
    await _history_repo.upsert_session_cost(sc)
    tiers = {t.id: t for t in await _history_repo.get_price_tiers()}
    bands = {b.id: b for b in await _history_repo.get_time_bands("home_grid")}
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
    )


@app.delete("/api/vehicles/{vin}/charging-costs/{cost_id}")
async def delete_charging_cost(vin: str, cost_id: int):
    """Delete a charging session cost."""
    deleted = await _history_repo.delete_session_cost(cost_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session cost {cost_id} not found")
    return {"status": "ok"}


async def _calculate_session_cost(
    tier_id: str, energy_kwh: float, start_ts, end_ts
) -> float:
    """Calculate cost for a session, using TOU bands if applicable."""
    prefs = await _load_preferences()
    tiers = {t.id: t for t in await _history_repo.get_price_tiers()}
    tier = tiers.get(tier_id)
    if not tier:
        return 0.0

    # If home_grid + time_of_use mode, split by time bands
    if (
        tier_id == "home_grid"
        and prefs.home_pricing_mode == "time_of_use"
        and start_ts
        and end_ts
    ):
        bands = await _history_repo.get_time_bands("home_grid")
        if bands:
            return _calculate_tou_cost(
                energy_kwh, start_ts, end_ts, bands, tier.price_kwh
            )

    # Flat rate
    return round(energy_kwh * tier.price_kwh, 4)


def _calculate_tou_cost(
    energy_kwh: float, start_ts, end_ts, bands, flat_price: float
) -> float:
    """Split energy proportionally across time bands based on session duration."""
    from datetime import timedelta as td

    total_seconds = (end_ts - start_ts).total_seconds()
    if total_seconds <= 0:
        return 0.0

    # Walk through the session in 15-min increments, determine band for each slot
    band_seconds: dict[int, float] = {}  # band_id -> seconds in that band
    fallback_seconds = 0.0
    slot = td(minutes=15)
    current = start_ts
    while current < end_ts:
        slot_end = min(current + slot, end_ts)
        slot_duration = (slot_end - current).total_seconds()
        matched_band = _match_time_band(current, bands)
        if matched_band:
            band_seconds[matched_band.id] = (
                band_seconds.get(matched_band.id, 0) + slot_duration
            )
        else:
            fallback_seconds += slot_duration
        current = slot_end

    # Calculate cost proportionally
    total_cost = 0.0
    for band_id, secs in band_seconds.items():
        band = next((b for b in bands if b.id == band_id), None)
        if band:
            proportion = secs / total_seconds
            total_cost += proportion * energy_kwh * band.price_kwh

    # Fallback: uncovered hours use the tier's flat price
    if fallback_seconds > 0:
        proportion = fallback_seconds / total_seconds
        total_cost += proportion * energy_kwh * flat_price

    return round(total_cost, 4)


def _match_time_band(timestamp, bands) -> object | None:
    """Find which time band a timestamp falls into."""
    weekday = timestamp.weekday()  # 0=Mon, 6=Sun
    hour = timestamp.hour
    minute = timestamp.minute
    time_minutes = hour * 60 + minute

    for band in bands:
        for slot in band.schedule:
            if weekday not in slot.get("days", []):
                continue
            start_min = slot.get("start_hour", 0) * 60 + slot.get("start_min", 0)
            end_min = slot.get("end_hour", 0) * 60 + slot.get("end_min", 0)
            # Handle overnight bands (e.g. 23:00 - 07:00)
            if end_min <= start_min:
                if time_minutes >= start_min or time_minutes < end_min:
                    return band
            else:
                if start_min <= time_minutes < end_min:
                    return band
    return None


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
    mqtt_interval = body.get("mqtt_interval_seconds")
    rate_limit = body.get("rate_limit_seconds")
    transition_enabled = body.get("transition_detection_enabled")
    transition_poll = body.get("transition_poll_interval_seconds")
    transition_min_event = body.get("transition_min_event_interval_seconds")

    if enabled is not None and not isinstance(enabled, bool):
        raise HTTPException(status_code=422, detail="'enabled' must be a boolean")
    if transition_enabled is not None and not isinstance(transition_enabled, bool):
        raise HTTPException(
            status_code=422, detail="'transition_detection_enabled' must be a boolean"
        )
    if interval is not None:
        try:
            interval = int(interval)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail="'interval_minutes' must be an integer",
            ) from exc
    if mqtt_interval is not None:
        try:
            mqtt_interval = int(mqtt_interval)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail="'mqtt_interval_seconds' must be an integer",
            ) from exc
    if rate_limit is not None:
        try:
            rate_limit = int(rate_limit)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail="'rate_limit_seconds' must be an integer",
            ) from exc

    settings = _scheduler.update_settings(
        enabled=enabled,
        interval_minutes=interval,
        mqtt_interval_seconds=mqtt_interval,
        rate_limit_seconds=rate_limit,
        transition_detection_enabled=transition_enabled,
        transition_poll_interval_seconds=transition_poll,
        transition_min_event_interval_seconds=transition_min_event,
    )

    # Persist to DB
    await _history_repo.save_scheduler_settings(settings)

    return _scheduler.status_dict()


# ---------------------------------------------------------------------------
# Routes — System
# ---------------------------------------------------------------------------


@app.get("/api/system/database-size", response_model=DatabaseSizeResponse)
async def get_database_size() -> DatabaseSizeResponse:
    """Return the current size of the SQLite database file."""
    db_path = os.environ.get(
        "HISTORY_DB_PATH", str(Path(__file__).parent / "leapconnect.db")
    )
    try:
        size_bytes = os.path.getsize(db_path)
    except OSError as exc:
        raise HTTPException(status_code=404, detail="Database file not found") from exc

    # Human-readable size
    if size_bytes < 1024:
        size_human = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_human = f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        size_human = f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        size_human = f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    return DatabaseSizeResponse(size_bytes=size_bytes, size_human=size_human)


# ---------------------------------------------------------------------------
# Routes — Live Refresh
# ---------------------------------------------------------------------------


@app.get("/api/live-refresh", response_model=LiveRefreshStatusResponse)
async def get_live_refresh() -> LiveRefreshStatusResponse:
    """Get live refresh status and current interval."""
    is_running = _live_refresh_task is not None and not _live_refresh_task.done()
    return LiveRefreshStatusResponse(
        interval_seconds=_live_refresh_interval,
        is_running=is_running,
    )


@app.put("/api/live-refresh", response_model=LiveRefreshStatusResponse)
async def update_live_refresh(request: Request) -> LiveRefreshStatusResponse:
    """Enable/disable live refresh or change its interval.

    Set interval_seconds to 0 to disable. Valid range: 10–600 seconds.
    """
    global _live_refresh_interval
    body = await request.json()
    interval = body.get("interval_seconds")
    if interval is None:
        raise HTTPException(status_code=422, detail="'interval_seconds' is required")
    try:
        interval = int(interval)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="'interval_seconds' must be an integer"
        ) from exc
    if interval < 0:
        raise HTTPException(status_code=422, detail="'interval_seconds' must be >= 0")
    # Cap at reasonable max (10 min) and min (10 sec when enabled)
    if interval > 0:
        interval = max(10, min(600, interval))

    _live_refresh_interval = interval
    # Persist
    if _history_repo:
        await _history_repo.save_setting("live_refresh_interval", str(interval))

    # (Re)start or stop the loop
    if interval > 0 and _connected:
        _start_live_refresh()
    else:
        _stop_live_refresh()

    is_running = _live_refresh_task is not None and not _live_refresh_task.done()
    return LiveRefreshStatusResponse(
        interval_seconds=_live_refresh_interval,
        is_running=is_running,
    )


# ---------------------------------------------------------------------------
# Routes — MQTT / Home Assistant
# ---------------------------------------------------------------------------


async def _load_mqtt_settings() -> MqttSettings:
    """Load MQTT settings from the database."""
    if not _history_repo:
        return MqttSettings()
    settings = MqttSettings()
    enabled = await _history_repo.get_setting("mqtt_enabled")
    settings.enabled = enabled == "1" if enabled else False
    settings.broker = await _history_repo.get_setting("mqtt_broker") or ""
    port_str = await _history_repo.get_setting("mqtt_port")
    settings.port = int(port_str) if port_str else 1883
    settings.username = await _history_repo.get_setting("mqtt_username") or ""
    settings.password = await _history_repo.get_setting("mqtt_password") or ""
    use_tls = await _history_repo.get_setting("mqtt_use_tls")
    settings.use_tls = use_tls == "1" if use_tls else False
    settings.discovery_prefix = (
        await _history_repo.get_setting("mqtt_discovery_prefix") or "homeassistant"
    )
    settings.topic_prefix = (
        await _history_repo.get_setting("mqtt_topic_prefix") or "leapconnect"
    )
    return settings


async def _save_mqtt_settings(settings: MqttSettings) -> None:
    """Persist MQTT settings to the database."""
    if not _history_repo:
        return
    await _history_repo.save_setting("mqtt_enabled", "1" if settings.enabled else "0")
    await _history_repo.save_setting("mqtt_broker", settings.broker)
    await _history_repo.save_setting("mqtt_port", str(settings.port))
    await _history_repo.save_setting("mqtt_username", settings.username)
    await _history_repo.save_setting("mqtt_password", settings.password)
    await _history_repo.save_setting("mqtt_use_tls", "1" if settings.use_tls else "0")
    await _history_repo.save_setting("mqtt_discovery_prefix", settings.discovery_prefix)
    await _history_repo.save_setting("mqtt_topic_prefix", settings.topic_prefix)


async def _save_mqtt_vehicle_pin(pin: str) -> None:
    """Persist the vehicle operation PIN for MQTT commands."""
    if not _history_repo:
        return
    await _history_repo.save_setting("mqtt_vehicle_pin", pin)


def _set_vehicle_pin(pin: str) -> None:
    """Temporarily set/restore the vehicle operation PIN on the sync client.

    When called with a non-empty pin, saves the current PIN and sets the new one.
    When called with empty string, restores the previously saved PIN.
    This ensures Telegram commands don't interfere with the persisted PIN.
    """
    if not _sync_client:
        return
    if pin.strip():
        # Save current PIN and set the temporary one
        _set_vehicle_pin._saved = _sync_client.operation_password
        _sync_client.operation_password = pin.strip()
    else:
        # Restore original PIN
        _sync_client.operation_password = getattr(_set_vehicle_pin, "_saved", None)


_set_vehicle_pin._saved = None


async def _handle_mqtt_command(vin: str, command: str) -> None:
    """Handle a command received from Home Assistant via MQTT."""
    if not _client:
        _LOGGER.warning("MQTT command %s for %s ignored: no client", command, vin)
        return

    result = None
    try:
        if command == "lock":
            result = await _client.lock_vehicle(vin)
        elif command == "unlock":
            result = await _client.unlock_vehicle(vin)
        elif command == "trunk_open":
            result = await _client.open_trunk(vin)
        elif command == "trunk_close":
            result = await _client.close_trunk(vin)
        elif command == "find":
            result = await _client.find_vehicle(vin)
        elif command == "windows_open":
            result = await _client.open_windows(vin)
        elif command == "windows_close":
            result = await _client.close_windows(vin)
        elif command == "charging_start":
            result = await _client.start_charging(vin)
        elif command == "charging_stop":
            result = await _client.stop_charging(vin)
        elif command == "battery_preheat":
            result = await _client.battery_preheat(vin)
        elif command == "battery_preheat_off":
            result = await _client.battery_preheat_off(vin)
        elif command == "unlock_charger":
            result = await _client.unlock_charger(vin)
        elif command == "sunroof_open":
            result = await _client.open_sunroof(vin)
        elif command == "sunroof_close":
            result = await _client.close_sunroof(vin)
        elif command == "on3_on":
            result = await _client.on3_on(vin)
        elif command == "on3_off":
            result = await _client.on3_off(vin)
        elif command == "ble_key_restart":
            result = await _client.ble_key_restart(vin)
        elif command == "hotspot":
            result = await _client.hotspot(vin)
        elif command == "autopark":
            result = await _client.autopark(vin)
        elif command == "defrost":
            result = await _client.windshield_defrost(vin)
        # Switch on/off commands
        elif command == "ac_on":
            result = await _client.ac_on(vin)
        elif command == "ac_off":
            result = await _client.ac_off(vin)
        elif command == "sentry_mode_on":
            result = await _client.sentry_mode_on(vin)
        elif command == "sentry_mode_off":
            result = await _client.sentry_mode_off(vin)
        elif command == "steering_wheel_heat_on":
            result = await _client.steering_wheel_heat_on(vin)
        elif command == "steering_wheel_heat_off":
            result = await _client.steering_wheel_heat_off(vin)
        elif command == "fuel_heating_on":
            result = await _client.fuel_heating_on(vin)
        elif command == "fuel_heating_off":
            result = await _client.fuel_heating_off(vin)
        elif command == "rearview_mirror_heat_on":
            result = await _client.rearview_mirror_heat_on(vin)
        elif command == "rearview_mirror_heat_off":
            result = await _client.rearview_mirror_heat_off(vin)
        elif command == "healthy_charging_on":
            result = await _client.healthy_charging_on(vin)
        elif command == "healthy_charging_off":
            result = await _client.healthy_charging_off(vin)
        else:
            _LOGGER.warning("MQTT: unknown command '%s' for %s", command, vin)
            return
    except Exception as exc:
        _LOGGER.exception("MQTT command %s failed for %s", command, vin)
        result = {"error": str(exc)}

    if _mqtt_service and result:
        await _mqtt_service.publish_command_result(vin, command, result)


async def _mqtt_publish_status(vin: str, status) -> None:
    """Publish vehicle status to MQTT if enabled."""
    if not _mqtt_service or not _mqtt_service.is_connected:
        return
    vehicle = _find_vehicle(vin)
    image_pkg = _image_packages.get(vin)
    await _mqtt_service.publish_vehicle_status(vehicle, status, image_pkg)
    # Also publish current scheduler intervals
    if _scheduler:
        s = _scheduler.settings
        await _mqtt_service.publish_scheduler_settings(
            vin, s.interval_minutes, s.mqtt_interval_seconds
        )


async def _handle_mqtt_settings(key: str, value: int) -> None:
    """Handle a polling interval change received from Home Assistant via MQTT."""
    if not _scheduler or not _history_repo:
        _LOGGER.warning("MQTT settings change ignored: scheduler not available")
        return

    if key == "polling_interval":
        settings = _scheduler.update_settings(mqtt_interval_seconds=value)
        await _history_repo.save_scheduler_settings(settings)
        _LOGGER.info("MQTT settings applied: %s = %d", key, value)
        if _mqtt_service and _mqtt_service.is_connected:
            for v in _vehicles:
                await _mqtt_service.publish_scheduler_settings(
                    v.vin, settings.interval_minutes, settings.mqtt_interval_seconds
                )
    elif key == "charge_limit":
        if not _client:
            _LOGGER.warning("MQTT charge_limit change ignored: no API client")
            return
        for v in _vehicles:
            try:
                await _client.set_charge_limit(v.vin, value)
                _LOGGER.info("Charge limit set to %d%% for %s", value, v.vin)
            except Exception as exc:
                _LOGGER.exception("Failed to set charge limit for %s: %s", v.vin, exc)
    elif key == "ac_temperature":
        if not _client:
            _LOGGER.warning("MQTT ac_temperature change ignored: no API client")
            return
        for v in _vehicles:
            try:
                await _client.ac_on(v.vin, params={"temperature": str(value)})
                _LOGGER.info("AC temperature set to %d°C for %s", value, v.vin)
            except Exception as exc:
                _LOGGER.exception("Failed to set AC temp for %s: %s", v.vin, exc)
    else:
        _LOGGER.warning("MQTT: unknown setting key '%s'", key)


def _mqtt_status_response() -> MqttStatusResponse:
    """Build a MqttStatusResponse from the service's settings + runtime state."""
    s = _mqtt_service.settings
    return MqttStatusResponse(
        enabled=s.enabled,
        connected=_mqtt_service.is_connected,
        broker=s.broker,
        port=s.port,
        username=s.username,
        use_tls=s.use_tls,
        discovery_prefix=s.discovery_prefix,
        topic_prefix=s.topic_prefix,
        last_error=_mqtt_service.last_error,
    )


@app.get("/api/mqtt", response_model=MqttStatusResponse)
async def get_mqtt_status() -> MqttStatusResponse:
    """Get current MQTT / Home Assistant integration status."""
    if not _mqtt_service:
        return MqttStatusResponse()
    return _mqtt_status_response()


@app.put("/api/mqtt", response_model=MqttStatusResponse)
async def update_mqtt_settings(request: Request) -> MqttStatusResponse:
    """Update MQTT connection settings and reconnect."""
    if not _mqtt_service or not _history_repo:
        raise HTTPException(status_code=503, detail="MQTT service not available")

    body = await request.json()

    # Validate
    if "port" in body:
        try:
            body["port"] = int(body["port"])
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422, detail="'port' must be an integer"
            ) from exc

    _mqtt_service.update_settings(
        enabled=body.get("enabled"),
        broker=body.get("broker"),
        port=body.get("port"),
        username=body.get("username"),
        password=body.get("password"),
        use_tls=body.get("use_tls"),
        discovery_prefix=body.get("discovery_prefix"),
        topic_prefix=body.get("topic_prefix"),
    )

    # Persist MQTT settings
    await _save_mqtt_settings(_mqtt_service.settings)

    return _mqtt_status_response()


@app.post("/api/mqtt/test", response_model=MqttTestResponse)
async def test_mqtt_connection(request: Request) -> MqttTestResponse:
    """Test MQTT connection with provided settings (without saving)."""
    import aiomqtt

    body = await request.json()
    broker = body.get("broker", "").strip()
    port = int(body.get("port", 1883))
    username = body.get("username", "").strip() or None
    password = body.get("password", "").strip() or None
    use_tls = body.get("use_tls", False)

    if not broker:
        raise HTTPException(status_code=422, detail="'broker' is required")

    try:
        tls_params = aiomqtt.TLSParameters() if use_tls else None
        async with aiomqtt.Client(
            hostname=broker,
            port=port,
            username=username,
            password=password,
            tls_params=tls_params,
            timeout=10,
        ):
            return MqttTestResponse(status="ok", message="Connection successful")
    except Exception as exc:
        return MqttTestResponse(status="error", message=str(exc))


# ---------------------------------------------------------------------------
# Routes — ABRP (A Better Route Planner)
# ---------------------------------------------------------------------------


async def _load_abrp_settings():
    """Load ABRP settings from the database."""
    from models import AbrpSettings

    if not _history_repo:
        return AbrpSettings()
    settings = AbrpSettings()
    enabled = await _history_repo.get_setting("abrp_enabled")
    settings.enabled = enabled == "1" if enabled else False
    settings.user_token = await _history_repo.get_setting("abrp_user_token") or ""
    return settings


async def _save_abrp_settings(settings) -> None:
    """Persist ABRP settings to the database."""
    if not _history_repo:
        return
    await _history_repo.save_setting("abrp_enabled", "1" if settings.enabled else "0")
    await _history_repo.save_setting("abrp_user_token", settings.user_token)


@app.get("/api/abrp", response_model=AbrpStatusResponse)
async def get_abrp_status() -> AbrpStatusResponse:
    """Get current ABRP integration status."""
    if not _abrp_service:
        return AbrpStatusResponse()
    d = _abrp_service.status_dict()
    return AbrpStatusResponse(**d)


@app.put("/api/abrp", response_model=AbrpStatusResponse)
async def update_abrp_settings(request: Request) -> AbrpStatusResponse:
    """Update ABRP settings."""
    if not _abrp_service or not _history_repo:
        raise HTTPException(status_code=503, detail="ABRP service not available")

    body = await request.json()

    _abrp_service.update_settings(
        enabled=body.get("enabled"),
        user_token=body.get("user_token"),
    )

    # Ensure vehicles are wired
    if _abrp_service.settings.enabled and _vehicles:
        _abrp_service.set_vehicles(_vehicles, _vehicle_cache)

    await _save_abrp_settings(_abrp_service.settings)

    d = _abrp_service.status_dict()
    return AbrpStatusResponse(**d)


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
    mode: str | None = None  # "cold", "hot", "wind"
    operate: str | None = None  # "manual", "auto", or "close"
    position: str | None = None  # "all"
    temperature: str | None = None  # e.g. "26"
    windlevel: int | None = None  # 1–7
    wshld: str | None = None  # "0" (off) or "1" (defrost on)


@app.post("/api/vehicles/{vin}/ac")
async def ac_switch(vin: str, body: ClimateRequest | None = None) -> dict:
    """Turn on the air conditioning with optional parameters."""
    client = _get_client()
    params = {
        k: v for k, v in (body.model_dump() if body else {}).items() if v is not None
    } or None
    return await client.ac_on(vin, params=params)


@app.post("/api/vehicles/{vin}/ac-off")
async def ac_off(vin: str) -> dict:
    """Turn off the air conditioning."""
    client = _get_client()
    return await client.ac_off(vin)


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
    try:
        return await client.set_charge_limit(vin, int(limit))
    except LeapmotorApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


class ChargeScheduleRequest(BaseModel):
    enabled: bool
    soc_limit: int = 80
    start_time: str
    end_time: str
    cycles: str
    circulation: int = 0
    recharge: int = 0


@app.get("/api/vehicles/{vin}/charge-schedule")
async def get_charge_schedule(vin: str) -> dict:
    """Retrieve the current charge schedule from the cloud."""
    client = _get_client()
    try:
        return await client.get_charge_schedule(vin)
    except LeapmotorApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/vehicles/{vin}/charge-schedule")
async def set_charge_schedule(vin: str, body: ChargeScheduleRequest) -> dict:
    """Set the full charging schedule (start/end time, days, SOC limit)."""
    client = _get_client()
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


@app.get("/api/vehicles/{vin}/ac-schedule")
async def get_climate_schedule(vin: str) -> list[dict]:
    """Retrieve active climate schedules from the cloud."""
    client = _get_client()
    try:
        return await client.get_climate_schedule(vin)
    except LeapmotorApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/vehicles/{vin}/ac-schedule")
async def set_climate_schedule(vin: str, body: ClimateScheduleRequest) -> dict:
    """Set climate schedules via cloud (cmd_id=171, full-state replacement)."""
    client = _get_client()
    controls = [entry.model_dump() for entry in body.controls]
    try:
        return await client.set_climate_schedule(vin, controls=controls)
    except LeapmotorApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.delete("/api/vehicles/{vin}/ac-schedule")
async def cancel_climate_schedule(vin: str) -> dict:
    """Cancel all climate schedules (sends empty controls array)."""
    client = _get_client()
    try:
        return await client.cancel_climate_schedule(vin)
    except LeapmotorApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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
# Routes — New Vehicle Commands
# ---------------------------------------------------------------------------


@app.post("/api/vehicles/{vin}/battery-preheat-off")
async def battery_preheat_off(vin: str) -> dict:
    """Stop battery preheating remotely."""
    client = _get_client()
    return await client.battery_preheat_off(vin)


@app.post("/api/vehicles/{vin}/sentry-mode/on")
async def sentry_mode_on(vin: str) -> dict:
    """Activate sentry mode (dashcam/sentinel)."""
    client = _get_client()
    return await client.sentry_mode_on(vin)


@app.post("/api/vehicles/{vin}/sentry-mode/off")
async def sentry_mode_off(vin: str) -> dict:
    """Deactivate sentry mode."""
    client = _get_client()
    return await client.sentry_mode_off(vin)


@app.post("/api/vehicles/{vin}/charging/start")
async def start_charging(vin: str) -> dict:
    """Start charging the vehicle."""
    client = _get_client()
    return await client.start_charging(vin)


@app.post("/api/vehicles/{vin}/charging/stop")
async def stop_charging(vin: str) -> dict:
    """Stop charging the vehicle."""
    client = _get_client()
    return await client.stop_charging(vin)


@app.post("/api/vehicles/{vin}/steering-wheel-heat/on")
async def steering_wheel_heat_on(vin: str) -> dict:
    """Turn on steering wheel heating."""
    client = _get_client()
    return await client.steering_wheel_heat_on(vin)


@app.post("/api/vehicles/{vin}/steering-wheel-heat/off")
async def steering_wheel_heat_off(vin: str) -> dict:
    """Turn off steering wheel heating."""
    client = _get_client()
    return await client.steering_wheel_heat_off(vin)


@app.post("/api/vehicles/{vin}/fuel-heating/on")
async def fuel_heating_on(vin: str) -> dict:
    """Turn on fuel heating."""
    client = _get_client()
    return await client.fuel_heating_on(vin)


@app.post("/api/vehicles/{vin}/fuel-heating/off")
async def fuel_heating_off(vin: str) -> dict:
    """Turn off fuel heating."""
    client = _get_client()
    return await client.fuel_heating_off(vin)


@app.post("/api/vehicles/{vin}/rearview-mirror-heat/on")
async def rearview_mirror_heat_on(vin: str) -> dict:
    """Turn on rearview mirror heating."""
    client = _get_client()
    return await client.rearview_mirror_heat_on(vin)


@app.post("/api/vehicles/{vin}/rearview-mirror-heat/off")
async def rearview_mirror_heat_off(vin: str) -> dict:
    """Turn off rearview mirror heating."""
    client = _get_client()
    return await client.rearview_mirror_heat_off(vin)


@app.post("/api/vehicles/{vin}/healthy-charging/on")
async def healthy_charging_on(vin: str) -> dict:
    """Enable healthy charging."""
    client = _get_client()
    return await client.healthy_charging_on(vin)


@app.post("/api/vehicles/{vin}/healthy-charging/off")
async def healthy_charging_off(vin: str) -> dict:
    """Disable healthy charging."""
    client = _get_client()
    return await client.healthy_charging_off(vin)


@app.post("/api/vehicles/{vin}/on3/on")
async def on3_on(vin: str) -> dict:
    """Activate ON3 (ignition)."""
    client = _get_client()
    return await client.on3_on(vin)


@app.post("/api/vehicles/{vin}/on3/off")
async def on3_off(vin: str) -> dict:
    """Deactivate ON3 (ignition)."""
    client = _get_client()
    return await client.on3_off(vin)


@app.post("/api/vehicles/{vin}/ble-key-restart")
async def ble_key_restart(vin: str) -> dict:
    """Restart BLE key module."""
    client = _get_client()
    return await client.ble_key_restart(vin)


@app.post("/api/vehicles/{vin}/sunroof/open")
async def open_sunroof(vin: str) -> dict:
    """Open the sunroof."""
    client = _get_client()
    return await client.open_sunroof(vin)


@app.post("/api/vehicles/{vin}/sunroof/close")
async def close_sunroof(vin: str) -> dict:
    """Close the sunroof."""
    client = _get_client()
    return await client.close_sunroof(vin)


@app.post("/api/vehicles/{vin}/unlock-charger")
async def unlock_charger(vin: str) -> dict:
    """Unlock the charging connector."""
    client = _get_client()
    return await client.unlock_charger(vin)


@app.post("/api/vehicles/{vin}/hotspot")
async def toggle_hotspot(vin: str) -> dict:
    """Toggle vehicle WiFi hotspot."""
    client = _get_client()
    return await client.hotspot(vin)


@app.post("/api/vehicles/{vin}/autopark")
async def autopark(vin: str) -> dict:
    """Trigger autopark."""
    client = _get_client()
    return await client.autopark(vin)


# -- Parameterized commands --


class SeatHeatRequest(BaseModel):
    position: int  # 1–6
    level: int  # 0–3


@app.post("/api/vehicles/{vin}/seat-heat")
async def seat_heat(vin: str, body: SeatHeatRequest) -> dict:
    """Control seat heating (position 1-6, level 0-3)."""
    client = _get_client()
    return await client.seat_heat(vin, position=body.position, level=body.level)


class SeatVentilationRequest(BaseModel):
    position: int  # 1–6
    level: int  # 0–3


@app.post("/api/vehicles/{vin}/seat-ventilation")
async def seat_ventilation(vin: str, body: SeatVentilationRequest) -> dict:
    """Control seat ventilation (position 1-6, level 0-3)."""
    client = _get_client()
    return await client.seat_ventilation(vin, position=body.position, level=body.level)


class SpeedLimitRequest(BaseModel):
    value: str  # km/h as string


@app.post("/api/vehicles/{vin}/speed-limit")
async def set_speed_limit(vin: str, body: SpeedLimitRequest) -> dict:
    """Set the vehicle speed limit."""
    client = _get_client()
    return await client.set_speed_limit(vin, value=body.value)


class MediaRequest(BaseModel):
    operation: str  # "play", "pause", "next", "previous"


@app.post("/api/vehicles/{vin}/music")
async def music(vin: str, body: MediaRequest) -> dict:
    """Control music playback."""
    client = _get_client()
    return await client.music(vin, operation=body.operation)


@app.post("/api/vehicles/{vin}/video")
async def video(vin: str, body: MediaRequest) -> dict:
    """Control video playback."""
    client = _get_client()
    return await client.video(vin, operation=body.operation)


@app.get("/api/vehicles/{vin}/ptc-heating-schedule")
async def get_ptc_heating_schedule(vin: str) -> list[dict]:
    """Retrieve PTC battery heating schedules from the cloud."""
    client = _get_client()
    try:
        return await client.get_ptc_heating_schedule(vin)
    except LeapmotorApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/vehicles/{vin}/prepare-car-schedule")
async def get_prepare_car_schedule(vin: str) -> list[dict]:
    """Retrieve prepare-car pre-conditioning schedules from the cloud."""
    client = _get_client()
    try:
        return await client.get_prepare_car_schedule(vin)
    except LeapmotorApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


class FotaRequest(BaseModel):
    task_id: int


@app.post("/api/vehicles/{vin}/fota/download")
async def fota_download(vin: str, body: FotaRequest) -> dict:
    """Start FOTA firmware download."""
    client = _get_client()
    return await client.fota_download(vin, task_id=body.task_id)


@app.post("/api/vehicles/{vin}/fota/install")
async def fota_install(vin: str, body: FotaRequest) -> dict:
    """Start FOTA firmware installation."""
    client = _get_client()
    return await client.fota_install(vin, task_id=body.task_id)


class FotaScheduleRequest(BaseModel):
    task_id: int
    schedule_time: str


@app.get("/api/vehicles/{vin}/fota/schedule")
async def get_fota_schedule(vin: str) -> list[dict]:
    """Retrieve active FOTA install schedules from the cloud."""
    client = _get_client()
    try:
        return await client.get_fota_schedule(vin)
    except LeapmotorApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/vehicles/{vin}/fota/schedule")
async def fota_schedule(vin: str, body: FotaScheduleRequest) -> dict:
    """Schedule a FOTA firmware installation."""
    client = _get_client()
    return await client.fota_schedule(
        vin, task_id=body.task_id, schedule_time=body.schedule_time
    )


class RearSeatsRequest(BaseModel):
    seat_info: str


@app.post("/api/vehicles/{vin}/rear-seats")
async def rear_seats(vin: str, body: RearSeatsRequest) -> dict:
    """Control rear seats (C16 only)."""
    client = _get_client()
    return await client.rear_seats(vin, seat_info=body.seat_info)


@app.post("/api/vehicles/{vin}/prepare-car")
async def prepare_car(vin: str, request: Request) -> dict:
    """Prepare car command (C10/B10)."""
    client = _get_client()
    body = await request.json()
    return await client.prepare_car(vin, params=body)


@app.post("/api/vehicles/{vin}/seat-adjust")
async def seat_adjust(vin: str, request: Request) -> dict:
    """Adjust seat position (C10/C16)."""
    client = _get_client()
    body = await request.json()
    return await client.seat_adjust(vin, params=body)


@app.post("/api/vehicles/{vin}/piloted-parking")
async def piloted_parking(vin: str, request: Request) -> dict:
    """Trigger piloted parking (C10/C16)."""
    client = _get_client()
    body = await request.json()
    return await client.piloted_parking(vin, params=body)


# ---------------------------------------------------------------------------
# Routes — New Data Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/vehicles/{vin}/charging-history", response_model=ChargingHistoryResponse)
async def get_charging_history(
    vin: str,
    start: str | None = None,
    end: str | None = None,
    timezone: str = "GMT+00:00",
    page: int = 1,
    size: int = 10,
) -> ChargingHistoryResponse:
    """Get paginated charging session history."""
    from datetime import date as date_cls

    client = _get_client()
    today = date_cls.today()
    start_date = date_cls.fromisoformat(start) if start else today.replace(day=1)
    end_date = date_cls.fromisoformat(end) if end else today
    result = await client.get_charging_daily_detail(
        vin,
        start_time=start_date,
        end_time=end_date,
        timezone=timezone,
        page_num=page,
        page_size=size,
    )
    return ChargingHistoryResponse.from_result(result.records, page, size)


@app.get(
    "/api/vehicles/{vin}/consumption/weekly-rank",
    response_model=ConsumptionWeeklyRankResponse,
)
async def get_consumption_weekly_rank(
    vin: str,
) -> ConsumptionWeeklyRankResponse:
    """Get weekly energy consumption ranking."""
    client = _get_client()
    vehicle = _find_vehicle(vin)
    result = await client.get_consumption_weekly_rank(vehicle)
    return ConsumptionWeeklyRankResponse.from_model(result)


@app.get(
    "/api/vehicles/{vin}/consumption/last-week",
    response_model=ConsumptionLastWeekResponse,
)
async def get_consumption_last_week(vin: str) -> ConsumptionLastWeekResponse:
    """Get last week energy consumption breakdown."""
    client = _get_client()
    vehicle = _find_vehicle(vin)
    result = await client.get_consumption_last_week_breakdown(vehicle)
    return ConsumptionLastWeekResponse.from_model(result)


# ---------------------------------------------------------------------------
# Routes — Trips & Driving Records
# ---------------------------------------------------------------------------


def _parse_range_date(value: str | None) -> str | None:
    """Normalize supported date inputs to YYYY-MM-DD.

    Accepted formats:
    - YYYY-MM-DD
    - ISO datetime
    - Unix timestamp seconds or milliseconds (string)
    """
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None

    if raw.isdigit():
        ts = int(raw)
        if ts > 10_000_000_000:
            ts = ts / 1000
        return datetime.utcfromtimestamp(ts).date().isoformat()

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        # Last fallback for strings like "YYYY-MM-DD HH:MM:SS"
        try:
            return datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S").date().isoformat()
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid date format: {value}",
            ) from exc


def _is_snapshot_moving(snapshot: VehicleSnapshot) -> bool:
    speed = snapshot.drive_speed or 0
    return speed > 0 or snapshot.drive_is_parked is False


# ---- Merge helpers ---------------------------------------------------------

# Maximum gap (seconds) between two moving segments to still consider them
# the same trip (e.g. traffic light, stop sign).  If the pause is longer
# than this, the segments become separate trips.
_MERGE_GAP_S = 300  # 5 minutes


def _segment_end(seg: list[VehicleSnapshot]) -> VehicleSnapshot:
    return seg[-1]


def _segment_start(seg: list[VehicleSnapshot]) -> VehicleSnapshot:
    return seg[0]


def _build_trip_row(segment: list[VehicleSnapshot]) -> dict | None:
    """Turn a *merged* segment into a trip row for the response payload."""
    if len(segment) < 2:
        return None

    start = _segment_start(segment)
    end = _segment_end(segment)
    duration_h = max(0.0, (end.timestamp - start.timestamp).total_seconds() / 3600.0)
    if duration_h <= 0:
        return None

    start_km = start.drive_total_mileage
    end_km = end.drive_total_mileage
    travel_km = 0.0
    if start_km is not None and end_km is not None:
        travel_km = max(0.0, float(end_km) - float(start_km))

    if travel_km < 0.2:
        return None

    start_wh = start.battery_dump_energy
    end_wh = end.battery_dump_energy
    energy_wh = 0.0
    if start_wh is not None and end_wh is not None:
        energy_wh = abs(float(end_wh) - float(start_wh))

    return {
        "beginTime": start.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "endTime": end.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "travelMile": int(round(travel_km * 1000)),
        "eneryConsume": int(round(energy_wh)),
        "recoveryEnery": int(round(_segment_regen_energy_wh(segment))),
        "maxSpeed": max((s.drive_speed or 0) for s in segment),
        "avgSpeed": round(travel_km / duration_h, 1) if duration_h > 0 else 0,
        "startSoc": start.battery_soc,
        "endSoc": end.battery_soc,
        "outdoorTemp": start.climate_outdoor_temp,
        "startLat": start.vehicle_latitude,
        "startLng": start.vehicle_longitude,
        "endLat": end.vehicle_latitude,
        "endLng": end.vehicle_longitude,
        "gpskey": (
            f"{int(start.timestamp.timestamp())}_{int(end.timestamp.timestamp())}"
        ),
        "_travel_km": travel_km,
        "_energy_kwh": energy_wh / 1000.0,
        "_duration_h": duration_h,
    }


def _any_parked_in_gap(
    snapshots: list[VehicleSnapshot],
    seg_a: list[VehicleSnapshot],
    seg_b: list[VehicleSnapshot],
) -> bool:
    """Check whether the vehicle was explicitly *parked* in the gap
    between two segments."""
    # Look at snapshot rows whose timestamps fall between seg_a end and seg_b start.
    gap_start = _segment_end(seg_a).timestamp
    gap_end = _segment_start(seg_b).timestamp
    for s in snapshots:
        if gap_start < s.timestamp < gap_end and s.drive_is_parked is True:
            return True
    return False


def _merge_segments(
    raw_segments: list[list[VehicleSnapshot]],
    snapshots: list[VehicleSnapshot],
) -> list[list[VehicleSnapshot]]:
    """Merge adjacent segments whose gap is small and there was no explicit park.

    Two raw segments are merged when:
    1. The time gap between them is <= ``_MERGE_GAP_S``.
    2. No snapshot in the gap has ``drive_is_parked == True``.
    """
    if not raw_segments:
        return []

    merged: list[list[VehicleSnapshot]] = [raw_segments[0].copy()]

    for seg in raw_segments[1:]:
        last = merged[-1]
        gap_s = (
            _segment_start(seg).timestamp - _segment_end(last).timestamp
        ).total_seconds()
        parked_in_gap = _any_parked_in_gap(snapshots, last, seg)

        if gap_s <= _MERGE_GAP_S and not parked_in_gap:
            # Extend the last merged segment instead of creating a new one.
            # Drop the first snapshot of 'seg' to avoid duplicating the boundary.
            if len(seg) > 1:
                merged[-1].extend(seg[1:])
            else:
                merged[-1].extend(seg)
        else:
            merged.append(seg.copy())

    return merged


def _build_local_trip_payload(snapshots: list[VehicleSnapshot]) -> dict:
    """Build a cloud-like trip payload from local history snapshots.

    1. Extract raw “moving” segments (contiguous speed>0 windows).
    2. Merge segments whose inter-segment gap is <= 5 min and not parked.
    3. Drop segments below minimum distance (0.2 km).
    """
    if len(snapshots) < 2:
        return {
            "source": "local_history",
            "total_enery": 0,
            "total_milage": 0,
            "total_ustime": 0,
            "data": [],
        }

    # --- Step 1: collect raw moving segments ---
    raw_segments: list[list[VehicleSnapshot]] = []
    cur: list[VehicleSnapshot] = []

    for idx, snap in enumerate(snapshots):
        moving = _is_snapshot_moving(snap)
        if moving:
            if not cur:
                prev = snapshots[idx - 1] if idx > 0 else snap
                cur = [prev]
            cur.append(snap)
        elif cur:
            cur.append(snap)
            raw_segments.append(cur)
            cur = []

    if cur:
        raw_segments.append(cur)

    # --- Step 2: merge close segments ---
    segments = _merge_segments(raw_segments, snapshots)

    # --- Step 3: build trip rows ---
    trip_rows = [r for seg in segments if (r := _build_trip_row(seg))]

    # --- Step 4: group by day ---
    by_day: dict[str, dict] = {}
    total_energy_kwh = 0.0
    total_distance_km = 0.0
    total_hours = 0.0

    for trip in trip_rows:
        day = trip["beginTime"][:10]
        bucket = by_day.setdefault(
            day,
            {
                "day": day,
                "accumulated_enery_consume": 0,
                "accumulated_mileage": 0.0,
                "current_mileage": 0.0,
                "drivingRecord": [],
            },
        )
        bucket["drivingRecord"].append(
            {
                "beginTime": trip["beginTime"],
                "endTime": trip["endTime"],
                "travelMile": trip["travelMile"],
                "eneryConsume": trip["eneryConsume"],
                "recoveryEnery": trip["recoveryEnery"],
                "maxSpeed": trip["maxSpeed"],
                "avgSpeed": trip["avgSpeed"],
                "startSoc": trip["startSoc"],
                "endSoc": trip["endSoc"],
                "outdoorTemp": trip["outdoorTemp"],
                "startLat": trip["startLat"],
                "startLng": trip["startLng"],
                "endLat": trip["endLat"],
                "endLng": trip["endLng"],
                "gpskey": trip["gpskey"],
            }
        )
        bucket["accumulated_enery_consume"] += trip["eneryConsume"]
        bucket["accumulated_mileage"] += trip["_travel_km"]
        bucket["current_mileage"] = round(bucket["accumulated_mileage"], 2)

        total_energy_kwh += trip["_energy_kwh"]
        total_distance_km += trip["_travel_km"]
        total_hours += trip["_duration_h"]

    for b in by_day.values():
        b["accumulated_mileage"] = round(b["accumulated_mileage"], 2)

    ordered_days = sorted(by_day.values(), key=lambda d: d["day"], reverse=True)
    return {
        "source": "local_history",
        "total_enery": round(total_energy_kwh, 3),
        "total_milage": round(total_distance_km, 2),
        "total_ustime": round(total_hours, 2),
        "data": ordered_days,
    }


def _calculate_local_regen_energy_kwh(snapshots: list[VehicleSnapshot]) -> float:
    total = 0.0
    for i in range(1, len(snapshots)):
        prev = snapshots[i - 1]
        curr = snapshots[i]
        if not curr.vehicle_is_regening:
            continue
        power_kw = curr.battery_charging_power_kw
        if power_kw is None or power_kw <= 0:
            continue
        dt_h = (curr.timestamp - prev.timestamp).total_seconds() / 3600
        if dt_h <= 0 or dt_h > 0.5:
            continue
        total += power_kw * dt_h
    return round(total, 3)


def _segment_regen_energy_wh(segment: list[VehicleSnapshot]) -> float:
    """Calculate regenerative braking energy (in Wh) for a single trip segment."""
    total = 0.0
    for i in range(1, len(segment)):
        prev = segment[i - 1]
        curr = segment[i]
        if not curr.vehicle_is_regening:
            continue
        power_kw = curr.battery_charging_power_kw
        if power_kw is None or power_kw <= 0:
            continue
        dt_h = (curr.timestamp - prev.timestamp).total_seconds() / 3600
        if dt_h <= 0 or dt_h > 0.5:
            continue
        total += power_kw * dt_h * 1000  # kWh → Wh
    return round(total, 1)


def _flatten_trip_rows(payload: dict) -> list[dict]:
    return [
        trip
        for day in payload.get("data", [])
        for trip in day.get("drivingRecord", [])
        if isinstance(trip, dict)
    ]


def _trip_distance_km(trip: dict) -> float:
    return max(0.0, (float(trip.get("travelMile") or 0.0)) / 1000.0)


def _trip_duration_h(trip: dict) -> float:
    try:
        start_dt = datetime.strptime(trip["beginTime"], "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(trip["endTime"], "%Y-%m-%d %H:%M:%S")
        return max(0.0, (end_dt - start_dt).total_seconds() / 3600.0)
    except (KeyError, TypeError, ValueError):
        return 0.0


def _trip_start_hour(trip: dict) -> int | None:
    try:
        start_dt = datetime.strptime(trip["beginTime"], "%Y-%m-%d %H:%M:%S")
        return start_dt.hour
    except (KeyError, TypeError, ValueError):
        return None


def _trip_consumption_kwh_100km(trip: dict) -> float | None:
    km = _trip_distance_km(trip)
    kwh = (float(trip.get("eneryConsume") or 0.0)) / 1000.0
    if km <= 0:
        return None
    return (kwh / km) * 100.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(d_lon / 2) ** 2
    )
    return radius_km * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def _trip_similarity_breakdown(reference: dict, candidate: dict) -> dict:
    ref_distance = _trip_distance_km(reference)
    cand_distance = _trip_distance_km(candidate)

    # Distance score: 1 when equal, 0 when difference >= 100% of reference.
    if ref_distance <= 0:
        distance_score = 0.0
    else:
        distance_score = 1.0 - min(
            1.0, abs(cand_distance - ref_distance) / ref_distance
        )

    # Time score on circular 24h clock.
    ref_hour = _trip_start_hour(reference)
    cand_hour = _trip_start_hour(candidate)
    if ref_hour is None or cand_hour is None:
        time_score = 0.0
    else:
        hour_diff = abs(ref_hour - cand_hour)
        hour_diff = min(hour_diff, 24 - hour_diff)
        time_score = 1.0 - min(1.0, hour_diff / 12.0)

    # Route score based on start/end distance; fallback if GPS anchors are missing.
    route_score = 0.5
    try:
        ref_start = (float(reference["startLat"]), float(reference["startLng"]))
        ref_end = (float(reference["endLat"]), float(reference["endLng"]))
        cand_start = (float(candidate["startLat"]), float(candidate["startLng"]))
        cand_end = (float(candidate["endLat"]), float(candidate["endLng"]))
        start_d = _haversine_km(
            ref_start[0],
            ref_start[1],
            cand_start[0],
            cand_start[1],
        )
        end_d = _haversine_km(ref_end[0], ref_end[1], cand_end[0], cand_end[1])
        avg_d = (start_d + end_d) / 2.0
        route_score = 1.0 - min(1.0, avg_d / 30.0)
    except (KeyError, TypeError, ValueError):
        route_score = 0.5

    score = 0.40 * route_score + 0.35 * time_score + 0.25 * distance_score

    return {
        "score": round(score, 4),
        "breakdown": {
            "route": round(route_score, 4),
            "time": round(time_score, 4),
            "distance": round(distance_score, 4),
        },
    }


def _trip_compare_metrics(reference: dict, candidate: dict) -> dict:
    ref_distance = _trip_distance_km(reference)
    cand_distance = _trip_distance_km(candidate)
    ref_duration = _trip_duration_h(reference)
    cand_duration = _trip_duration_h(candidate)

    ref_cons = _trip_consumption_kwh_100km(reference)
    cand_cons = _trip_consumption_kwh_100km(candidate)
    ref_regen = (float(reference.get("recoveryEnery") or 0.0)) / 1000.0
    cand_regen = (float(candidate.get("recoveryEnery") or 0.0)) / 1000.0

    ref_avg_speed = float(reference.get("avgSpeed") or 0.0)
    cand_avg_speed = float(candidate.get("avgSpeed") or 0.0)
    ref_temp = reference.get("outdoorTemp")
    cand_temp = candidate.get("outdoorTemp")

    return {
        "efficiency": {
            "consumption_kwh_100km": {
                "reference": round(ref_cons, 2) if ref_cons is not None else None,
                "candidate": round(cand_cons, 2) if cand_cons is not None else None,
                "delta": round((cand_cons - ref_cons), 2)
                if ref_cons is not None and cand_cons is not None
                else None,
            },
            "regen_kwh": {
                "reference": round(ref_regen, 3),
                "candidate": round(cand_regen, 3),
                "delta": round(cand_regen - ref_regen, 3),
            },
        },
        "performance": {
            "distance_km": {
                "reference": round(ref_distance, 2),
                "candidate": round(cand_distance, 2),
                "delta": round(cand_distance - ref_distance, 2),
            },
            "duration_h": {
                "reference": round(ref_duration, 2),
                "candidate": round(cand_duration, 2),
                "delta": round(cand_duration - ref_duration, 2),
            },
            "avg_speed_kmh": {
                "reference": round(ref_avg_speed, 1),
                "candidate": round(cand_avg_speed, 1),
                "delta": round(cand_avg_speed - ref_avg_speed, 1),
            },
        },
        "conditions": {
            "outside_temp_c": {
                "reference": ref_temp,
                "candidate": cand_temp,
                "delta": (cand_temp - ref_temp)
                if ref_temp is not None and cand_temp is not None
                else None,
            },
        },
    }


def _detect_local_charge_sessions(snapshots: list[VehicleSnapshot]) -> list[dict]:
    sessions: list[dict] = []
    in_session = False
    start_idx = -1

    for i, snap in enumerate(snapshots):
        is_charging = bool(snap.battery_is_charging)
        if is_charging and not in_session:
            in_session = True
            start_idx = i
        elif not is_charging and in_session:
            in_session = False
            start_snap = snapshots[start_idx]
            end_snap = snapshots[i - 1] if i > 0 else snap

            start_energy = (
                start_snap.battery_dump_energy / 1000
                if start_snap.battery_dump_energy is not None
                else None
            )
            end_energy = (
                end_snap.battery_dump_energy / 1000
                if end_snap.battery_dump_energy is not None
                else None
            )
            energy = (
                abs(end_energy - start_energy)
                if start_energy is not None and end_energy is not None
                else None
            )
            sessions.append(
                {
                    "start_ts": start_snap.timestamp,
                    "end_ts": end_snap.timestamp,
                    "energy_kwh": round(energy, 3) if energy is not None else None,
                }
            )

    if in_session and start_idx >= 0:
        start_snap = snapshots[start_idx]
        end_snap = snapshots[-1]
        start_energy = (
            start_snap.battery_dump_energy / 1000
            if start_snap.battery_dump_energy is not None
            else None
        )
        end_energy = (
            end_snap.battery_dump_energy / 1000
            if end_snap.battery_dump_energy is not None
            else None
        )
        energy = (
            abs(end_energy - start_energy)
            if start_energy is not None and end_energy is not None
            else None
        )
        sessions.append(
            {
                "start_ts": start_snap.timestamp,
                "end_ts": None,
                "energy_kwh": round(energy, 3) if energy is not None else None,
            }
        )

    return sessions


@app.get("/api/vehicles/{vin}/trips")
async def get_trips(
    vin: str,
    begin_time: str | None = None,
    end_time: str | None = None,
):
    """Get driving records from locally collected history snapshots."""
    from datetime import date as date_cls
    from datetime import timedelta

    if not _history_repo:
        raise HTTPException(status_code=503, detail="History not available")

    _find_vehicle(vin)
    today = date_cls.today()
    bt = _parse_range_date(begin_time) or (today - timedelta(days=30)).isoformat()
    et = _parse_range_date(end_time) or today.isoformat()
    snapshots = await _history_repo.get_history(
        vin,
        from_date=bt,
        to_date=et,
        max_points=10_000,
    )
    return _build_local_trip_payload(snapshots)


@app.get("/api/vehicles/{vin}/trips/totals")
async def get_trips_totals(
    vin: str,
    begin_time: str | None = None,
    end_time: str | None = None,
):
    """Get total driving statistics computed from local history snapshots."""
    from datetime import date as date_cls
    from datetime import timedelta

    if not _history_repo:
        raise HTTPException(status_code=503, detail="History not available")

    _find_vehicle(vin)
    today = date_cls.today()
    bt = _parse_range_date(begin_time) or (today - timedelta(days=30)).isoformat()
    et = _parse_range_date(end_time) or today.isoformat()
    snapshots = await _history_repo.get_history(
        vin,
        from_date=bt,
        to_date=et,
        max_points=10_000,
    )
    payload = _build_local_trip_payload(snapshots)

    # Flatten trip rows for totals.
    trip_rows = [
        trip for day in payload.get("data", []) for trip in day.get("drivingRecord", [])
    ]
    max_speed = max((s.drive_speed or 0) for s in snapshots) if snapshots else 0
    total_hours = 0.0
    for trip in trip_rows:
        try:
            bt_dt = datetime.strptime(trip["beginTime"], "%Y-%m-%d %H:%M:%S")
            et_dt = datetime.strptime(trip["endTime"], "%Y-%m-%d %H:%M:%S")
            total_hours += max(0.0, (et_dt - bt_dt).total_seconds() / 3600)
        except (ValueError, KeyError):
            continue

    return {
        "source": "local_history",
        "maxspeed": int(max_speed),
        "totalenery": round(float(payload.get("total_enery", 0.0)), 3),
        "totalmileage": round(float(payload.get("total_milage", 0.0)), 2),
        "totalrecoveryenery": _calculate_local_regen_energy_kwh(snapshots),
        "ustime": round(total_hours, 2),
    }


@app.get("/api/vehicles/{vin}/trips/gps/{gpskey}")
async def get_trip_gps(vin: str, gpskey: str):
    """Get trip GPS trace from local history snapshots."""
    if not _history_repo:
        raise HTTPException(status_code=503, detail="History not available")

    _find_vehicle(vin)
    try:
        start_raw, end_raw = gpskey.split("_", 1)
        start_dt = datetime.utcfromtimestamp(int(start_raw))
        end_dt = datetime.utcfromtimestamp(int(end_raw))
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"Invalid gpskey: {gpskey}"
        ) from exc

    snapshots = await _history_repo.get_history(
        vin,
        from_date=start_dt.date().isoformat(),
        to_date=end_dt.date().isoformat(),
        max_points=10_000,
    )
    points = [
        {
            "timestamp": s.timestamp.isoformat(),
            "lat": s.vehicle_latitude,
            "lng": s.vehicle_longitude,
            "speed": s.drive_speed,
        }
        for s in snapshots
        if (
            s.vehicle_latitude is not None
            and s.vehicle_longitude is not None
            and start_dt <= s.timestamp <= end_dt
        )
    ]
    return points


@app.get("/api/vehicles/{vin}/trips/similar")
async def get_similar_trips(
    vin: str,
    gpskey: str,
    limit: int = 3,
    begin_time: str | None = None,
    end_time: str | None = None,
):
    """Suggest trips similar to a reference trip.

    Similarity score is composed by route (40%), time-of-day (35%), and
    distance (25%).
    """
    from datetime import date as date_cls
    from datetime import timedelta

    if not _history_repo:
        raise HTTPException(status_code=503, detail="History not available")

    _find_vehicle(vin)
    today = date_cls.today()
    bt = _parse_range_date(begin_time) or (today - timedelta(days=90)).isoformat()
    et = _parse_range_date(end_time) or today.isoformat()
    snapshots = await _history_repo.get_history(
        vin,
        from_date=bt,
        to_date=et,
        max_points=50_000,
    )
    payload = _build_local_trip_payload(snapshots)
    trips = _flatten_trip_rows(payload)

    # Try exact gpskey match first; if downsampling shifted boundaries,
    # fall back to fuzzy match using the timestamps embedded in gpskey.
    reference = next((t for t in trips if t.get("gpskey") == gpskey), None)
    if not reference:
        try:
            ref_start_ts, ref_end_ts = gpskey.split("_", 1)
            ref_start = int(ref_start_ts)
            ref_end = int(ref_end_ts)
            # Allow ±120 seconds tolerance for downsampling-induced shifts
            for t in trips:
                t_start = t.get("beginTime", "")
                t_end = t.get("endTime", "")
                if not t_start or not t_end:
                    continue
                try:
                    ts_s = int(
                        datetime.strptime(t_start, "%Y-%m-%d %H:%M:%S")
                        .replace(tzinfo=UTC)
                        .timestamp()
                    )
                    ts_e = int(
                        datetime.strptime(t_end, "%Y-%m-%d %H:%M:%S")
                        .replace(tzinfo=UTC)
                        .timestamp()
                    )
                except (ValueError, OSError):
                    continue
                if abs(ts_s - ref_start) <= 120 and abs(ts_e - ref_end) <= 120:
                    reference = t
                    break
        except (ValueError, IndexError):
            pass

    if not reference:
        raise HTTPException(
            status_code=404,
            detail=f"Trip not found for gpskey={gpskey}",
        )

    candidates: list[dict] = []
    ref_distance = _trip_distance_km(reference)
    ref_hour = _trip_start_hour(reference)
    for trip in trips:
        if trip.get("gpskey") == gpskey:
            continue

        cand_distance = _trip_distance_km(trip)
        if ref_distance > 0:
            ratio = cand_distance / ref_distance if ref_distance else 0
            if ratio < 0.6 or ratio > 1.4:
                continue

        cand_hour = _trip_start_hour(trip)
        if ref_hour is not None and cand_hour is not None:
            hour_diff = abs(ref_hour - cand_hour)
            hour_diff = min(hour_diff, 24 - hour_diff)
            if hour_diff > 6:
                continue

        similarity = _trip_similarity_breakdown(reference, trip)
        metrics = _trip_compare_metrics(reference, trip)
        candidates.append(
            {
                "trip": trip,
                "similarity_score": similarity["score"],
                "score_breakdown": similarity["breakdown"],
                "metrics": metrics,
            }
        )

    candidates.sort(
        key=lambda c: (
            c["similarity_score"],
            c["trip"].get("beginTime", ""),
        ),
        reverse=True,
    )
    max_limit = max(1, min(int(limit or 3), 10))

    return {
        "source": "local_history",
        "reference": reference,
        "count": len(candidates),
        "items": candidates[:max_limit],
    }


@app.get("/api/vehicles/{vin}/charge-stats/cloud")
async def get_charge_stats_cloud(
    vin: str,
    begin_time: str | None = None,
    end_time: str | None = None,
):
    """Get daily charging statistics derived from local history."""
    from datetime import date as date_cls
    from datetime import timedelta

    if not _history_repo:
        raise HTTPException(status_code=503, detail="History not available")

    _find_vehicle(vin)
    today = date_cls.today()
    bt = _parse_range_date(begin_time) or (today - timedelta(days=30)).isoformat()
    et = _parse_range_date(end_time) or today.isoformat()

    snapshots = await _history_repo.get_history(
        vin,
        from_date=bt,
        to_date=et,
        max_points=10_000,
    )
    sessions = _detect_local_charge_sessions(snapshots)

    days: dict[str, dict] = {}
    for session in sessions:
        day = session["start_ts"].date().isoformat()
        bucket = days.setdefault(
            day,
            {
                "date": day,
                "sessions": 0,
                "energy_kwh": 0.0,
            },
        )
        bucket["sessions"] += 1
        bucket["energy_kwh"] += float(session["energy_kwh"] or 0.0)

    ordered = sorted(days.values(), key=lambda d: d["date"])
    total_energy = round(sum(d["energy_kwh"] for d in ordered), 3)
    return {
        "source": "local_history",
        "vin": vin,
        "beginTime": bt,
        "endTime": et,
        "days": [
            {
                "date": d["date"],
                "sessions": d["sessions"],
                "energy_kwh": round(d["energy_kwh"], 3),
            }
            for d in ordered
        ],
        "total_sessions": sum(d["sessions"] for d in ordered),
        "total_energy_kwh": total_energy,
    }


@app.get("/api/vehicles/{vin}/charge-stats/year")
async def get_charge_stats_year(vin: str, year: str | None = None):
    """Get annual charging statistics derived from local history."""
    from datetime import date as date_cls

    if not _history_repo:
        raise HTTPException(status_code=503, detail="History not available")

    _find_vehicle(vin)
    y = year or str(date_cls.today().year)
    if not y.isdigit() or len(y) != 4:
        raise HTTPException(status_code=422, detail="year must be YYYY")

    from_date = f"{y}-01-01"
    to_date = f"{y}-12-31"
    snapshots = await _history_repo.get_history(
        vin,
        from_date=from_date,
        to_date=to_date,
        max_points=20_000,
    )
    sessions = _detect_local_charge_sessions(snapshots)

    months: dict[str, dict] = {}
    for session in sessions:
        month = session["start_ts"].strftime("%Y-%m")
        bucket = months.setdefault(
            month,
            {
                "month": month,
                "sessions": 0,
                "energy_kwh": 0.0,
            },
        )
        bucket["sessions"] += 1
        bucket["energy_kwh"] += float(session["energy_kwh"] or 0.0)

    ordered = sorted(months.values(), key=lambda m: m["month"])
    return {
        "source": "local_history",
        "vin": vin,
        "year": y,
        "months": [
            {
                "month": m["month"],
                "sessions": m["sessions"],
                "energy_kwh": round(m["energy_kwh"], 3),
            }
            for m in ordered
        ],
        "total_sessions": sum(m["sessions"] for m in ordered),
        "total_energy_kwh": round(sum(m["energy_kwh"] for m in ordered), 3),
    }


# ---------------------------------------------------------------------------
# Routes — Messages
# ---------------------------------------------------------------------------


@app.get("/api/messages", response_model=MessageListResponse)
async def get_messages(page_no: int = 1, page_size: int = 20) -> MessageListResponse:
    """Get paginated notification messages from the account."""
    client = _get_client()
    try:
        msg_list: MessageList = await client.get_message_list(
            page_no=page_no, page_size=page_size
        )
    except LeapmotorApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
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
    try:
        count = await client.get_unread_message_count()
    except LeapmotorApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return UnreadCountResponse(unread=count)


# ---------------------------------------------------------------------------
# Logging — level control & live viewer
# ---------------------------------------------------------------------------

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


@app.get("/api/logs/levels")
async def get_log_levels():
    """Return current log levels for app and leapmotor-api library."""
    app_level = logging.getLogger("__main__").getEffectiveLevel()
    lib_level = logging.getLogger("leapmotor_api").getEffectiveLevel()
    return {
        "app_level": logging.getLevelName(app_level),
        "library_level": logging.getLevelName(lib_level),
    }


class _LogLevelBody(BaseModel):
    app_level: str | None = None
    library_level: str | None = None


@app.put("/api/logs/levels")
async def set_log_levels(body: _LogLevelBody):
    """Change log levels at runtime for app and/or leapmotor-api."""
    if body.app_level:
        level = body.app_level.upper()
        if level not in _VALID_LOG_LEVELS:
            raise HTTPException(status_code=400, detail=f"Invalid level: {level}")
        logging.getLogger("__main__").setLevel(level)
        logging.getLogger("main").setLevel(level)
        _LOGGER.info("App log level changed to %s", level)
    if body.library_level:
        level = body.library_level.upper()
        if level not in _VALID_LOG_LEVELS:
            raise HTTPException(status_code=400, detail=f"Invalid level: {level}")
        logging.getLogger("leapmotor_api").setLevel(level)
        _LOGGER.info("leapmotor-api log level changed to %s", level)
    # Return current state
    return await get_log_levels()


@app.get("/api/logs/entries")
async def get_log_entries(limit: int = 200):
    """Return recent log entries from the in-memory buffer."""
    if limit < 1:
        limit = 1
    elif limit > 2000:
        limit = 2000
    return {"entries": _log_handler.get_entries(limit)}


# ---------------------------------------------------------------------------
# Notification Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/notifications/channels")
async def get_notification_channels(
    request: Request,
) -> list[NotificationChannelResponse]:
    """List all configured notification channels."""
    channels = await _history_repo.get_notification_channels()
    return [
        NotificationChannelResponse(
            id=ch.id,
            channel_type=ch.channel_type,
            config=ch.config,
            enabled=ch.enabled,
            created_at=ch.created_at.isoformat() if ch.created_at else None,
        )
        for ch in channels
    ]


@app.post("/api/notifications/channels")
async def create_notification_channel(
    request: Request, body: NotificationChannelCreate
) -> NotificationChannelResponse:
    """Create a new notification channel."""
    channel = NotificationChannel(
        channel_type=body.channel_type,
        config=body.config,
        enabled=body.enabled,
    )
    saved = await _history_repo.save_notification_channel(channel)
    # Reload dispatcher config
    if _notification_dispatcher:
        await _notification_dispatcher.reload_config()
    return NotificationChannelResponse(
        id=saved.id,
        channel_type=saved.channel_type,
        config=saved.config,
        enabled=saved.enabled,
        created_at=saved.created_at.isoformat() if saved.created_at else None,
    )


@app.put("/api/notifications/channels/{channel_id}")
async def update_notification_channel(
    request: Request, channel_id: int, body: NotificationChannelUpdate
) -> NotificationChannelResponse:
    """Update a notification channel."""
    existing = await _history_repo.get_notification_channel(channel_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Channel not found")
    if body.config is not None:
        existing.config = body.config
    if body.enabled is not None:
        existing.enabled = body.enabled
    saved = await _history_repo.save_notification_channel(existing)
    if _notification_dispatcher:
        await _notification_dispatcher.reload_config()
    return NotificationChannelResponse(
        id=saved.id,
        channel_type=saved.channel_type,
        config=saved.config,
        enabled=saved.enabled,
        created_at=saved.created_at.isoformat() if saved.created_at else None,
    )


@app.delete("/api/notifications/channels/{channel_id}")
async def delete_notification_channel(
    request: Request, channel_id: int
) -> StatusResponse:
    """Delete a notification channel."""
    deleted = await _history_repo.delete_notification_channel(channel_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Channel not found")
    if _notification_dispatcher:
        await _notification_dispatcher.reload_config()
    return StatusResponse(status="ok")


@app.post("/api/notifications/channels/{channel_id}/test")
async def test_notification_channel(request: Request, channel_id: int) -> dict:
    """Send a test notification via the specified channel."""
    channel = await _history_repo.get_notification_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    notifier = NotificationDispatcher._create_notifier(channel)
    if not notifier:
        raise HTTPException(status_code=400, detail="Invalid channel configuration")
    success, message = await notifier.test_connection()
    return {"success": success, "message": message}


@app.post("/api/notifications/channels/{channel_id}/test-event")
async def test_notification_event(request: Request, channel_id: int) -> dict:
    """Send a test notification for a specific event type."""
    if not _notification_dispatcher:
        raise HTTPException(
            status_code=503, detail="Notification dispatcher not available"
        )
    body = await request.json()
    event_type = body.get("event_type")
    if not event_type:
        raise HTTPException(status_code=400, detail="event_type is required")
    vin = body.get("vin", "")
    success, message = await _notification_dispatcher.send_test_event(
        channel_id, event_type, vin=vin
    )
    return {"success": success, "message": message}


@app.get("/api/notifications/cooldown")
async def get_notification_cooldown() -> dict:
    """Get the notification cooldown duration in seconds."""
    raw = await _history_repo.get_setting("notification_cooldown_seconds")
    return {"cooldown_seconds": int(float(raw)) if raw else 300}


@app.put("/api/notifications/cooldown")
async def update_notification_cooldown(request: Request) -> dict:
    """Set the notification cooldown duration in seconds."""
    body = await request.json()
    value = body.get("cooldown_seconds")
    if value is None:
        raise HTTPException(status_code=422, detail="'cooldown_seconds' is required")
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="'cooldown_seconds' must be an integer"
        ) from exc
    if value < 0 or value > 86400:
        raise HTTPException(
            status_code=422, detail="'cooldown_seconds' must be between 0 and 86400"
        )
    await _history_repo.save_setting("notification_cooldown_seconds", str(value))
    if _notification_dispatcher:
        await _notification_dispatcher.reload_config()
    return {"cooldown_seconds": value}


# ---------------------------------------------------------------------------
# Routes — Location Tracking
# ---------------------------------------------------------------------------


@app.post("/api/tracking/{vin}/start")
async def start_tracking(request: Request, vin: str) -> dict:
    """Start periodic location tracking for a vehicle."""
    if not _notification_dispatcher:
        raise HTTPException(
            status_code=503, detail="Notification dispatcher not available"
        )
    body = await request.json()
    interval = body.get("interval_seconds", 60)
    try:
        interval = int(interval)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="'interval_seconds' must be an integer"
        ) from exc
    if interval < 10 or interval > 3600:
        raise HTTPException(
            status_code=422, detail="'interval_seconds' must be between 10 and 3600"
        )
    await _notification_dispatcher.start_tracking(vin, interval_seconds=interval)
    return {"tracking": True, "vin": vin, "interval_seconds": interval}


@app.post("/api/tracking/{vin}/stop")
async def stop_tracking_post(request: Request, vin: str) -> dict:
    """Stop location tracking for a vehicle (POST)."""
    if not _notification_dispatcher:
        raise HTTPException(
            status_code=503, detail="Notification dispatcher not available"
        )
    stopped = await _notification_dispatcher.stop_tracking(vin)
    return {"tracking": False, "vin": vin, "stopped": stopped}


@app.get("/api/tracking/{vin}")
async def get_tracking_status(vin: str) -> dict:
    """Get tracking status for a vehicle."""
    if not _notification_dispatcher:
        return {"tracking": False, "vin": vin}
    info = _notification_dispatcher.get_tracking_info(vin)
    if info:
        return {"tracking": True, "vin": vin, **info}
    return {"tracking": False, "vin": vin}


@app.get("/api/notifications/events")
async def get_notification_events(
    request: Request, channel_id: int | None = None
) -> list[NotificationEventStatus]:
    """List all available notification events with their current status."""

    # Get preferences for the specified channel (or first channel)
    prefs_map: dict[str, NotificationPreference] = {}
    if channel_id:
        prefs = await _history_repo.get_notification_preferences(channel_id)
        prefs_map = {p.event_type: p for p in prefs}
    else:
        channels = await _history_repo.get_notification_channels()
        if channels:
            prefs = await _history_repo.get_notification_preferences(channels[0].id)
            prefs_map = {p.event_type: p for p in prefs}

    result = []
    for event in EVENT_CATALOG:
        pref = prefs_map.get(event["event_type"])
        result.append(
            NotificationEventStatus(
                event_type=event["event_type"],
                label=event["label"],
                description=event["description"],
                category=event["category"],
                has_image=event.get("has_image", False),
                configurable=event.get("configurable", False),
                config_schema=event.get("config_schema"),
                enabled=pref.enabled if pref else False,
                config=pref.config if pref else None,
            )
        )
    return result


@app.put("/api/notifications/events")
async def update_notification_events(
    request: Request, body: NotificationPreferencesUpdate
) -> StatusResponse:
    """Bulk update notification preferences for a channel."""
    channel = await _history_repo.get_notification_channel(body.channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    prefs = [
        NotificationPreference(
            channel_id=body.channel_id,
            event_type=item.event_type,
            enabled=item.enabled,
            config=item.config,
        )
        for item in body.preferences
    ]
    await _history_repo.save_notification_preferences(body.channel_id, prefs)
    if _notification_dispatcher:
        await _notification_dispatcher.reload_config()
    return StatusResponse(status="ok")


# -- Geofences --


def _geofence_to_response(gf: Geofence) -> GeofenceResponse:
    return GeofenceResponse(
        id=gf.id,
        vin=gf.vin,
        name=gf.name,
        shape_type=gf.shape_type,
        latitude=gf.latitude,
        longitude=gf.longitude,
        radius_m=gf.radius_m,
        points=gf.points,
        notify_on_enter=gf.notify_on_enter,
        notify_on_exit=gf.notify_on_exit,
        enabled=gf.enabled,
    )


def _polygon_centroid(points: list[list[float]]) -> tuple[float, float]:
    """Average of the polygon vertices, used for map centering/fit."""
    lat = sum(p[0] for p in points) / len(points)
    lon = sum(p[1] for p in points) / len(points)
    return lat, lon


@app.get("/api/notifications/geofences")
async def get_geofences(
    request: Request, vin: str | None = None
) -> list[GeofenceResponse]:
    """List geofences, optionally filtered by VIN."""
    geofences = await _history_repo.get_geofences(vin=vin)
    return [_geofence_to_response(gf) for gf in geofences]


@app.post("/api/notifications/geofences")
async def create_geofence(request: Request, body: GeofenceCreate) -> GeofenceResponse:
    """Create a new geofence."""
    latitude, longitude = body.latitude, body.longitude
    points = body.points
    if body.shape_type == "polygon":
        if not points or len(points) < 3:
            raise HTTPException(
                status_code=400, detail="A polygon geofence needs at least 3 points"
            )
        latitude, longitude = _polygon_centroid(points)
    else:
        points = None
    gf = Geofence(
        vin=body.vin,
        name=body.name,
        shape_type=body.shape_type,
        latitude=latitude,
        longitude=longitude,
        radius_m=body.radius_m,
        points=points,
        notify_on_enter=body.notify_on_enter,
        notify_on_exit=body.notify_on_exit,
        enabled=body.enabled,
    )
    saved = await _history_repo.save_geofence(gf)
    if _notification_dispatcher:
        await _notification_dispatcher.reload_config()
    return _geofence_to_response(saved)


@app.put("/api/notifications/geofences/{geofence_id}")
async def update_geofence(
    request: Request, geofence_id: int, body: GeofenceUpdate
) -> GeofenceResponse:
    """Update a geofence."""
    geofences = await _history_repo.get_geofences()
    existing = next((gf for gf in geofences if gf.id == geofence_id), None)
    if not existing:
        raise HTTPException(status_code=404, detail="Geofence not found")
    if body.name is not None:
        existing.name = body.name
    if body.shape_type is not None:
        existing.shape_type = body.shape_type
    if body.radius_m is not None:
        existing.radius_m = body.radius_m
    if body.notify_on_enter is not None:
        existing.notify_on_enter = body.notify_on_enter
    if body.notify_on_exit is not None:
        existing.notify_on_exit = body.notify_on_exit
    if body.enabled is not None:
        existing.enabled = body.enabled
    if body.points is not None:
        existing.points = body.points
    # Recompute geometry: polygons derive center from points, circles use lat/lon.
    if existing.shape_type == "polygon":
        if not existing.points or len(existing.points) < 3:
            raise HTTPException(
                status_code=400, detail="A polygon geofence needs at least 3 points"
            )
        existing.latitude, existing.longitude = _polygon_centroid(existing.points)
    else:
        existing.points = None
        if body.latitude is not None:
            existing.latitude = body.latitude
        if body.longitude is not None:
            existing.longitude = body.longitude
    saved = await _history_repo.save_geofence(existing)
    if _notification_dispatcher:
        await _notification_dispatcher.reload_config()
    return _geofence_to_response(saved)


@app.delete("/api/notifications/geofences/{geofence_id}")
async def delete_geofence_endpoint(
    request: Request, geofence_id: int
) -> StatusResponse:
    """Delete a geofence."""
    deleted = await _history_repo.delete_geofence(geofence_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Geofence not found")
    if _notification_dispatcher:
        await _notification_dispatcher.reload_config()
    return StatusResponse(status="ok")


@app.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket) -> None:
    """Stream live log entries to connected clients via WebSocket."""
    token = websocket.query_params.get(
        "token",
    ) or websocket.cookies.get(SESSION_COOKIE_NAME)
    if not _validate_session(token):
        await websocket.close(code=4401, reason="Unauthorized")
        return

    await websocket.accept()
    _log_handler.register_ws(websocket)
    _LOGGER.info("Log viewer WebSocket connected")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _log_handler.unregister_ws(websocket)
        _LOGGER.info("Log viewer WebSocket disconnected")


# ---------------------------------------------------------------------------
# Telegram Users (multi-user access management)
# ---------------------------------------------------------------------------


@app.get("/api/notifications/channels/telegram/users")
async def get_telegram_users(
    request: Request, status: str | None = None
) -> list[TelegramUserResponse]:
    """List all Telegram users, optionally filtered by status."""
    users = await _history_repo.get_telegram_users(status=status)
    return [
        TelegramUserResponse(
            id=u.id,
            chat_id=u.chat_id,
            username=u.username,
            first_name=u.first_name,
            last_name=u.last_name,
            status=u.status,
            created_at=u.created_at.isoformat() if u.created_at else None,
            approved_at=u.approved_at.isoformat() if u.approved_at else None,
        )
        for u in users
    ]


@app.put("/api/notifications/channels/telegram/users/{chat_id}/approve")
async def approve_telegram_user(request: Request, chat_id: str) -> StatusResponse:
    """Approve a pending Telegram user."""
    updated = await _history_repo.update_telegram_user_status(chat_id, "approved")
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    if _notification_dispatcher:
        await _notification_dispatcher.refresh_telegram_users()
        await _notification_dispatcher.notify_telegram_user_status(chat_id, "approved")
    return StatusResponse(status="ok")


@app.put("/api/notifications/channels/telegram/users/{chat_id}/reject")
async def reject_telegram_user(request: Request, chat_id: str) -> StatusResponse:
    """Reject a pending Telegram user."""
    updated = await _history_repo.update_telegram_user_status(chat_id, "rejected")
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    if _notification_dispatcher:
        await _notification_dispatcher.refresh_telegram_users()
        await _notification_dispatcher.notify_telegram_user_status(chat_id, "rejected")
    return StatusResponse(status="ok")


@app.delete("/api/notifications/channels/telegram/users/{chat_id}")
async def delete_telegram_user(request: Request, chat_id: str) -> StatusResponse:
    """Remove a Telegram user entirely."""
    deleted = await _history_repo.delete_telegram_user(chat_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    if _notification_dispatcher:
        await _notification_dispatcher.refresh_telegram_users()
    return StatusResponse(status="ok")


@app.post("/api/notifications/channels/telegram/link-token")
async def create_telegram_link_token(request: Request) -> TelegramLinkTokenResponse:
    """Generate a deep-link token for Telegram account linking."""
    token = await _history_repo.create_link_token()
    # Get bot username for the link
    bot_username = None
    if _notification_dispatcher:
        notifier = _notification_dispatcher.get_telegram_notifier()
        if notifier:
            bot_username = await notifier.get_bot_username()
    if not bot_username:
        raise HTTPException(
            status_code=503,
            detail="Bot username not available. Ensure Telegram bot is configured.",
        )
    from datetime import UTC, datetime, timedelta

    expires_at = datetime.now(UTC) + timedelta(minutes=10)
    link = f"https://t.me/{bot_username}?start={token}"
    return TelegramLinkTokenResponse(
        token=token,
        link=link,
        expires_at=expires_at.isoformat(),
    )


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


def _cli_reset_password(new_password: str) -> None:
    """Reset the LeapConnect user password from the command line."""
    import asyncio as _asyncio

    if len(new_password) < 4:
        print("Error: Password must be at least 4 characters")
        raise SystemExit(1)

    db_path = os.environ.get(
        "HISTORY_DB_PATH", str(Path(__file__).parent / "leapconnect.db")
    )
    db_url = f"sqlite+aiosqlite:///{db_path}"

    async def _reset():
        repo = SQLAlchemyVehicleHistoryRepository(db_url)
        await repo.init_db()
        user = await repo.get_user()
        if not user:
            print("Error: No user account found. Nothing to reset.")
            return False
        await repo.update_user(password=new_password)
        print(f"Password reset successfully for user '{user['display_name']}'.")
        return True

    success = _asyncio.run(_reset())
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    import sys

    import uvicorn

    if len(sys.argv) >= 2 and sys.argv[1] == "--reset-password":
        if len(sys.argv) < 3:
            print("Usage: python main.py --reset-password <new_password>")
            raise SystemExit(1)
        _cli_reset_password(sys.argv[2])
    else:
        uvicorn.run(app, host="0.0.0.0", port=8099)
