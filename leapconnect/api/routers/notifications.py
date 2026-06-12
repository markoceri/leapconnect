"""Notification routes: channels, events, geofences, tracking, Telegram users."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, WebSocket
from starlette.websockets import WebSocketDisconnect

from leapconnect.api.deps import SESSION_COOKIE_NAME, ContainerDep, RepoDep
from leapconnect.api.schemas import (
    GeofenceCreate,
    GeofenceResponse,
    GeofenceUpdate,
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationChannelUpdate,
    NotificationEventStatus,
    NotificationPreferencesUpdate,
    StatusResponse,
    TelegramLinkTokenResponse,
    TelegramUserResponse,
)
from leapconnect.application.notifications import NotificationDispatcher
from leapconnect.container import AppContainer
from leapconnect.domain.notifications.event_catalog import EVENT_CATALOG
from leapconnect.domain.notifications.geofencing import polygon_centroid
from leapconnect.domain.notifications.models import (
    Geofence,
    NotificationChannel,
    NotificationPreference,
)

_LOGGER = logging.getLogger(__name__)

router = APIRouter(tags=["notifications"])


def _channel_response(ch: NotificationChannel) -> NotificationChannelResponse:
    return NotificationChannelResponse(
        id=ch.id,
        channel_type=ch.channel_type,
        config=ch.config,
        enabled=ch.enabled,
        created_at=ch.created_at.isoformat() if ch.created_at else None,
    )


async def _reload_dispatcher(container: AppContainer) -> None:
    if container.notification_dispatcher:
        await container.notification_dispatcher.reload_config()


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------


@router.get("/api/notifications/channels")
async def get_notification_channels(
    request: Request, repo: RepoDep
) -> list[NotificationChannelResponse]:
    """List all configured notification channels."""
    channels = await repo.get_notification_channels()
    return [_channel_response(ch) for ch in channels]


@router.post("/api/notifications/channels")
async def create_notification_channel(
    request: Request,
    body: NotificationChannelCreate,
    repo: RepoDep,
    container: ContainerDep,
) -> NotificationChannelResponse:
    """Create a new notification channel."""
    channel = NotificationChannel(
        channel_type=body.channel_type,
        config=body.config,
        enabled=body.enabled,
    )
    saved = await repo.save_notification_channel(channel)
    await _reload_dispatcher(container)
    return _channel_response(saved)


@router.put("/api/notifications/channels/{channel_id}")
async def update_notification_channel(
    request: Request,
    channel_id: int,
    body: NotificationChannelUpdate,
    repo: RepoDep,
    container: ContainerDep,
) -> NotificationChannelResponse:
    """Update a notification channel."""
    existing = await repo.get_notification_channel(channel_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Channel not found")
    if body.config is not None:
        existing.config = body.config
    if body.enabled is not None:
        existing.enabled = body.enabled
    saved = await repo.save_notification_channel(existing)
    await _reload_dispatcher(container)
    return _channel_response(saved)


@router.delete("/api/notifications/channels/{channel_id}")
async def delete_notification_channel(
    request: Request, channel_id: int, repo: RepoDep, container: ContainerDep
) -> StatusResponse:
    """Delete a notification channel."""
    deleted = await repo.delete_notification_channel(channel_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Channel not found")
    await _reload_dispatcher(container)
    return StatusResponse(status="ok")


@router.post("/api/notifications/channels/{channel_id}/test")
async def test_notification_channel(
    request: Request, channel_id: int, repo: RepoDep
) -> dict:
    """Send a test notification via the specified channel."""
    channel = await repo.get_notification_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    notifier = NotificationDispatcher._create_notifier(channel)
    if not notifier:
        raise HTTPException(status_code=400, detail="Invalid channel configuration")
    success, message = await notifier.test_connection()
    return {"success": success, "message": message}


@router.post("/api/notifications/channels/{channel_id}/test-event")
async def test_notification_event(
    request: Request, channel_id: int, container: ContainerDep
) -> dict:
    """Send a test notification for a specific event type."""
    if not container.notification_dispatcher:
        raise HTTPException(
            status_code=503, detail="Notification dispatcher not available"
        )
    body = await request.json()
    event_type = body.get("event_type")
    if not event_type:
        raise HTTPException(status_code=400, detail="event_type is required")
    vin = body.get("vin", "")
    success, message = await container.notification_dispatcher.send_test_event(
        channel_id, event_type, vin=vin
    )
    return {"success": success, "message": message}


# ---------------------------------------------------------------------------
# Cooldown
# ---------------------------------------------------------------------------


@router.get("/api/notifications/cooldown")
async def get_notification_cooldown(repo: RepoDep) -> dict:
    """Get the notification cooldown duration in seconds."""
    raw = await repo.get_setting("notification_cooldown_seconds")
    return {"cooldown_seconds": int(float(raw)) if raw else 300}


@router.put("/api/notifications/cooldown")
async def update_notification_cooldown(
    request: Request, repo: RepoDep, container: ContainerDep
) -> dict:
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
    await repo.save_setting("notification_cooldown_seconds", str(value))
    await _reload_dispatcher(container)
    return {"cooldown_seconds": value}


# ---------------------------------------------------------------------------
# Location tracking
# ---------------------------------------------------------------------------


@router.post("/api/vehicles/{vin}/tracking")
async def start_tracking(request: Request, vin: str, container: ContainerDep) -> dict:
    """Start periodic location tracking for a vehicle."""
    if not container.notification_dispatcher:
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
    await container.notification_dispatcher.start_tracking(
        vin, interval_seconds=interval
    )
    return {"tracking": True, "vin": vin, "interval_seconds": interval}


@router.delete("/api/vehicles/{vin}/tracking")
async def stop_tracking(request: Request, vin: str, container: ContainerDep) -> dict:
    """Stop location tracking for a vehicle."""
    if not container.notification_dispatcher:
        raise HTTPException(
            status_code=503, detail="Notification dispatcher not available"
        )
    stopped = await container.notification_dispatcher.stop_tracking(vin)
    return {"tracking": False, "vin": vin, "stopped": stopped}


@router.get("/api/vehicles/{vin}/tracking")
async def get_tracking_status(vin: str, container: ContainerDep) -> dict:
    """Get tracking status for a vehicle."""
    if not container.notification_dispatcher:
        return {"tracking": False, "vin": vin}
    info = container.notification_dispatcher.get_tracking_info(vin)
    if info:
        return {"tracking": True, "vin": vin, **info}
    return {"tracking": False, "vin": vin}


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@router.get("/api/notifications/events")
async def get_notification_events(
    request: Request, repo: RepoDep, channel_id: int | None = None
) -> list[NotificationEventStatus]:
    """List all available notification events with their current status."""

    # Get preferences for the specified channel (or first channel)
    prefs_map: dict[str, NotificationPreference] = {}
    if channel_id:
        prefs = await repo.get_notification_preferences(channel_id)
        prefs_map = {p.event_type: p for p in prefs}
    else:
        channels = await repo.get_notification_channels()
        if channels:
            prefs = await repo.get_notification_preferences(channels[0].id)
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


@router.put("/api/notifications/events")
async def update_notification_events(
    request: Request,
    body: NotificationPreferencesUpdate,
    repo: RepoDep,
    container: ContainerDep,
) -> StatusResponse:
    """Bulk update notification preferences for a channel."""
    channel = await repo.get_notification_channel(body.channel_id)
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
    await repo.save_notification_preferences(body.channel_id, prefs)
    await _reload_dispatcher(container)
    return StatusResponse(status="ok")


# ---------------------------------------------------------------------------
# Geofences
# ---------------------------------------------------------------------------


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


@router.get("/api/notifications/geofences")
async def get_geofences(
    request: Request, repo: RepoDep, vin: str | None = None
) -> list[GeofenceResponse]:
    """List geofences, optionally filtered by VIN."""
    geofences = await repo.get_geofences(vin=vin)
    return [_geofence_to_response(gf) for gf in geofences]


@router.post("/api/notifications/geofences")
async def create_geofence(
    request: Request, body: GeofenceCreate, repo: RepoDep, container: ContainerDep
) -> GeofenceResponse:
    """Create a new geofence."""
    latitude, longitude = body.latitude, body.longitude
    points = body.points
    if body.shape_type == "polygon":
        if not points or len(points) < 3:
            raise HTTPException(
                status_code=400, detail="A polygon geofence needs at least 3 points"
            )
        latitude, longitude = polygon_centroid(points)
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
    saved = await repo.save_geofence(gf)
    await _reload_dispatcher(container)
    return _geofence_to_response(saved)


@router.put("/api/notifications/geofences/{geofence_id}")
async def update_geofence(
    request: Request,
    geofence_id: int,
    body: GeofenceUpdate,
    repo: RepoDep,
    container: ContainerDep,
) -> GeofenceResponse:
    """Update a geofence."""
    geofences = await repo.get_geofences()
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
        existing.latitude, existing.longitude = polygon_centroid(existing.points)
    else:
        existing.points = None
        if body.latitude is not None:
            existing.latitude = body.latitude
        if body.longitude is not None:
            existing.longitude = body.longitude
    saved = await repo.save_geofence(existing)
    await _reload_dispatcher(container)
    return _geofence_to_response(saved)


@router.delete("/api/notifications/geofences/{geofence_id}")
async def delete_geofence_endpoint(
    request: Request, geofence_id: int, repo: RepoDep, container: ContainerDep
) -> StatusResponse:
    """Delete a geofence."""
    deleted = await repo.delete_geofence(geofence_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Geofence not found")
    await _reload_dispatcher(container)
    return StatusResponse(status="ok")


# ---------------------------------------------------------------------------
# Log viewer WebSocket
# ---------------------------------------------------------------------------


@router.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket, container: ContainerDep) -> None:
    """Stream live log entries to connected clients via WebSocket."""
    token = websocket.query_params.get(
        "token",
    ) or websocket.cookies.get(SESSION_COOKIE_NAME)
    if not container.sessions.validate(token):
        await websocket.close(code=4401, reason="Unauthorized")
        return

    await websocket.accept()
    container.log_handler.register_ws(websocket)
    _LOGGER.info("Log viewer WebSocket connected")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        container.log_handler.unregister_ws(websocket)
        _LOGGER.info("Log viewer WebSocket disconnected")


# ---------------------------------------------------------------------------
# Telegram users (multi-user access management)
# ---------------------------------------------------------------------------


@router.get("/api/telegram/users")
async def get_telegram_users(
    request: Request, repo: RepoDep, status: str | None = None
) -> list[TelegramUserResponse]:
    """List all Telegram users, optionally filtered by status."""
    users = await repo.get_telegram_users(status=status)
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


@router.put("/api/telegram/users/{chat_id}/approve")
async def approve_telegram_user(
    request: Request, chat_id: str, repo: RepoDep, container: ContainerDep
) -> StatusResponse:
    """Approve a pending Telegram user."""
    updated = await repo.update_telegram_user_status(chat_id, "approved")
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    if container.notification_dispatcher:
        await container.notification_dispatcher.refresh_telegram_users()
        await container.notification_dispatcher.notify_telegram_user_status(
            chat_id, "approved"
        )
    return StatusResponse(status="ok")


@router.put("/api/telegram/users/{chat_id}/reject")
async def reject_telegram_user(
    request: Request, chat_id: str, repo: RepoDep, container: ContainerDep
) -> StatusResponse:
    """Reject a pending Telegram user."""
    updated = await repo.update_telegram_user_status(chat_id, "rejected")
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    if container.notification_dispatcher:
        await container.notification_dispatcher.refresh_telegram_users()
        await container.notification_dispatcher.notify_telegram_user_status(
            chat_id, "rejected"
        )
    return StatusResponse(status="ok")


@router.delete("/api/telegram/users/{chat_id}")
async def delete_telegram_user(
    request: Request, chat_id: str, repo: RepoDep, container: ContainerDep
) -> StatusResponse:
    """Remove a Telegram user entirely."""
    deleted = await repo.delete_telegram_user(chat_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    if container.notification_dispatcher:
        await container.notification_dispatcher.refresh_telegram_users()
    return StatusResponse(status="ok")


@router.post("/api/telegram/link-token")
async def create_telegram_link_token(
    request: Request, repo: RepoDep, container: ContainerDep
) -> TelegramLinkTokenResponse:
    """Generate a deep-link token for Telegram account linking."""
    token = await repo.create_link_token()
    # Get bot username for the link
    bot_username = None
    if container.notification_dispatcher:
        notifier = container.notification_dispatcher.get_telegram_notifier()
        if notifier:
            bot_username = await notifier.get_bot_username()
    if not bot_username:
        raise HTTPException(
            status_code=503,
            detail="Bot username not available. Ensure Telegram bot is configured.",
        )
    expires_at = datetime.now(UTC) + timedelta(minutes=10)
    link = f"https://t.me/{bot_username}?start={token}"
    return TelegramLinkTokenResponse(
        token=token,
        link=link,
        expires_at=expires_at.isoformat(),
    )
