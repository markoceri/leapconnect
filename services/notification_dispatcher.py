"""Notification dispatcher — orchestrates event-to-notification pipeline.

Receives vehicle events from the transition detection loop, checks user
preferences, applies custom logic (geofencing, thresholds, timeouts),
composes rich notifications, and dispatches them via configured notifiers.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from models import Geofence, NotificationChannel, NotificationPreference, VehicleEvent
from services.notifiers import BaseNotifier, Notification
from services.notifiers.telegram import TelegramNotifier
from services.telegram_config import TelegramConfig

if TYPE_CHECKING:
    from leapmotor_api.models import Vehicle, VehicleStatus

    from persistence.sqlite_adapter import SQLAlchemyVehicleHistoryRepository

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event catalog — defines all available notification events
# ---------------------------------------------------------------------------

EVENT_CATALOG: list[dict] = [
    # Charging
    {
        "event_type": "charge_start",
        "label": "Charging started",
        "description": "Notify when the vehicle starts charging",
        "category": "charging",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "charge_stop",
        "label": "Charging stopped",
        "description": "Notify when charging ends",
        "category": "charging",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "charge_interrupted",
        "label": "Charging interrupted",
        "description": "Notify if charging stops before reaching the SOC target",
        "category": "charging",
        "has_image": True,
        "configurable": True,
        "config_schema": {
            "soc_target": {
                "label": "Target SOC",
                "type": "number",
                "default": 80,
                "min": 20,
                "max": 100,
                "unit": "%",
            }
        },
    },
    {
        "event_type": "soc_threshold_high",
        "label": "SOC above threshold",
        "description": "Notify when the SOC rises above the configured threshold",
        "category": "charging",
        "has_image": True,
        "configurable": True,
        "config_schema": {
            "threshold": {
                "label": "SOC threshold",
                "type": "number",
                "default": 80,
                "min": 10,
                "max": 100,
                "unit": "%",
            }
        },
    },
    {
        "event_type": "soc_threshold_low",
        "label": "SOC below threshold",
        "description": "Notify when the SOC drops below the configured threshold",
        "category": "charging",
        "has_image": True,
        "configurable": True,
        "config_schema": {
            "threshold": {
                "label": "SOC threshold",
                "type": "number",
                "default": 20,
                "min": 5,
                "max": 90,
                "unit": "%",
            }
        },
    },
    {
        "event_type": "plugged_in",
        "label": "Plugged in",
        "description": "Notify when the charging cable is connected",
        "category": "charging",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "unplugged",
        "label": "Unplugged",
        "description": "Notify when the charging cable is disconnected",
        "category": "charging",
        "has_image": True,
        "configurable": False,
    },
    # Driving
    {
        "event_type": "driving_start",
        "label": "Driving started",
        "description": "Notify when the vehicle starts moving",
        "category": "driving",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "parked",
        "label": "Vehicle parked",
        "description": "Notify when the vehicle is parked",
        "category": "driving",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "ignition_on",
        "label": "Ignition on",
        "description": "Notify when the vehicle is turned on",
        "category": "driving",
        "has_image": False,
        "configurable": False,
    },
    {
        "event_type": "ignition_off",
        "label": "Ignition off",
        "description": "Notify when the vehicle is turned off",
        "category": "driving",
        "has_image": False,
        "configurable": False,
    },
    # Security
    {
        "event_type": "locked",
        "label": "Vehicle locked",
        "description": "Notify when the vehicle is locked",
        "category": "security",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "unlocked",
        "label": "Vehicle unlocked",
        "description": "Notify when the vehicle is unlocked",
        "category": "security",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "movement_alert",
        "label": "Movement alert",
        "description": "Notify if the vehicle moves while parked and off (anti-theft)",
        "category": "security",
        "has_image": True,
        "configurable": True,
        "config_schema": {
            "distance_m": {
                "label": "Distance threshold",
                "type": "number",
                "default": 50,
                "min": 10,
                "max": 1000,
                "unit": "m",
            },
            "tracking_interval": {
                "label": "Auto-track interval (0=off)",
                "type": "number",
                "default": 0,
                "min": 0,
                "max": 300,
                "unit": "s",
            },
        },
    },
    {
        "event_type": "geofence_enter",
        "label": "Geofence enter",
        "description": "Notify when the vehicle enters a configured zone",
        "category": "security",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "geofence_exit",
        "label": "Geofence exit",
        "description": "Notify when the vehicle exits a configured zone",
        "category": "security",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "unlocked_timeout",
        "label": "Unlocked too long",
        "description": "Notify if the vehicle stays unlocked for too long while parked",
        "category": "security",
        "has_image": True,
        "configurable": True,
        "config_schema": {
            "timeout_minutes": {
                "label": "Timeout",
                "type": "number",
                "default": 30,
                "min": 5,
                "max": 240,
                "unit": "min",
            }
        },
    },
    # Maintenance
    {
        "event_type": "tire_pressure_alert",
        "label": "Tire pressure alert",
        "description": "Notify when tire pressure is outside the configured range",
        "category": "maintenance",
        "has_image": False,
        "configurable": True,
        "config_schema": {
            "min_bar": {
                "label": "Minimum pressure",
                "type": "number",
                "default": 2.2,
                "min": 1.5,
                "max": 3.0,
                "unit": "bar",
            },
            "max_bar": {
                "label": "Maximum pressure",
                "type": "number",
                "default": 3.0,
                "min": 2.5,
                "max": 4.0,
                "unit": "bar",
            },
        },
    },
    {
        "event_type": "range_low",
        "label": "Low range",
        "description": "Notify when estimated range drops below the threshold",
        "category": "maintenance",
        "has_image": True,
        "configurable": True,
        "config_schema": {
            "threshold_km": {
                "label": "Range threshold",
                "type": "number",
                "default": 50,
                "min": 10,
                "max": 200,
                "unit": "km",
            }
        },
    },
]

# Lookup map
EVENT_CATALOG_MAP: dict[str, dict] = {e["event_type"]: e for e in EVENT_CATALOG}

# Events that come directly from TransitionDetector
TRANSITION_EVENTS = {
    "charge_start",
    "charge_stop",
    "plugged_in",
    "unplugged",
    "locked",
    "unlocked",
    "driving_start",
    "parked",
    "ignition_on",
    "ignition_off",
}

# ---------------------------------------------------------------------------
# Message templates
# ---------------------------------------------------------------------------

MESSAGE_TEMPLATES: dict[str, dict[str, str]] = {
    "charge_start": {
        "title": "🔌 Charging started",
        "body": "SOC: {soc}% — Range: {range} km",
    },
    "charge_stop": {
        "title": "✅ Charging complete",
        "body": "SOC: {soc}% — Range: {range} km",
    },
    "charge_interrupted": {
        "title": "⚠️ Charging interrupted",
        "body": "SOC: {soc}% (target: {soc_target}%) — Range: {range} km",
    },
    "soc_threshold_high": {
        "title": "🔋 SOC above threshold",
        "body": "SOC: {soc}% (threshold: {threshold}%) — Range: {range} km",
    },
    "soc_threshold_low": {
        "title": "🪫 SOC below threshold",
        "body": "SOC: {soc}% (threshold: {threshold}%) — Range: {range} km",
    },
    "plugged_in": {
        "title": "🔌 Plugged in",
        "body": "SOC: {soc}% — Range: {range} km",
    },
    "unplugged": {
        "title": "🔌 Unplugged",
        "body": "SOC: {soc}% — Range: {range} km",
    },
    "driving_start": {
        "title": "🚗 Driving",
        "body": "SOC: {soc}% — Range: {range} km",
    },
    "parked": {
        "title": "🅿️ Parked",
        "body": "SOC: {soc}% — Range: {range} km",
    },
    "ignition_on": {
        "title": "🔑 Ignition on",
        "body": "SOC: {soc}% — Range: {range} km",
    },
    "ignition_off": {
        "title": "🔑 Ignition off",
        "body": "SOC: {soc}% — Range: {range} km",
    },
    "locked": {
        "title": "🔒 Locked",
        "body": "",
    },
    "unlocked": {
        "title": "🔓 Unlocked",
        "body": "",
    },
    "movement_alert": {
        "title": "🚨 Movement alert!",
        "body": (
            "Vehicle moved {distance}m while parked and off!\n\n"
            '📍 <a href="https://www.google.com/maps?q={lat},{lon}">'
            "View on map</a>"
        ),
    },
    "geofence_enter": {
        "title": "📍 Entered zone",
        "body": 'Vehicle entered zone "{zone_name}"',
    },
    "geofence_exit": {
        "title": "📍 Left zone",
        "body": 'Vehicle left zone "{zone_name}"',
    },
    "unlocked_timeout": {
        "title": "⚠️ Unlocked too long",
        "body": "Vehicle has been unlocked for {minutes} minutes",
    },
    "tire_pressure_alert": {
        "title": "⚠️ Tire pressure alert",
        "body": "{details}",
    },
    "range_low": {
        "title": "🪫 Low range",
        "body": "Estimated range: {range} km (threshold: {threshold_km} km)",
    },
}


# ---------------------------------------------------------------------------
# Haversine utility
# ---------------------------------------------------------------------------


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two GPS coordinates."""
    R = 6_371_000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class NotificationDispatcher:
    """Orchestrates the event → notification pipeline."""

    def __init__(
        self,
        repo: SQLAlchemyVehicleHistoryRepository,
        image_composer: Callable | None = None,
        vehicle_cache: object | None = None,
        command_executor: Callable | None = None,
        rights_checker: Callable | None = None,
        pin_checker: Callable | None = None,
        pin_setter: Callable | None = None,
    ) -> None:
        self._repo = repo
        self._image_composer = image_composer  # async fn(vin) -> bytes | None
        self._vehicle_cache = vehicle_cache  # VehicleStatusCache instance
        self._command_executor = command_executor  # async fn(vin, command) -> dict|None
        self._rights_checker = rights_checker  # fn(vin, command) -> bool
        self._pin_checker = pin_checker  # fn() -> bool
        self._pin_setter = pin_setter  # fn(pin) -> None
        self._notifiers: dict[int, BaseNotifier] = {}  # channel_id -> notifier
        self._preferences: dict[
            int, dict[str, NotificationPreference]
        ] = {}  # channel_id -> {event_type: pref}
        self._geofences: list[Geofence] = []

        # Custom detection state
        # vin -> {lat, lon} last known parked position
        self._parked_positions: dict[str, tuple[float, float]] = {}
        # vin -> timestamp when unlocked was detected (while parked)
        self._unlock_times: dict[str, float] = {}
        # vin -> last SOC value (for threshold crossings)
        self._last_soc: dict[str, int] = {}
        # vin -> set of geofence IDs the vehicle is currently inside
        self._inside_geofences: dict[str, set[int]] = {}
        # Per-event cooldowns: (vin, event_type) -> last_notification_time
        self._cooldowns: dict[tuple[str, str], float] = {}
        self._cooldown_seconds: float = 300.0  # 5 min default

        # Tracking mode: vin -> {interval_seconds, task, last_sent, base_url}
        self._tracking: dict[str, dict] = {}

        # Mute state: None = not muted, 0 = permanently muted, timestamp = muted until
        self._muted_until: float | None = None

    async def reload_config(self) -> None:
        """Reload channels, preferences, and geofences from the database."""
        # Stop existing Telegram polling before recreating notifiers
        for notifier in self._notifiers.values():
            if isinstance(notifier, TelegramNotifier):
                notifier.stop_callback_polling()

        channels = await self._repo.get_notification_channels()
        self._notifiers.clear()
        self._preferences.clear()

        for ch in channels:
            if not ch.enabled or not ch.id:
                continue
            notifier = self._create_notifier(ch)
            if notifier:
                self._notifiers[ch.id] = notifier
                # Load preferences for this channel
                prefs = await self._repo.get_notification_preferences(ch.id)
                self._preferences[ch.id] = {p.event_type: p for p in prefs}

        self._geofences = await self._repo.get_geofences()

        # Load cooldown setting
        raw = await self._repo.get_setting("notification_cooldown_seconds")
        if raw:
            with contextlib.suppress(TypeError, ValueError):
                self._cooldown_seconds = max(0, float(raw))

        _LOGGER.info(
            "NotificationDispatcher reloaded: %d channels, %d geofences, cooldown=%ds",
            len(self._notifiers),
            len(self._geofences),
            int(self._cooldown_seconds),
        )

        # Start Telegram callback polling for inline keyboard buttons
        for notifier in self._notifiers.values():
            if isinstance(notifier, TelegramNotifier):
                notifier.set_repository(self._repo)
                notifier.start_callback_polling(self)

    @staticmethod
    def _create_notifier(channel: NotificationChannel) -> BaseNotifier | None:
        """Factory: create a notifier instance from channel config."""
        if channel.channel_type == "telegram":
            token = channel.config.get("bot_token", "")
            chat_id = channel.config.get("chat_id", "")
            if token and chat_id:
                bot_enabled = channel.config.get("bot_enabled", True)
                config = TelegramConfig(
                    bot_token=token,
                    chat_id=chat_id,
                    bot_enabled=bot_enabled,
                )
                return TelegramNotifier(config=config)
            _LOGGER.warning(
                "Telegram channel %d: missing bot_token or chat_id", channel.id
            )
            return None
        _LOGGER.warning("Unknown channel type: %s", channel.channel_type)
        return None

    def _is_event_enabled(self, channel_id: int, event_type: str) -> bool:
        """Check if an event type is enabled for a given channel."""
        prefs = self._preferences.get(channel_id, {})
        pref = prefs.get(event_type)
        if pref is None:
            return False  # Not configured = not enabled
        return pref.enabled

    def _get_event_config(self, channel_id: int, event_type: str) -> dict | None:
        """Get event-specific configuration for a channel."""
        prefs = self._preferences.get(channel_id, {})
        pref = prefs.get(event_type)
        if pref:
            return pref.config
        return None

    def _check_cooldown(self, vin: str, event_type: str) -> bool:
        """Returns True if we can send (cooldown expired)."""
        key = (vin, event_type)
        last = self._cooldowns.get(key)
        if last is None:
            return True
        return (time.monotonic() - last) >= self._cooldown_seconds

    def _mark_cooldown(self, vin: str, event_type: str) -> None:
        self._cooldowns[(vin, event_type)] = time.monotonic()

    async def refresh_telegram_users(self) -> None:
        """Refresh approved chat IDs on all Telegram notifiers."""
        for notifier in self._notifiers.values():
            if isinstance(notifier, TelegramNotifier):
                await notifier.refresh_approved_ids()

    def get_telegram_notifier(self) -> TelegramNotifier | None:
        """Return the first active Telegram notifier (for bot username etc.)."""
        for notifier in self._notifiers.values():
            if isinstance(notifier, TelegramNotifier):
                return notifier
        return None

    async def notify_telegram_user_status(self, chat_id: str, status: str) -> None:
        """Send a status notification to a Telegram user and admins."""
        notifier = self.get_telegram_notifier()
        if not notifier:
            return
        import httpx

        if status == "approved":
            user_text = (
                "✅ <b>Access approved!</b>\n\n"
                "You can now use all bot commands.\n"
                "Type /commands to see what's available."
            )
        else:
            user_text = "🚫 Your access request has been declined."

        # Build admin notification
        user = await self._repo.get_telegram_user_by_chat_id(chat_id)
        if user:
            name_parts = [p for p in [user.first_name, user.last_name] if p]
            name = " ".join(name_parts) if name_parts else "Unknown"
            display = f"@{user.username}" if user.username else ""
            status_emoji = "✅" if status == "approved" else "❌"
            admin_text = (
                f"{status_emoji} <b>User {status}</b>\n\n"
                f"👤 {name}"
                + (f" ({display})" if display else "")
                + f"\n🆔 Chat ID: <code>{chat_id}</code>"
            )
        else:
            admin_text = None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Notify the target user
                await client.post(
                    f"{notifier._base_url}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": user_text,
                        "parse_mode": "HTML",
                    },
                )
                # Notify all admins (approved users)
                if admin_text:
                    for admin_id in notifier._approved_chat_ids:
                        if admin_id == chat_id:
                            continue  # Don't duplicate to the user themselves
                        with contextlib.suppress(Exception):
                            await client.post(
                                f"{notifier._base_url}/sendMessage",
                                json={
                                    "chat_id": admin_id,
                                    "text": admin_text,
                                    "parse_mode": "HTML",
                                },
                            )
        except Exception as exc:
            _LOGGER.debug("Failed to notify user %s: %s", chat_id, exc)

    # -----------------------------------------------------------------------
    # Mute / unmute
    # -----------------------------------------------------------------------

    def mute(self, minutes: int = 0) -> None:
        """Mute all notifications. minutes=0 means permanent."""
        if minutes <= 0:
            self._muted_until = 0.0  # permanent
        else:
            self._muted_until = time.monotonic() + minutes * 60

    def unmute(self) -> None:
        """Unmute notifications."""
        self._muted_until = None

    @property
    def is_muted(self) -> bool:
        """True if notifications are currently muted."""
        if self._muted_until is None:
            return False
        if self._muted_until == 0.0:
            return True  # permanent
        if time.monotonic() < self._muted_until:
            return True
        # Expired
        self._muted_until = None
        return False

    @property
    def mute_remaining_minutes(self) -> int | None:
        """Minutes remaining on timed mute. None if not muted, 0 if permanent."""
        if self._muted_until is None:
            return None
        if self._muted_until == 0.0:
            return 0
        remaining = (self._muted_until - time.monotonic()) / 60
        if remaining <= 0:
            self._muted_until = None
            return None
        return int(remaining) + 1

    async def dispatch(
        self,
        events: list[VehicleEvent],
        status: VehicleStatus,
        vehicle: Vehicle,
    ) -> None:
        """Process events and status, dispatch notifications."""
        if not self._notifiers:
            return

        # Skip all notifications if muted
        if self.is_muted:
            return

        vin = vehicle.vin
        vehicle_name = vehicle.vehicle_nickname or vehicle.car_type or vin

        # Collect all notification-worthy event types
        notifications_to_send: list[tuple[str, dict]] = []

        # 1. Direct transition events
        # --- Robust regen-braking filter for charge_start/charge_stop ---
        # Do NOT rely solely on VehicleStatus.is_plugged because its fallback
        # path (when ac_input_slow_charge is None) incorrectly returns True for
        # regenerative braking while the vehicle is momentarily stopped (speed=0).
        # Instead check the actual gun-insert sensors and the explicit is_regening
        # flag to distinguish real plug-in charging from regenerative braking.
        is_regening = getattr(status, "is_regening", None)
        battery = getattr(status, "battery", None)
        gun_inserted: bool | None = None  # None = data unavailable
        if battery:
            fast_gun = getattr(battery, "is_charge_fast_gun_insert", None)
            slow_gun = getattr(battery, "is_charge_slow_gun_insert", None)
            if fast_gun is not None or slow_gun is not None:
                gun_inserted = (fast_gun is True) or (slow_gun is True)

        for event in events:
            if event.event_type in TRANSITION_EVENTS:
                if event.event_type in ("charge_start", "charge_stop"):
                    # Suppress if regenerative braking (explicit regen flag)
                    if is_regening:
                        _LOGGER.debug(
                            "Suppressing %s — is_regening=True (regen braking)",
                            event.event_type,
                        )
                        continue
                    # Suppress if gun sensor data is available and no gun is inserted
                    if gun_inserted is not None and not gun_inserted:
                        _LOGGER.debug(
                            "Suppressing %s — no gun inserted (regen or driving)",
                            event.event_type,
                        )
                        continue
                    # When gun sensor data is unavailable, fall back to the
                    # is_plugged property as a best-effort heuristic
                    if gun_inserted is None:
                        is_plugged = getattr(status, "is_plugged", None)
                        if not is_plugged:
                            _LOGGER.debug(
                                "Suppressing %s — is_plugged=False"
                                " (gun data unavailable)",
                                event.event_type,
                            )
                            continue
                notifications_to_send.append((event.event_type, {}))

        # 2. Custom detection logic based on current status
        custom_events = self._detect_custom_events(vin, status)
        notifications_to_send.extend(custom_events)

        # Persist custom-detected events to history
        for event_type, extra in custom_events:
            try:
                await self._repo.save_event(
                    VehicleEvent(
                        vin=vin,
                        timestamp=datetime.now(UTC),
                        event_type=event_type,
                        field_name=event_type,
                        old_value=None,
                        new_value=extra.get("zone_name")
                        or extra.get("details")
                        or extra.get("threshold_km")
                        or None,
                    )
                )
            except Exception as exc:
                _LOGGER.debug("Failed to persist custom event %s: %s", event_type, exc)

        if not notifications_to_send:
            return

        # Build status context for message formatting
        soc = status.battery.soc if status.battery else None
        range_km = status.battery.expected_mileage if status.battery else None
        context = {
            "soc": soc if soc is not None else "?",
            "range": range_km if range_km is not None else "?",
            "vehicle_name": vehicle_name,
        }

        # Dispatch each event to each channel (if enabled)
        for event_type, extra_context in notifications_to_send:
            for channel_id, notifier in self._notifiers.items():
                if not self._is_event_enabled(channel_id, event_type):
                    continue
                # Use zone-specific cooldown key for geofence events
                cooldown_key = event_type
                if (
                    event_type in ("geofence_enter", "geofence_exit")
                    and "zone_name" in extra_context
                ):
                    cooldown_key = f"{event_type}:{extra_context['zone_name']}"
                if not self._check_cooldown(vin, cooldown_key):
                    continue

                # Merge event config into context
                event_config = self._get_event_config(channel_id, event_type) or {}
                msg_context = {**context, **extra_context, **event_config}

                # Build notification
                notification = await self._build_notification(
                    event_type, vin, vehicle_name, msg_context
                )
                if not notification:
                    continue

                # Send (with or without image)
                asyncio.create_task(
                    self._send_notification(
                        notifier, notification, event_type, vin, cooldown_key
                    )
                )

                # Auto-start tracking on movement_alert if configured
                if event_type == "movement_alert" and not self.is_tracking(vin):
                    tracking_interval = event_config.get("tracking_interval", 0)
                    if tracking_interval and tracking_interval > 0:
                        await self.start_tracking(
                            vin, interval_seconds=int(tracking_interval)
                        )

    async def _send_notification(
        self,
        notifier: BaseNotifier,
        notification: Notification,
        event_type: str,
        vin: str,
        cooldown_key: str | None = None,
    ) -> None:
        """Send a notification and mark cooldown on success."""
        try:
            if notification.image:
                ok = await notifier.send_photo(notification)
            else:
                ok = await notifier.send(notification)
            if ok:
                self._mark_cooldown(vin, cooldown_key or event_type)
                _LOGGER.info("Notification sent: [%s] %s", vin, event_type)
            else:
                _LOGGER.warning("Notification failed: [%s] %s", vin, event_type)
        except Exception as exc:
            _LOGGER.error("Notification error [%s] %s: %s", vin, event_type, exc)

    async def send_test_event(
        self, channel_id: int, event_type: str, vin: str = ""
    ) -> tuple[bool, str]:
        """Send a test notification for a specific event type.

        Bypasses cooldown/preferences.
        """
        notifier = self._notifiers.get(channel_id)
        if not notifier:
            # Try to build from DB
            channel = await self._repo.get_notification_channel(channel_id)
            if not channel:
                return False, "Channel not found"
            notifier = self._create_notifier(channel)
            if not notifier:
                return False, "Invalid channel configuration"

        catalog_entry = EVENT_CATALOG_MAP.get(event_type)
        if not catalog_entry:
            return False, f"Unknown event type: {event_type}"

        # Build mock context for the template
        context: dict[str, str | int | float] = {
            "soc": 72,
            "range": 245,
            "vehicle_name": "Test Vehicle",
            "distance": 120,
            "zone_name": "Home",
            "minutes": 35,
            "details": "FL: 2.1 bar (low)",
            "threshold": 80,
            "soc_target": 80,
            "threshold_km": 50,
        }

        # Use real VIN for image composition, fallback to "TEST"
        use_vin = vin or "TEST"
        notification = await self._build_notification(
            event_type, use_vin, "Test Vehicle", context
        )
        if not notification:
            return False, "Failed to build notification"

        try:
            if notification.image:
                ok = await notifier.send_photo(notification)
            else:
                ok = await notifier.send(notification)
            return ok, "Test notification sent" if ok else "Failed to send"
        except Exception as exc:
            return False, str(exc)

    # -----------------------------------------------------------------------
    # Location tracking mode
    # -----------------------------------------------------------------------

    async def start_tracking(
        self, vin: str, interval_seconds: int = 60, base_url: str = ""
    ) -> bool:
        """Start sending periodic location updates for a VIN."""
        if vin in self._tracking:
            # Already tracking — update interval
            self._tracking[vin]["interval_seconds"] = interval_seconds
            return True
        self._tracking[vin] = {
            "interval_seconds": interval_seconds,
            "task": asyncio.create_task(self._tracking_loop(vin)),
        }
        # Ensure Telegram callback polling is active for stop buttons
        for notifier in self._notifiers.values():
            if isinstance(notifier, TelegramNotifier):
                notifier.start_callback_polling(self)
        _LOGGER.info("Tracking started for %s (every %ds)", vin, interval_seconds)
        # Persist tracking_start event
        with contextlib.suppress(Exception):
            await self._repo.save_event(
                VehicleEvent(
                    vin=vin,
                    timestamp=datetime.now(UTC),
                    event_type="tracking_start",
                    field_name="tracking",
                    old_value=None,
                    new_value=f"{interval_seconds}s",
                )
            )
        return True

    async def stop_tracking(self, vin: str) -> bool:
        """Stop location tracking for a VIN."""
        info = self._tracking.pop(vin, None)
        if info and info.get("task"):
            info["task"].cancel()
            _LOGGER.info("Tracking stopped for %s", vin)
            # Persist tracking_stop event
            with contextlib.suppress(Exception):
                await self._repo.save_event(
                    VehicleEvent(
                        vin=vin,
                        timestamp=datetime.now(UTC),
                        event_type="tracking_stop",
                        field_name="tracking",
                        old_value=None,
                        new_value=None,
                    )
                )
            return True
        return False

    def is_tracking(self, vin: str) -> bool:
        return vin in self._tracking

    def get_tracking_info(self, vin: str) -> dict | None:
        info = self._tracking.get(vin)
        if info:
            return {"interval_seconds": info["interval_seconds"]}
        return None

    async def _tracking_loop(self, vin: str) -> None:
        """Periodic loop that sends location notifications via Telegram sendLocation."""
        try:
            while vin in self._tracking:
                info = self._tracking.get(vin)
                if not info:
                    break
                interval = info["interval_seconds"]

                # Get latest cached position from the vehicle cache
                lat = lon = None
                if self._vehicle_cache:
                    cached = self._vehicle_cache.get_cached(vin)
                    if cached:
                        lat = getattr(cached, "latitude", None) or (
                            cached.vehicle.latitude
                            if hasattr(cached, "vehicle") and cached.vehicle
                            else None
                        )
                        lon = getattr(cached, "longitude", None) or (
                            cached.vehicle.longitude
                            if hasattr(cached, "vehicle") and cached.vehicle
                            else None
                        )
                        if not lat and hasattr(cached, "location") and cached.location:
                            lat = cached.location.latitude
                            lon = cached.location.longitude

                if lat and lon:
                    # Build inline keyboard with Stop button (callback_data, not URL)
                    reply_markup = {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "⏹ Stop tracking",
                                    "callback_data": f"stop_tracking:{vin}",
                                },
                            ]
                        ]
                    }

                    # Use native sendLocation for map preview
                    for notifier in self._notifiers.values():
                        if isinstance(notifier, TelegramNotifier):
                            try:
                                await notifier.send_location(
                                    lat,
                                    lon,
                                    reply_markup=reply_markup,
                                )
                            except Exception as exc:
                                _LOGGER.warning("Tracking send error: %s", exc)
                        else:
                            # Fallback for non-Telegram notifiers
                            maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                            body = (
                                f'📍 <a href="{maps_url}">View on map</a>'
                                f"\nLat: {lat:.5f} · Lon: {lon:.5f}"
                            )
                            notification = Notification(
                                event_type="tracking",
                                title="📡 Location update",
                                body=body,
                                vin=vin,
                                timestamp=datetime.now(UTC),
                            )
                            try:
                                await notifier.send(notification)
                            except Exception as exc:
                                _LOGGER.warning("Tracking send error: %s", exc)

                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            _LOGGER.error("Tracking loop error for %s: %s", vin, exc)
        finally:
            self._tracking.pop(vin, None)

    async def _build_notification(
        self, event_type: str, vin: str, vehicle_name: str, context: dict
    ) -> Notification | None:
        """Compose a Notification object from template + context."""
        template = MESSAGE_TEMPLATES.get(event_type)
        if not template:
            _LOGGER.warning("No message template for event: %s", event_type)
            return None

        title = f"{template['title']} — {vehicle_name}"
        try:
            body = template["body"].format(**context) if template["body"] else ""
        except KeyError as e:
            _LOGGER.warning("Template format error for %s: missing %s", event_type, e)
            body = ""

        # Get image if this event type supports it
        image: bytes | None = None
        catalog_entry = EVENT_CATALOG_MAP.get(event_type, {})
        if catalog_entry.get("has_image") and self._image_composer:
            try:
                image = await self._image_composer(vin)
            except Exception as exc:
                _LOGGER.warning("Image composition failed for %s: %s", vin, exc)

        return Notification(
            event_type=event_type,
            title=title,
            body=body,
            vin=vin,
            vehicle_name=vehicle_name,
            image=image,
            timestamp=datetime.now(UTC),
        )

    # -----------------------------------------------------------------------
    # Custom event detection (runs each poll cycle)
    # -----------------------------------------------------------------------

    def _detect_custom_events(
        self, vin: str, status: VehicleStatus
    ) -> list[tuple[str, dict]]:
        """Detect events that require stateful logic beyond simple transitions."""
        results: list[tuple[str, dict]] = []

        lat = getattr(status, "latitude", None) or (
            status.vehicle.latitude
            if hasattr(status, "vehicle") and status.vehicle
            else None
        )
        lon = getattr(status, "longitude", None) or (
            status.vehicle.longitude
            if hasattr(status, "vehicle") and status.vehicle
            else None
        )
        # Fallback: check location sub-object
        if not lat and hasattr(status, "location") and status.location:
            lat = status.location.latitude
            lon = status.location.longitude
        soc = status.battery.soc if status.battery else None
        is_parked = status.is_parked if hasattr(status, "is_parked") else None
        is_locked = status.is_locked if hasattr(status, "is_locked") else None
        is_charging = status.is_charging if hasattr(status, "is_charging") else None
        ignition_on = (
            status.ignition.bcm_key_position_on3
            if hasattr(status, "ignition") and status.ignition
            else None
        )
        range_km = status.battery.expected_mileage if status.battery else None

        # --- Movement alert (anti-theft) ---
        if is_parked and not ignition_on and lat and lon:
            parked_pos = self._parked_positions.get(vin)
            if parked_pos:
                distance = haversine_distance_m(parked_pos[0], parked_pos[1], lat, lon)
                if distance > 50:  # default 50m threshold
                    results.append(
                        (
                            "movement_alert",
                            {"distance": f"{distance:.0f}", "lat": lat, "lon": lon},
                        )
                    )
                    # Update position to avoid repeated alerts
                    self._parked_positions[vin] = (lat, lon)
            else:
                self._parked_positions[vin] = (lat, lon)
        elif not is_parked:
            # Vehicle is moving — clear parked position
            self._parked_positions.pop(vin, None)

        # --- Unlocked timeout ---
        if is_parked and not is_locked:
            if vin not in self._unlock_times:
                self._unlock_times[vin] = time.monotonic()
            else:
                elapsed_min = (time.monotonic() - self._unlock_times[vin]) / 60
                if elapsed_min >= 30:  # default 30 min
                    results.append(
                        ("unlocked_timeout", {"minutes": f"{elapsed_min:.0f}"})
                    )
                    # Reset to avoid repeated alerts every cycle
                    self._unlock_times[vin] = time.monotonic()
        else:
            self._unlock_times.pop(vin, None)

        # --- SOC thresholds ---
        if soc is not None:
            prev_soc = self._last_soc.get(vin)
            if prev_soc is not None:
                # High threshold (crossing upward)
                for channel_id in self._notifiers:
                    cfg = self._get_event_config(channel_id, "soc_threshold_high")
                    threshold = (cfg or {}).get("threshold", 80)
                    if prev_soc < threshold <= soc:
                        results.append(
                            ("soc_threshold_high", {"threshold": str(threshold)})
                        )
                        break
                # Low threshold (crossing downward)
                for channel_id in self._notifiers:
                    cfg = self._get_event_config(channel_id, "soc_threshold_low")
                    threshold = (cfg or {}).get("threshold", 20)
                    if prev_soc >= threshold > soc:
                        results.append(
                            ("soc_threshold_low", {"threshold": str(threshold)})
                        )
                        break
            self._last_soc[vin] = soc

        # --- Charge interrupted ---
        if is_charging is False and soc is not None:
            prev_soc = self._last_soc.get(vin)
            # Only if we were previously tracking charging
            # This will be caught by charge_stop + soc below target
            for channel_id in self._notifiers:
                cfg = self._get_event_config(channel_id, "charge_interrupted")
                soc_target = (cfg or {}).get("soc_target", 80)
                if soc < soc_target and self._is_event_enabled(
                    channel_id, "charge_interrupted"
                ):
                    # Check if charge_stop just happened (will be in the events list)
                    results.append(
                        ("charge_interrupted", {"soc_target": str(soc_target)})
                    )
                    break

        # --- Range low ---
        if range_km is not None:
            for channel_id in self._notifiers:
                cfg = self._get_event_config(channel_id, "range_low")
                threshold_km = (cfg or {}).get("threshold_km", 50)
                if range_km < threshold_km:
                    results.append(("range_low", {"threshold_km": str(threshold_km)}))
                    break

        # --- Tire pressure ---
        if status.tires:
            pressures = {
                "FL": getattr(status.tires, "front_left_pressure", None),
                "FR": getattr(status.tires, "front_right_pressure", None),
                "RL": getattr(status.tires, "rear_left_pressure", None),
                "RR": getattr(status.tires, "rear_right_pressure", None),
            }
            for channel_id in self._notifiers:
                cfg = self._get_event_config(channel_id, "tire_pressure_alert")
                min_bar = (cfg or {}).get("min_bar", 2.2)
                max_bar = (cfg or {}).get("max_bar", 3.0)
                alerts = []
                for pos, val in pressures.items():
                    if val is not None and (val < min_bar or val > max_bar):
                        alerts.append(f"{pos}: {val:.1f} bar")
                if alerts:
                    results.append(
                        ("tire_pressure_alert", {"details": ", ".join(alerts)})
                    )
                    break

        # --- Geofence enter/exit ---
        if lat and lon:
            current_inside: set[int] = set()
            for gf in self._geofences:
                if not gf.enabled or not gf.id:
                    continue
                if gf.vin and gf.vin != vin:
                    continue
                dist = haversine_distance_m(gf.latitude, gf.longitude, lat, lon)
                if dist <= gf.radius_m:
                    current_inside.add(gf.id)

            prev_inside = self._inside_geofences.get(vin, set())

            # Entered zones
            for gf_id in current_inside - prev_inside:
                gf = next((g for g in self._geofences if g.id == gf_id), None)
                if gf and gf.notify_on_enter:
                    results.append(("geofence_enter", {"zone_name": gf.name}))

            # Exited zones
            for gf_id in prev_inside - current_inside:
                gf = next((g for g in self._geofences if g.id == gf_id), None)
                if gf and gf.notify_on_exit:
                    results.append(("geofence_exit", {"zone_name": gf.name}))

            self._inside_geofences[vin] = current_inside

        return results
