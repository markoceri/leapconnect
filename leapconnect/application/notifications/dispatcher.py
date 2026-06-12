"""Notification dispatcher — orchestrates the event-to-notification pipeline.

Receives vehicle events from the transition detection loop, checks user
preferences, runs the custom detection policies (``policies.py``), composes
rich notifications, and dispatches them via the configured notifiers.
Location tracking lives in ``tracking.py``; Telegram user-administration
messages in ``telegram_admin.py``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from leapconnect.application.notifications import telegram_admin
from leapconnect.application.notifications.policies import (
    ChannelView,
    CustomEventPipeline,
    StatusReading,
    charge_transition_suppression,
)
from leapconnect.application.notifications.tracking import LocationTracker
from leapconnect.application.ports.notifier import BaseNotifier, Notification
from leapconnect.domain.notifications.event_catalog import (
    EVENT_CATALOG_MAP,
    IMAGE_ENABLED_BY_DEFAULT_EVENTS,
    MESSAGE_TEMPLATES,
    TRANSITION_EVENTS,
)
from leapconnect.domain.notifications.models import (
    Geofence,
    NotificationChannel,
    NotificationPreference,
)
from leapconnect.domain.telemetry.models import VehicleEvent
from leapconnect.infrastructure.telegram.config import TelegramConfig
from leapconnect.infrastructure.telegram.notifier import TelegramNotifier

if TYPE_CHECKING:
    from collections.abc import Callable

    from leapmotor_api.models import Vehicle, VehicleStatus

    from leapconnect.application.ports.repositories import AppRepository

_LOGGER = logging.getLogger(__name__)


class NotificationDispatcher:
    """Orchestrates the event → notification pipeline."""

    def __init__(
        self,
        repo: AppRepository,
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

        # Custom detection policies (own all per-VIN detection state)
        self._policies = CustomEventPipeline()

        # Per-event cooldowns: (vin, event_type) -> last_notification_time
        self._cooldowns: dict[tuple[str, str], float] = {}
        self._cooldown_seconds: float = 300.0  # 5 min default

        # Location tracking mode
        self._tracker = LocationTracker(
            repo,
            vehicle_cache,
            notifiers=lambda: list(self._notifiers.values()),
            on_start=self._ensure_telegram_polling,
        )

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

    def _channel_view(self) -> ChannelView:
        """Snapshot of the channel configuration for the detection policies."""
        return ChannelView(
            channel_ids=list(self._notifiers),
            get_config=self._get_event_config,
            is_enabled=self._is_event_enabled,
            geofences=self._geofences,
        )

    def _check_cooldown(self, vin: str, event_type: str) -> bool:
        """Returns True if we can send (cooldown expired)."""
        key = (vin, event_type)
        last = self._cooldowns.get(key)
        if last is None:
            return True
        return (time.monotonic() - last) >= self._cooldown_seconds

    def _mark_cooldown(self, vin: str, event_type: str) -> None:
        self._cooldowns[(vin, event_type)] = time.monotonic()

    # -----------------------------------------------------------------------
    # Telegram helpers
    # -----------------------------------------------------------------------

    def _ensure_telegram_polling(self) -> None:
        """Make sure callback polling is active on all Telegram notifiers."""
        for notifier in self._notifiers.values():
            if isinstance(notifier, TelegramNotifier):
                notifier.start_callback_polling(self)

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
        await telegram_admin.notify_user_status(notifier, self._repo, chat_id, status)

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

    # -----------------------------------------------------------------------
    # Dispatch pipeline
    # -----------------------------------------------------------------------

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

        # 1. Direct transition events (with the regen-braking filter for
        #    charge_start/charge_stop — see charge_transition_suppression)
        reading = StatusReading.from_status(status)
        for event in events:
            if event.event_type in TRANSITION_EVENTS:
                reason = charge_transition_suppression(reading, event.event_type)
                if reason:
                    _LOGGER.debug("Suppressing %s — %s", event.event_type, reason)
                    continue
                notifications_to_send.append((event.event_type, {}))

        # 2. Custom detection logic based on current status
        custom_events = self._policies.detect(vin, status, self._channel_view())
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
                send_dynamic_image = self._should_send_dynamic_image(
                    channel_id=channel_id,
                    event_type=event_type,
                    event_config=event_config,
                )

                # Build notification
                notification = await self._build_notification(
                    event_type,
                    vin,
                    vehicle_name,
                    msg_context,
                    send_dynamic_image=send_dynamic_image,
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
        event_config = self._get_event_config(channel_id, event_type) or {}
        send_dynamic_image = self._should_send_dynamic_image(
            channel_id=channel_id,
            event_type=event_type,
            event_config=event_config,
        )
        notification = await self._build_notification(
            event_type,
            use_vin,
            "Test Vehicle",
            context,
            send_dynamic_image=send_dynamic_image,
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
    # Location tracking mode (delegates to LocationTracker)
    # -----------------------------------------------------------------------

    async def start_tracking(
        self, vin: str, interval_seconds: int = 60, base_url: str = ""
    ) -> bool:
        """Start sending periodic location updates for a VIN."""
        return await self._tracker.start(vin, interval_seconds, base_url)

    async def stop_tracking(self, vin: str) -> bool:
        """Stop location tracking for a VIN."""
        return await self._tracker.stop(vin)

    def is_tracking(self, vin: str) -> bool:
        return self._tracker.is_tracking(vin)

    def get_tracking_info(self, vin: str) -> dict | None:
        return self._tracker.info(vin)

    # -----------------------------------------------------------------------
    # Notification composition
    # -----------------------------------------------------------------------

    def _should_send_dynamic_image(
        self,
        channel_id: int,
        event_type: str,
        event_config: dict | None,
    ) -> bool:
        """Resolve whether a dynamic image should be attached for this event."""
        catalog_entry = EVENT_CATALOG_MAP.get(event_type, {})
        if not catalog_entry.get("has_image"):
            return False

        configured = (event_config or {}).get("send_dynamic_image")
        if isinstance(configured, bool):
            return configured

        _ = channel_id  # reserved for future channel-specific defaults
        return event_type in IMAGE_ENABLED_BY_DEFAULT_EVENTS

    async def _build_notification(
        self,
        event_type: str,
        vin: str,
        vehicle_name: str,
        context: dict,
        send_dynamic_image: bool = False,
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
        if (
            send_dynamic_image
            and catalog_entry.get("has_image")
            and self._image_composer
        ):
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
