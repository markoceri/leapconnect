"""Telegram Bot command handler — receives commands via getUpdates and responds.

Provides vehicle status, commands, and system info through Telegram chat commands.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

_LOGGER = logging.getLogger(__name__)

# Commands available to the user
BOT_COMMANDS = [
    {"command": "status", "description": "Vehicle status overview"},
    {"command": "location", "description": "Current vehicle location"},
    {"command": "lock", "description": "Lock the vehicle"},
    {"command": "unlock", "description": "Unlock the vehicle"},
    {"command": "ac_on", "description": "Turn on climate control"},
    {"command": "ac_off", "description": "Turn off climate control"},
    {"command": "trunk_open", "description": "Open the trunk"},
    {"command": "trunk_close", "description": "Close the trunk"},
    {"command": "windows_open", "description": "Open windows"},
    {"command": "windows_close", "description": "Close windows"},
    {"command": "find", "description": "Flash lights & honk to find car"},
    {"command": "charging_start", "description": "Start charging"},
    {"command": "charging_stop", "description": "Stop charging"},
    {"command": "track", "description": "Start location tracking (60s)"},
    {"command": "track_stop", "description": "Stop location tracking"},
    {"command": "mute", "description": "Mute notifications (permanent or N min)"},
    {"command": "unmute", "description": "Unmute notifications"},
    {"command": "notifications", "description": "Notification settings menu"},
    {"command": "commands", "description": "Show all available commands"},
]

# Commands that execute a vehicle action
VEHICLE_COMMANDS = {
    "lock",
    "unlock",
    "trunk_open",
    "trunk_close",
    "windows_open",
    "windows_close",
    "find",
    "charging_start",
    "charging_stop",
    "ac_on",
    "ac_off",
    "defrost",
    "sunroof_open",
    "sunroof_close",
    "sentry_mode_on",
    "sentry_mode_off",
    "steering_wheel_heat_on",
    "steering_wheel_heat_off",
    "battery_preheat",
    "battery_preheat_off",
    "unlock_charger",
}

COMMAND_LABELS = {
    "lock": "🔒 Lock",
    "unlock": "🔓 Unlock",
    "trunk_open": "📦 Open trunk",
    "trunk_close": "📦 Close trunk",
    "windows_open": "🪟 Open windows",
    "windows_close": "🪟 Close windows",
    "find": "🔔 Find vehicle",
    "charging_start": "⚡ Start charging",
    "charging_stop": "⚡ Stop charging",
    "ac_on": "❄️ AC on",
    "ac_off": "❄️ AC off",
    "defrost": "🌬️ Defrost",
    "sunroof_open": "☀️ Open sunroof",
    "sunroof_close": "☀️ Close sunroof",
    "sentry_mode_on": "👁️ Sentry on",
    "sentry_mode_off": "👁️ Sentry off",
    "battery_preheat": "🔥 Battery preheat",
    "battery_preheat_off": "🔥 Preheat off",
    "unlock_charger": "🔌 Unlock charger",
    "steering_wheel_heat_on": "🔥 Steering heat on",
    "steering_wheel_heat_off": "🔥 Steering heat off",
}


class TelegramBotHandler:
    """Handles Telegram bot commands by interfacing with the app layer."""

    def __init__(
        self,
        vehicle_cache,
        command_executor,
        notification_dispatcher=None,
        rights_checker=None,
        pin_checker=None,
        pin_setter=None,
    ):
        """
        Args:
            vehicle_cache: VehicleStatusCache instance for reading state.
            command_executor: async callable(vin, command) -> dict|None
                (raises PermissionError)
            notification_dispatcher: NotificationDispatcher for tracking control.
            rights_checker: callable(vin, command) -> bool for permission filtering.
            pin_checker: callable() -> bool — returns True if PIN is already configured.
            pin_setter: callable(pin: str) -> None — sets the vehicle PIN.
        """
        self._vehicle_cache = vehicle_cache
        self._execute_command = command_executor
        self._dispatcher = notification_dispatcher
        self._rights_checker = rights_checker
        self._pin_checker = pin_checker
        self._pin_setter = pin_setter
        self._pending_pin_command: str | None = None

    def get_vin(self) -> str | None:
        """Get the first known VIN from the cache."""
        if self._vehicle_cache and self._vehicle_cache._cache:
            return next(iter(self._vehicle_cache._cache), None)
        return None

    async def handle_command(self, text: str) -> str:
        """Process a /command and return the response text (HTML)."""
        # Strip bot username from commands like /status@MyBot
        cmd = text.strip().split()[0].lstrip("/").split("@")[0].lower()
        args = text.strip().split()[1:]

        if cmd == "status":
            return await self._cmd_status()
        elif cmd == "location":
            return await self._cmd_location()
        elif cmd == "commands" or cmd == "menu" or cmd == "help" or cmd == "start":
            return self._cmd_menu()
        elif cmd == "track":
            interval = int(args[0]) if args and args[0].isdigit() else 60
            return await self._cmd_track(interval)
        elif cmd == "track_stop":
            return await self._cmd_track_stop()
        elif cmd == "mute":
            minutes = int(args[0]) if args and args[0].isdigit() else 0
            return self._cmd_mute(minutes)
        elif cmd == "unmute":
            return self._cmd_unmute()
        elif cmd == "notifications":
            return self._cmd_notifications()
        elif cmd in VEHICLE_COMMANDS:
            return await self._cmd_vehicle_action(cmd)
        else:
            return (
                f"❓ Unknown command: <code>/{cmd}</code>\n\n"
                "Use /commands to see available commands."
            )

    async def _cmd_status(self) -> str:
        """Build a status overview message."""
        vin = self.get_vin()
        if not vin:
            return "⚠️ No vehicle connected."

        cached = self._vehicle_cache.get_cached(vin)
        if not cached:
            return "⚠️ No cached status available. Waiting for next refresh."

        lines = ["<b>🚗 Vehicle Status</b>", ""]

        # Battery
        if hasattr(cached, "battery") and cached.battery:
            soc = cached.battery.soc
            range_km = cached.battery.expected_mileage
            if soc is not None:
                lines.append(f"🔋 Battery: <b>{soc}%</b>")
            if range_km is not None:
                lines.append(f"📏 Range: <b>{range_km} km</b>")

        # Charging
        is_charging = getattr(cached, "is_charging", None)
        is_plugged = getattr(cached, "is_plugged", None)
        if is_charging:
            lines.append("⚡ <b>Charging</b>")
        elif is_plugged:
            lines.append("🔌 Plugged in (not charging)")

        # Lock
        is_locked = getattr(cached, "is_locked", None)
        if is_locked is not None:
            lines.append(f"{'🔒 Locked' if is_locked else '🔓 <b>Unlocked</b>'}")

        # Climate
        if hasattr(cached, "climate") and cached.climate:
            ac = getattr(cached.climate, "ac_switch", None)
            temp = getattr(cached.climate, "outdoor_temp", None)
            cabin = getattr(cached.climate, "indoor_temp", None)
            if ac:
                lines.append("❄️ AC: <b>ON</b>")
            if temp is not None:
                lines.append(f"🌡️ Outside: {temp}°C")
            if cabin is not None:
                lines.append(f"🏠 Cabin: {cabin}°C")

        # Parked / driving
        is_parked = getattr(cached, "is_parked", None)
        if is_parked is not None:
            lines.append(f"{'🅿️ Parked' if is_parked else '🚗 <b>Driving</b>'}")

        # Odometer
        if hasattr(cached, "driving") and cached.driving:
            odo = getattr(cached.driving, "odometer", None)
            if odo:
                lines.append(f"🛣️ Odometer: {odo:,.0f} km")

        # Doors & Trunk
        if hasattr(cached, "doors") and cached.doors:
            d = cached.doors
            door_names = {
                "lbcm_driver_door_status": "Driver",
                "rbcm_driver_door_status": "Passenger",
                "lbcm_left_rear_door_status": "Rear L",
                "rbcm_right_rear_door_status": "Rear R",
            }
            open_doors = [
                label
                for attr, label in door_names.items()
                if getattr(d, attr, None) is True
            ]
            if open_doors:
                lines.append(f"🚪 Doors open: <b>{', '.join(open_doors)}</b>")
            else:
                lines.append("🚪 Doors: <b>All closed</b>")

            trunk_open = getattr(d, "bbcm_back_door_status", None) is True
            lines.append(f"📦 Trunk: <b>{'Open' if trunk_open else 'Closed'}</b>")

        # Windows
        if hasattr(cached, "windows") and cached.windows:
            w = cached.windows
            win_positions = {
                "left_front_window_percent": "Driver",
                "right_front_window_percent": "Passenger",
                "left_rear_window_percent": "Rear L",
                "right_rear_window_percent": "Rear R",
            }
            open_windows = [
                f"{label} {getattr(w, attr)}%"
                for attr, label in win_positions.items()
                if getattr(w, attr, None) and getattr(w, attr) > 0
            ]
            if open_windows:
                lines.append(f"🪟 Windows: <b>{', '.join(open_windows)}</b>")
            else:
                lines.append("🪟 Windows: <b>All closed</b>")

        # Tires
        if hasattr(cached, "tires") and cached.tires:
            t = cached.tires
            pressures = []
            for attr in [
                "front_left_pressure",
                "front_right_pressure",
                "rear_left_pressure",
                "rear_right_pressure",
            ]:
                p = getattr(t, attr, None)
                if p is not None:
                    pressures.append(f"{p:.1f}")
            if pressures:
                lines.append(f"🛞 Tires: {' / '.join(pressures)} bar")

        lines.append(f"\n<i>Updated: {datetime.now(UTC).strftime('%H:%M:%S UTC')}</i>")
        return "\n".join(lines)

    async def _cmd_location(self) -> str:
        """Return vehicle location."""
        vin = self.get_vin()
        if not vin:
            return "⚠️ No vehicle connected."

        cached = self._vehicle_cache.get_cached(vin)
        if not cached:
            return "⚠️ No cached status available."

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
            return (
                f'📍 <a href="https://www.google.com/maps?q={lat},{lon}">'
                f"View on map</a>\nLat: {lat:.5f} · Lon: {lon:.5f}"
            )
        return "⚠️ Location not available."

    def _cmd_menu(self) -> str:
        """Show available commands filtered by vehicle permissions."""
        vin = self.get_vin()

        def _allowed(cmd: str) -> bool:
            if not vin or not self._rights_checker:
                return True
            return self._rights_checker(vin, cmd)

        lines = ["<b>📋 Available Commands</b>", ""]
        lines.append("<b>ℹ️ Info</b>")
        lines.append("/status — Vehicle status overview")
        lines.append("/location — Current vehicle location")

        security = []
        if _allowed("lock"):
            security.append("/lock — Lock the vehicle")
            security.append("/unlock — Unlock the vehicle")
        if _allowed("find"):
            security.append("/find — Flash lights & honk")
        if security:
            lines.append("")
            lines.append("<b>🔐 Security</b>")
            lines.extend(security)

        climate = []
        if _allowed("ac_on"):
            climate.append("/ac_on — Turn on AC")
            climate.append("/ac_off — Turn off AC")
        if _allowed("defrost"):
            climate.append("/defrost — Windshield defrost")
        if climate:
            lines.append("")
            lines.append("<b>❄️ Climate</b>")
            lines.extend(climate)

        vehicle = []
        if _allowed("trunk_open"):
            vehicle.append("/trunk_open — Open trunk")
            vehicle.append("/trunk_close — Close trunk")
        if _allowed("windows_open"):
            vehicle.append("/windows_open — Open windows")
            vehicle.append("/windows_close — Close windows")
        if _allowed("sunroof_open"):
            vehicle.append("/sunroof_open — Open sunroof")
            vehicle.append("/sunroof_close — Close sunroof")
        if vehicle:
            lines.append("")
            lines.append("<b>🚗 Vehicle</b>")
            lines.extend(vehicle)

        charging = []
        if _allowed("charging_start"):
            charging.append("/charging_start — Start charging")
            charging.append("/charging_stop — Stop charging")
        if _allowed("unlock_charger"):
            charging.append("/unlock_charger — Unlock charge port")
        if charging:
            lines.append("")
            lines.append("<b>⚡ Charging</b>")
            lines.extend(charging)

        lines.append("")
        lines.append("<b>📡 Tracking</b>")
        lines.append("/track — Start location tracking (60s)")
        lines.append("/track <i>N</i> — Track every N seconds")
        lines.append("/track_stop — Stop tracking")

        lines.append("")
        lines.append("<b>🔔 Notifications</b>")
        lines.append("/mute — Mute notifications permanently")
        lines.append("/mute <i>N</i> — Mute for N minutes")
        lines.append("/unmute — Unmute notifications")
        lines.append("/notifications — Notification settings")
        return "\n".join(lines)

    def _cmd_mute(self, minutes: int = 0) -> str:
        """Mute all notifications."""
        if not self._dispatcher:
            return "⚠️ Notification system not available."
        self._dispatcher.mute(minutes)
        if minutes > 0:
            return (
                f"🔇 Notifications muted for <b>{minutes} minutes</b>."
                "\n\nUse /unmute to re-enable."
            )
        return "🔇 Notifications muted <b>permanently</b>.\n\nUse /unmute to re-enable."

    def _cmd_unmute(self) -> str:
        """Unmute notifications."""
        if not self._dispatcher:
            return "⚠️ Notification system not available."
        self._dispatcher.unmute()
        return "🔔 Notifications <b>unmuted</b>."

    def _cmd_notifications(self) -> str:
        """Show notification settings overview with inline instructions."""
        if not self._dispatcher:
            return "⚠️ Notification system not available."

        lines = ["<b>🔔 Notification Settings</b>", ""]

        # Mute status
        if self._dispatcher.is_muted:
            remaining = self._dispatcher.mute_remaining_minutes
            if remaining == 0:
                lines.append("🔇 Status: <b>Muted permanently</b>")
            else:
                lines.append(f"🔇 Status: <b>Muted</b> (~{remaining} min remaining)")
        else:
            lines.append("🔔 Status: <b>Active</b>")

        lines.append("")
        lines.append("<b>Quick actions:</b>")
        lines.append("/mute — Mute permanently")
        lines.append("/mute 30 — Mute for 30 minutes")
        lines.append("/mute 60 — Mute for 1 hour")
        lines.append("/mute 480 — Mute for 8 hours")
        lines.append("/unmute — Re-enable all notifications")
        lines.append("")
        lines.append(
            "<i>To configure individual notifications (enable/disable, "
            "thresholds), use the web interface Settings → Notifications tab.</i>"
        )
        return "\n".join(lines)

    def get_notifications_keyboard(self) -> dict:
        """Build inline keyboard for notification settings."""
        is_muted = self._dispatcher.is_muted if self._dispatcher else False
        rows = []

        if is_muted:
            rows.append([{"text": "🔔 Unmute", "callback_data": "notif:unmute"}])
        else:
            rows.append(
                [
                    {"text": "🔇 Mute permanently", "callback_data": "notif:mute:0"},
                ]
            )
            rows.append(
                [
                    {"text": "🔇 30 min", "callback_data": "notif:mute:30"},
                    {"text": "🔇 1h", "callback_data": "notif:mute:60"},
                    {"text": "🔇 8h", "callback_data": "notif:mute:480"},
                ]
            )

        # Category toggles
        rows.append([{"text": "⚡ Charging", "callback_data": "notif:cat:charging"}])
        rows.append([{"text": "🚗 Driving", "callback_data": "notif:cat:driving"}])
        rows.append([{"text": "🔐 Security", "callback_data": "notif:cat:security"}])
        rows.append(
            [{"text": "🔧 Maintenance", "callback_data": "notif:cat:maintenance"}]
        )

        return {"inline_keyboard": rows}

    def get_category_keyboard(self, category: str) -> tuple[str, dict]:
        """Build inline keyboard for a notification category."""
        from leapconnect.domain.notifications.event_catalog import EVENT_CATALOG

        category_labels = {
            "charging": "⚡ Charging",
            "driving": "🚗 Driving",
            "security": "🔐 Security",
            "maintenance": "🔧 Maintenance",
        }

        events = [e for e in EVENT_CATALOG if e.get("category") == category]
        rows = []

        for ev in events:
            event_type = ev["event_type"]
            label = ev["label"]
            # Check if enabled in any channel
            enabled = self._is_event_enabled_any(event_type)
            icon = "✅" if enabled else "❌"
            rows.append(
                [
                    {
                        "text": f"{icon} {label}",
                        "callback_data": f"notif:toggle:{event_type}",
                    }
                ]
            )

        rows.append([{"text": "⬅️ Back", "callback_data": "notif:back"}])

        title = category_labels.get(category, category.title())
        text = (
            f"<b>🔔 {title} Notifications</b>\n\n"
            "✅ = enabled, ❌ = disabled\nTap to toggle."
        )
        return text, {"inline_keyboard": rows}

    def _is_event_enabled_any(self, event_type: str) -> bool:
        """Check if an event is enabled in any channel."""
        if not self._dispatcher:
            return False
        for channel_id in self._dispatcher._notifiers:
            if self._dispatcher._is_event_enabled(channel_id, event_type):
                return True
        return False

    async def handle_notification_callback(
        self, callback_data: str
    ) -> tuple[str, dict | None]:
        """Handle notification-related callback queries.

        Returns (response_text, reply_markup or None).
        """
        parts = callback_data.split(":")
        action = parts[1] if len(parts) > 1 else ""

        if action == "unmute":
            if self._dispatcher:
                self._dispatcher.unmute()
            return "🔔 Notifications unmuted.", self.get_notifications_keyboard()

        elif action == "mute":
            minutes = int(parts[2]) if len(parts) > 2 else 0
            if self._dispatcher:
                self._dispatcher.mute(minutes)
            if minutes > 0:
                text = f"🔇 Muted for {minutes} minutes."
            else:
                text = "🔇 Muted permanently."
            return text, self.get_notifications_keyboard()

        elif action == "cat":
            category = parts[2] if len(parts) > 2 else ""
            text, keyboard = self.get_category_keyboard(category)
            return text, keyboard

        elif action == "toggle":
            event_type = parts[2] if len(parts) > 2 else ""
            toggled = await self._toggle_event(event_type)
            # Find the category to rebuild the keyboard
            from leapconnect.domain.notifications.event_catalog import EVENT_CATALOG_MAP

            ev = EVENT_CATALOG_MAP.get(event_type, {})
            category = ev.get("category", "")
            if category:
                text, keyboard = self.get_category_keyboard(category)
                return text, keyboard
            return toggled, None

        elif action == "back":
            return self._cmd_notifications(), self.get_notifications_keyboard()

        return "⚠️ Unknown action.", None

    async def _toggle_event(self, event_type: str) -> str:
        """Toggle a notification event on/off for all channels."""
        if not self._dispatcher:
            return "⚠️ Not available."

        from leapconnect.domain.notifications.models import NotificationPreference

        # Toggle in all channels
        for channel_id in self._dispatcher._notifiers:
            prefs = self._dispatcher._preferences.get(channel_id, {})
            pref = prefs.get(event_type)
            if pref:
                pref.enabled = not pref.enabled
            else:
                # Create new preference (enabled)
                new_pref = NotificationPreference(
                    channel_id=channel_id,
                    event_type=event_type,
                    enabled=True,
                )
                prefs[event_type] = new_pref
                self._dispatcher._preferences[channel_id] = prefs

            # Persist all preferences for this channel
            try:
                all_prefs = list(prefs.values())
                await self._dispatcher._repo.save_notification_preferences(
                    channel_id, all_prefs
                )
            except Exception:
                pass

        from leapconnect.domain.notifications.event_catalog import EVENT_CATALOG_MAP

        label = EVENT_CATALOG_MAP.get(event_type, {}).get("label", event_type)
        enabled = self._is_event_enabled_any(event_type)
        icon = "✅" if enabled else "❌"
        return f"{icon} {label} — {'enabled' if enabled else 'disabled'}"

    async def _cmd_vehicle_action(self, command: str) -> str:
        """Execute a vehicle command — always asks for PIN first."""
        vin = self.get_vin()
        if not vin:
            return "⚠️ No vehicle connected."

        # Always require PIN for vehicle commands via Telegram
        self._pending_pin_command = command
        label = COMMAND_LABELS.get(command, command)
        return f"🔑 {label} — enter your vehicle PIN (the message will be deleted):"

    @property
    def awaiting_pin(self) -> bool:
        """True if the bot is waiting for a PIN input."""
        return self._pending_pin_command is not None

    async def handle_pin_input(self, pin: str) -> str:
        """Process a PIN sent by the user, set it temporarily, execute, then clear."""
        command = self._pending_pin_command
        self._pending_pin_command = None

        if not command:
            return ""

        pin = pin.strip()
        if not pin:
            return "⚠️ Empty PIN. Command cancelled."

        # Set the PIN temporarily
        if self._pin_setter:
            self._pin_setter(pin)

        # Execute the pending command
        label = COMMAND_LABELS.get(command, command)
        vin = self.get_vin()
        if not vin:
            return "⚠️ No vehicle connected."

        try:
            result = await self._execute_command(vin, command)
            if result is None:
                return f"⚠️ Command <code>{command}</code> not supported."
            return f"✅ {label} — command sent"
        except PermissionError:
            return f"🚫 {label} — not available for this vehicle (missing permission)"
        except Exception as exc:
            _LOGGER.warning("Telegram command %s failed after PIN: %s", command, exc)
            return f"❌ {label} failed: {exc}"
        finally:
            # Clear PIN immediately — never persist from Telegram
            if self._pin_setter:
                self._pin_setter("")

    async def _cmd_track(self, interval: int = 60) -> str:
        """Start location tracking."""
        vin = self.get_vin()
        if not vin:
            return "⚠️ No vehicle connected."
        if not self._dispatcher:
            return "⚠️ Tracking not available."

        interval = max(10, min(3600, interval))
        await self._dispatcher.start_tracking(vin, interval_seconds=interval)
        return (
            f"📡 Tracking started — updates every {interval}s\n\n"
            "Use /track_stop to stop."
        )

    async def _cmd_track_stop(self) -> str:
        """Stop location tracking."""
        vin = self.get_vin()
        if not vin:
            return "⚠️ No vehicle connected."
        if not self._dispatcher:
            return "⚠️ Tracking not available."

        stopped = await self._dispatcher.stop_tracking(vin)
        if stopped:
            return "✅ Tracking stopped."
        return "ℹ️ Tracking was not active."
