"""System routes: preferences, scheduler, database, MQTT, ABRP, messages, logs."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Request
from leapmotor_api.models import MessageList
from pydantic import BaseModel

from leapconnect import config
from leapconnect.api.deps import ClientDep, ContainerDep, RepoDep
from leapconnect.api.schemas import (
    AbrpStatusResponse,
    DatabaseSizeResponse,
    MessageListResponse,
    MessageSchema,
    MqttStatusResponse,
    MqttTestResponse,
    PreferencesResponse,
    SchedulerStatusResponse,
    UnreadCountResponse,
)
from leapconnect.application.settings_store import (
    load_preferences,
    save_abrp_settings,
    save_mqtt_settings,
)
from leapconnect.container import AppContainer
from leapconnect.domain.charging.models import ChargingPriceTier

_LOGGER = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# User preferences
# ---------------------------------------------------------------------------


def _prefs_response(prefs) -> PreferencesResponse:
    return PreferencesResponse(
        electricity_price_kwh=prefs.electricity_price_kwh,
        theme=prefs.theme,
        downsampling_enabled=prefs.downsampling_enabled,
        downsampling_max_points=prefs.downsampling_max_points,
        has_solar_panels=prefs.has_solar_panels,
        home_pricing_mode=prefs.home_pricing_mode,
    )


@router.get("/api/preferences", response_model=PreferencesResponse)
async def get_preferences(repo: RepoDep) -> PreferencesResponse:
    """Get user preferences (electricity price, etc.)."""
    return _prefs_response(await load_preferences(repo))


@router.put("/api/preferences", response_model=PreferencesResponse)
async def update_preferences(request: Request, repo: RepoDep) -> PreferencesResponse:
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
        await repo.save_setting("electricity_price_kwh", str(price))
    theme = body.get("theme")
    if theme is not None:
        if theme not in ("dark", "light"):
            raise HTTPException(
                status_code=422, detail="'theme' must be 'dark' or 'light'"
            )
        await repo.save_setting("theme", theme)
    ds_enabled = body.get("downsampling_enabled")
    if ds_enabled is not None:
        if not isinstance(ds_enabled, bool):
            raise HTTPException(
                status_code=422, detail="'downsampling_enabled' must be a boolean"
            )
        await repo.save_setting("downsampling_enabled", str(ds_enabled).lower())
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
        await repo.save_setting("downsampling_max_points", str(ds_max_points))
    # -- solar panels toggle --
    has_solar = body.get("has_solar_panels")
    if has_solar is not None:
        if not isinstance(has_solar, bool):
            raise HTTPException(
                status_code=422, detail="'has_solar_panels' must be a boolean"
            )
        await repo.save_setting("has_solar_panels", "true" if has_solar else "false")
        # Enable/disable home_solar tier
        tiers = await repo.get_price_tiers()
        solar_tier = next((t for t in tiers if t.id == "home_solar"), None)
        if has_solar:
            if solar_tier:
                solar_tier.enabled = True
                await repo.upsert_price_tier(solar_tier)
            else:
                await repo.upsert_price_tier(
                    ChargingPriceTier(
                        id="home_solar",
                        label="Home (solar)",
                        price_kwh=0.0,
                        enabled=True,
                    )
                )
        elif solar_tier:
            solar_tier.enabled = False
            await repo.upsert_price_tier(solar_tier)
    # -- home pricing mode --
    pricing_mode = body.get("home_pricing_mode")
    if pricing_mode is not None:
        if pricing_mode not in ("flat", "time_of_use"):
            raise HTTPException(
                status_code=422,
                detail="'home_pricing_mode' must be 'flat' or 'time_of_use'",
            )
        await repo.save_setting("home_pricing_mode", pricing_mode)
    return _prefs_response(await load_preferences(repo))


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


@router.get("/api/scheduler", response_model=SchedulerStatusResponse)
async def get_scheduler_status(container: ContainerDep) -> SchedulerStatusResponse:
    """Get current background data collection scheduler status."""
    if not container.scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not available")
    return container.scheduler.status_dict()


@router.put("/api/scheduler", response_model=SchedulerStatusResponse)
async def update_scheduler_settings(
    request: Request, container: ContainerDep
) -> SchedulerStatusResponse:
    """Enable/disable or change the interval of background data collection."""
    if not container.scheduler or not container.repo:
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

    settings = container.scheduler.update_settings(
        enabled=enabled,
        interval_minutes=interval,
        mqtt_interval_seconds=mqtt_interval,
        rate_limit_seconds=rate_limit,
        transition_detection_enabled=transition_enabled,
        transition_poll_interval_seconds=transition_poll,
        transition_min_event_interval_seconds=transition_min_event,
    )

    # Persist to DB
    await container.repo.save_scheduler_settings(settings)

    return container.scheduler.status_dict()


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------


@router.get("/api/system/database-size", response_model=DatabaseSizeResponse)
async def get_database_size() -> DatabaseSizeResponse:
    """Return the current size of the SQLite database file."""
    db_path = config.database_path()
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
# MQTT / Home Assistant
# ---------------------------------------------------------------------------


def _mqtt_status_response(container: AppContainer) -> MqttStatusResponse:
    """Build a MqttStatusResponse from the service's settings + runtime state."""
    s = container.mqtt_service.settings
    return MqttStatusResponse(
        enabled=s.enabled,
        connected=container.mqtt_service.is_connected,
        broker=s.broker,
        port=s.port,
        username=s.username,
        use_tls=s.use_tls,
        discovery_prefix=s.discovery_prefix,
        topic_prefix=s.topic_prefix,
        last_error=container.mqtt_service.last_error,
    )


@router.get("/api/mqtt", response_model=MqttStatusResponse)
async def get_mqtt_status(container: ContainerDep) -> MqttStatusResponse:
    """Get current MQTT / Home Assistant integration status."""
    if not container.mqtt_service:
        return MqttStatusResponse()
    return _mqtt_status_response(container)


@router.put("/api/mqtt", response_model=MqttStatusResponse)
async def update_mqtt_settings(
    request: Request, container: ContainerDep
) -> MqttStatusResponse:
    """Update MQTT connection settings and reconnect."""
    if not container.mqtt_service or not container.repo:
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

    container.mqtt_service.update_settings(
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
    await save_mqtt_settings(container.repo, container.mqtt_service.settings)

    return _mqtt_status_response(container)


@router.post("/api/mqtt/test", response_model=MqttTestResponse)
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
# ABRP (A Better Route Planner)
# ---------------------------------------------------------------------------


@router.get("/api/abrp", response_model=AbrpStatusResponse)
async def get_abrp_status(container: ContainerDep) -> AbrpStatusResponse:
    """Get current ABRP integration status."""
    if not container.abrp_service:
        return AbrpStatusResponse()
    return AbrpStatusResponse(**container.abrp_service.status_dict())


@router.put("/api/abrp", response_model=AbrpStatusResponse)
async def update_abrp_settings(
    request: Request, container: ContainerDep
) -> AbrpStatusResponse:
    """Update ABRP settings."""
    if not container.abrp_service or not container.repo:
        raise HTTPException(status_code=503, detail="ABRP service not available")

    body = await request.json()

    container.abrp_service.update_settings(
        enabled=body.get("enabled"),
        user_token=body.get("user_token"),
    )

    # Ensure vehicles are wired
    if container.abrp_service.settings.enabled and container.vehicles:
        container.abrp_service.set_vehicles(container.vehicles, container.vehicle_cache)

    await save_abrp_settings(container.repo, container.abrp_service.settings)

    return AbrpStatusResponse(**container.abrp_service.status_dict())


# ---------------------------------------------------------------------------
# Account messages
# ---------------------------------------------------------------------------


@router.get("/api/messages", response_model=MessageListResponse)
async def get_messages(
    client: ClientDep, page_no: int = 1, page_size: int = 20
) -> MessageListResponse:
    """Get paginated notification messages from the account."""
    msg_list: MessageList = await client.get_message_list(
        page_no=page_no, page_size=page_size
    )
    return MessageListResponse(
        count=msg_list.count,
        page_no=page_no,
        page_size=page_size,
        messages=[MessageSchema.from_model(m) for m in msg_list.messages],
    )


@router.get("/api/messages/unread-count", response_model=UnreadCountResponse)
async def get_unread_message_count(client: ClientDep) -> UnreadCountResponse:
    """Get the number of unread notification messages."""
    count = await client.get_unread_message_count()
    return UnreadCountResponse(unread=count)


# ---------------------------------------------------------------------------
# Logging — level control & live viewer entries
# ---------------------------------------------------------------------------

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


@router.get("/api/logs/levels")
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


@router.put("/api/logs/levels")
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


@router.get("/api/logs/entries")
async def get_log_entries(container: ContainerDep, limit: int = 200):
    """Return recent log entries from the in-memory buffer."""
    if limit < 1:
        limit = 1
    elif limit > 2000:
        limit = 2000
    return {"entries": container.log_handler.get_entries(limit)}
