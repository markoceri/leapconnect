"""Telegram notifier implementation using the Bot API via httpx."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import UTC, datetime
from io import BytesIO

import httpx

from models import TelegramUser
from services.telegram_bot import BOT_COMMANDS, TelegramBotHandler
from services.telegram_config import TelegramConfig

from . import BaseNotifier, Notification

_LOGGER = logging.getLogger(__name__)


class TelegramNotifier(BaseNotifier):
    """Sends notifications via Telegram Bot API."""

    def __init__(self, config: TelegramConfig) -> None:
        self._config = config
        self._bot_token = config.bot_token
        self._chat_id = config.chat_id
        self._base_url = config.base_url
        self._callback_handler: asyncio.Task | None = None
        self._callback_listeners: dict[
            str, object
        ] = {}  # callback_data_prefix -> dispatcher ref
        self._last_update_id: int = 0
        self._bot_handler: TelegramBotHandler | None = None
        # Multi-user auth: set of approved chat IDs
        self._approved_chat_ids: set[str] = set()
        # Per-user bot handlers (keyed by chat_id)
        self._bot_handlers: dict[str, TelegramBotHandler] = {}
        self._repository = None  # Set via set_repository()
        self._bot_username: str | None = None  # Resolved via getMe

    def set_repository(self, repository) -> None:
        """Set the persistence repository for telegram user management."""
        self._repository = repository

    async def refresh_approved_ids(self) -> None:
        """Reload approved chat IDs from the database."""
        if not self._repository:
            self._approved_chat_ids = set()
            return
        self._approved_chat_ids = await self._repository.get_approved_chat_ids()

    async def get_bot_username(self) -> str | None:
        """Get the bot username via getMe API (cached)."""
        if self._bot_username:
            return self._bot_username
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self._base_url}/getMe")
                if resp.status_code == 200:
                    data = resp.json()
                    self._bot_username = data.get("result", {}).get("username")
                    return self._bot_username
        except Exception as exc:
            _LOGGER.debug("getMe error: %s", exc)
        return None

    async def send(self, notification: Notification) -> bool:
        """Send a text message with HTML formatting."""
        text = self._format_message(notification)
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        # Add inline keyboard if provided
        if notification.extra.get("reply_markup"):
            payload["reply_markup"] = notification.extra["reply_markup"]
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(f"{self._base_url}/sendMessage", json=payload)
                if resp.status_code == 200:
                    return True
                _LOGGER.warning(
                    "Telegram sendMessage failed: %d %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return False
        except Exception as exc:
            _LOGGER.error("Telegram send error: %s", exc)
            return False

    async def send_photo(self, notification: Notification) -> bool:
        """Send a photo with caption."""
        if not notification.image:
            return await self.send(notification)

        caption = self._format_message(notification)
        # Telegram caption limit is 1024 chars
        if len(caption) > 1024:
            caption = caption[:1020] + "..."

        files = {
            "photo": ("vehicle.png", BytesIO(notification.image), "image/png"),
        }
        data = {
            "chat_id": self._chat_id,
            "caption": caption,
            "parse_mode": "HTML",
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._base_url}/sendPhoto", data=data, files=files
                )
                if resp.status_code == 200:
                    return True
                _LOGGER.warning(
                    "Telegram sendPhoto failed: %d %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return False
        except Exception as exc:
            _LOGGER.error("Telegram send_photo error: %s", exc)
            return False

    async def test_connection(self) -> tuple[bool, str]:
        """Send a test message to verify bot configuration."""
        payload = {
            "chat_id": self._chat_id,
            "text": (
                "✅ <b>LeapConnect</b> — Notifications active!\n\n"
                "Connection configured successfully."
            ),
            "parse_mode": "HTML",
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(f"{self._base_url}/sendMessage", json=payload)
                if resp.status_code == 200:
                    return True, "Test message sent successfully"
                data = (
                    resp.json()
                    if resp.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                    else {}
                )
                description = data.get("description", resp.text[:100])
                return False, f"Telegram error: {description}"
        except httpx.TimeoutException:
            return False, "Connection timeout to Telegram"
        except Exception as exc:
            return False, f"Error: {exc}"

    @staticmethod
    def _format_message(notification: Notification) -> str:
        """Build an HTML-formatted Telegram message."""
        parts = []
        parts.append(f"<b>{notification.title}</b>")
        if notification.body:
            parts.append(notification.body)
        return "\n".join(parts)

    async def send_location(
        self,
        lat: float,
        lon: float,
        caption: str = "",
        reply_markup: dict | None = None,
    ) -> bool:
        """Send a native Telegram location message with optional inline keyboard."""
        payload: dict = {
            "chat_id": self._chat_id,
            "latitude": lat,
            "longitude": lon,
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(f"{self._base_url}/sendLocation", json=payload)
                if resp.status_code == 200:
                    return True
                _LOGGER.warning(
                    "Telegram sendLocation failed: %d %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return False
        except Exception as exc:
            _LOGGER.error("Telegram send_location error: %s", exc)
            return False

    async def answer_callback_query(
        self, callback_query_id: str, text: str = ""
    ) -> None:
        """Acknowledge a callback query."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{self._base_url}/answerCallbackQuery",
                    json={
                        "callback_query_id": callback_query_id,
                        "text": text,
                    },
                )
        except Exception as exc:
            _LOGGER.debug("answer_callback_query error: %s", exc)

    def start_callback_polling(self, dispatcher) -> None:
        """Start a background task polling for Telegram updates."""
        if self._callback_handler and not self._callback_handler.done():
            return
        self._callback_listeners["stop_tracking:"] = dispatcher
        # Store dispatcher reference for creating per-user bot handlers
        self._dispatcher = dispatcher
        # Set up bot command handler only if bot is enabled
        if self._config.bot_enabled:
            vehicle_cache = getattr(dispatcher, "_vehicle_cache", None)
            command_executor = getattr(dispatcher, "_command_executor", None)
            rights_checker = getattr(dispatcher, "_rights_checker", None)
            pin_checker = getattr(dispatcher, "_pin_checker", None)
            pin_setter = getattr(dispatcher, "_pin_setter", None)
            self._bot_handler = TelegramBotHandler(
                vehicle_cache=vehicle_cache,
                command_executor=command_executor,
                notification_dispatcher=dispatcher,
                rights_checker=rights_checker,
                pin_checker=pin_checker,
                pin_setter=pin_setter,
            )
        self._callback_handler = asyncio.create_task(self._poll_updates(dispatcher))

    def stop_callback_polling(self) -> None:
        """Stop the callback polling task."""
        if self._callback_handler and not self._callback_handler.done():
            self._callback_handler.cancel()
            self._callback_handler = None

    async def _poll_updates(self, dispatcher) -> None:
        """Long-poll Telegram for all relevant updates (callbacks + bot commands)."""
        _LOGGER.info("Telegram update polling started")
        await self._set_bot_commands()
        await self.refresh_approved_ids()
        await self.get_bot_username()
        try:
            while True:
                try:
                    async with httpx.AsyncClient(timeout=35) as client:
                        params = {
                            "timeout": 30,
                            "allowed_updates": json.dumps(
                                ["callback_query", "message"]
                            ),
                        }
                        if self._last_update_id:
                            params["offset"] = self._last_update_id + 1
                        resp = await client.get(
                            f"{self._base_url}/getUpdates", params=params
                        )
                        if resp.status_code != 200:
                            await asyncio.sleep(5)
                            continue
                        data = resp.json()
                        for update in data.get("result", []):
                            self._last_update_id = update["update_id"]

                            # Handle callback queries (inline buttons)
                            cq = update.get("callback_query")
                            if cq:
                                cq_chat_id = str(
                                    cq.get("message", {}).get("chat", {}).get("id", "")
                                )
                                if cq_chat_id in self._approved_chat_ids:
                                    await self._handle_callback_query(
                                        client, cq, dispatcher
                                    )
                                continue

                            # Handle text messages (bot commands)
                            msg = update.get("message")
                            if msg and msg.get("text"):
                                chat_id = str(msg.get("chat", {}).get("id", ""))
                                if chat_id in self._approved_chat_ids:
                                    # Update user profile info on each message
                                    await self._update_user_info(msg)
                                    text = msg["text"]
                                    if text.startswith("/"):
                                        await self._handle_bot_command(
                                            client, msg, chat_id
                                        )
                                    elif (
                                        self._bot_handler
                                        and self._bot_handler.awaiting_pin
                                    ):
                                        await self._handle_pin_message(
                                            client, msg, chat_id
                                        )
                                else:
                                    # Unapproved user — handle /start or reject
                                    await self._handle_new_user(client, msg)

                except httpx.TimeoutException:
                    continue
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    _LOGGER.warning("Update poll error: %s", exc)
                    await asyncio.sleep(5)
        except asyncio.CancelledError:
            _LOGGER.info("Telegram update polling stopped")
        except Exception as exc:
            _LOGGER.error("Update polling fatal: %s", exc)

    async def _handle_callback_query(self, client, cq, dispatcher) -> None:
        """Process an inline keyboard callback."""
        cb_data = cq.get("data", "")
        chat_id = str(cq.get("message", {}).get("chat", {}).get("id", ""))
        if cb_data.startswith("stop_tracking:"):
            vin = cb_data.split(":", 1)[1]
            stopped = await dispatcher.stop_tracking(vin)
            ack_text = "✅ Tracking stopped" if stopped else "⚠️ Tracking was not active"
            await self.answer_callback_query(cq["id"], ack_text)
            if cq.get("message"):
                with contextlib.suppress(Exception):
                    await client.post(
                        f"{self._base_url}/editMessageReplyMarkup",
                        json={
                            "chat_id": cq["message"]["chat"]["id"],
                            "message_id": cq["message"]["message_id"],
                            "reply_markup": {"inline_keyboard": []},
                        },
                    )
        elif cb_data.startswith("notif:"):
            # Notification settings callbacks
            if self._bot_handler:
                text, keyboard = await self._bot_handler.handle_notification_callback(
                    cb_data
                )
                await self.answer_callback_query(cq["id"])
                msg = cq.get("message")
                if msg and keyboard:
                    # Edit existing message with new text and keyboard
                    with contextlib.suppress(Exception):
                        await client.post(
                            f"{self._base_url}/editMessageText",
                            json={
                                "chat_id": msg["chat"]["id"],
                                "message_id": msg["message_id"],
                                "text": text,
                                "parse_mode": "HTML",
                                "reply_markup": keyboard,
                            },
                        )
                elif text:
                    await client.post(
                        f"{self._base_url}/sendMessage",
                        json={
                            "chat_id": chat_id or self._chat_id,
                            "text": text,
                            "parse_mode": "HTML",
                        },
                    )
            else:
                await self.answer_callback_query(cq["id"], "⚠️ Bot not active")
        elif cb_data.startswith("cmd:"):
            command = cb_data.split(":", 1)[1]
            if self._bot_handler:
                response = await self._bot_handler.handle_command(f"/{command}")
                await client.post(
                    f"{self._base_url}/sendMessage",
                    json={
                        "chat_id": chat_id or self._chat_id,
                        "text": response,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )
            await self.answer_callback_query(cq["id"])
        elif cb_data.startswith("tguser:"):
            # Approve/reject user from Telegram inline button
            await self._handle_user_action_callback(client, cq, cb_data)
        else:
            await self.answer_callback_query(cq["id"], "⚠️ Unknown action")

    async def _handle_bot_command(self, client, msg, chat_id: str) -> None:
        """Process a bot command message."""
        if not self._bot_handler:
            return
        text = msg.get("text", "")
        response = await self._bot_handler.handle_command(text)
        if not response:
            return
        # For /location, send native location pin
        cmd = text.strip().split()[0].split("@")[0].lstrip("/")
        if cmd == "location":
            import re

            match = re.search(r"Lat: ([\d.-]+) · Lon: ([\d.-]+)", response)
            if match:
                lat, lon = float(match.group(1)), float(match.group(2))
                await client.post(
                    f"{self._base_url}/sendLocation",
                    json={
                        "chat_id": chat_id,
                        "latitude": lat,
                        "longitude": lon,
                    },
                )
                return

        # For /status, attach the dynamic car image by default (if available).
        if cmd == "status":
            vin = self._bot_handler.get_vin()
            image_composer = getattr(
                getattr(self, "_dispatcher", None), "_image_composer", None
            )
            if vin and image_composer:
                try:
                    image = await image_composer(vin)
                    if image:
                        caption = (
                            response[:1020] + "..."
                            if len(response) > 1024
                            else response
                        )
                        files = {
                            "photo": ("vehicle.png", BytesIO(image), "image/png"),
                        }
                        data = {
                            "chat_id": chat_id,
                            "caption": caption,
                            "parse_mode": "HTML",
                        }
                        photo_resp = await client.post(
                            f"{self._base_url}/sendPhoto", data=data, files=files
                        )
                        if photo_resp.status_code == 200:
                            return
                except Exception as exc:
                    _LOGGER.debug("Failed to send /status photo: %s", exc)

        # For /notifications, include inline keyboard
        payload = {
            "chat_id": chat_id,
            "text": response,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if cmd == "notifications":
            keyboard = self._bot_handler.get_notifications_keyboard()
            payload["reply_markup"] = json.dumps(keyboard)

        await client.post(f"{self._base_url}/sendMessage", json=payload)

    async def _handle_pin_message(self, client, msg, chat_id: str) -> None:
        """Process a PIN input message: delete it, set PIN, execute pending command."""
        message_id = msg["message_id"]
        pin_text = msg.get("text", "").strip()

        # Delete the message containing the PIN immediately
        with contextlib.suppress(Exception):
            await client.post(
                f"{self._base_url}/deleteMessage",
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                },
            )

        # Process the PIN and execute the pending command
        response = await self._bot_handler.handle_pin_input(pin_text)
        if response:
            await client.post(
                f"{self._base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": response,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )

    async def _handle_new_user(self, client, msg) -> None:
        """Handle a message from an unapproved user (deep-link or plain /start)."""
        chat_id = str(msg.get("chat", {}).get("id", ""))
        text = msg.get("text", "").strip()
        chat = msg.get("chat", {})
        username = chat.get("username")
        first_name = chat.get("first_name")
        last_name = chat.get("last_name")
        # Also check from field for user details
        from_user = msg.get("from", {})
        username = username or from_user.get("username")
        first_name = first_name or from_user.get("first_name")
        last_name = last_name or from_user.get("last_name")

        if not self._repository:
            return  # Silent — system not ready

        # Handle /start with deep-link token (must be checked FIRST)
        if text.startswith("/start "):
            token = text[7:].strip()
            if token:
                valid = await self._repository.validate_link_token(token)
                if valid:
                    # Auto-approve user
                    user = TelegramUser(
                        chat_id=chat_id,
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        status="approved",
                        linked_token=token,
                        created_at=datetime.now(UTC),
                        approved_at=datetime.now(UTC),
                    )
                    await self._repository.save_telegram_user(user)
                    self._approved_chat_ids.add(chat_id)
                    await self._send_text(
                        client,
                        chat_id,
                        "✅ <b>Account linked successfully!</b>\n\n"
                        "You can now use all bot commands.\n"
                        "Type /commands to see what's available.",
                    )
                    _LOGGER.info(
                        "Telegram user auto-approved via deep link: %s (@%s)",
                        chat_id,
                        username or "no-username",
                    )
                    # Notify all existing admins about the new user
                    await self._notify_admins_user_joined(client, user)
                    return
                # Invalid/expired token — stay silent
                return

        # For any other message: bot is completely silent for unapproved users
        # But save new users as pending (only on first /start)
        existing = await self._repository.get_telegram_user_by_chat_id(chat_id)
        if existing:
            # Already known (pending or rejected) — stay silent
            return

        # New user: save as pending, notify admin, stay silent to user
        if not text.startswith("/start"):
            # Only register on /start, ignore random messages
            return

        user = TelegramUser(
            chat_id=chat_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            status="pending",
            created_at=datetime.now(UTC),
        )
        await self._repository.save_telegram_user(user)
        _LOGGER.info(
            "New Telegram user pending approval: %s (@%s)",
            chat_id,
            username or "no-username",
        )
        # Notify admin with approve/reject buttons
        await self._notify_admin_new_request(client, user)

    async def _notify_admin_new_request(self, client, user: TelegramUser) -> None:
        """Notify admin about a new pending access request with inline buttons."""
        display = user.username and f"@{user.username}" or ""
        name_parts = [p for p in [user.first_name, user.last_name] if p]
        name = " ".join(name_parts) if name_parts else "Unknown"
        text = (
            "🔔 <b>New Telegram access request</b>\n\n"
            f"👤 {name}"
            + (f" ({display})" if display else "")
            + f"\n🆔 Chat ID: <code>{user.chat_id}</code>"
        )
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Approve",
                        "callback_data": f"tguser:approve:{user.chat_id}",
                    },
                    {
                        "text": "❌ Reject",
                        "callback_data": f"tguser:reject:{user.chat_id}",
                    },
                ]
            ]
        }
        for admin_chat_id in self._approved_chat_ids:
            with contextlib.suppress(Exception):
                await client.post(
                    f"{self._base_url}/sendMessage",
                    json={
                        "chat_id": admin_chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "reply_markup": json.dumps(keyboard),
                    },
                )

    async def _notify_admins_user_joined(self, client, user: TelegramUser) -> None:
        """Notify all approved users that a new user joined via deep link."""
        display = user.username and f"@{user.username}" or ""
        name_parts = [p for p in [user.first_name, user.last_name] if p]
        name = " ".join(name_parts) if name_parts else "Unknown"
        text = (
            "🔗 <b>New user joined via link</b>\n\n"
            f"👤 {name}"
            + (f" ({display})" if display else "")
            + f"\n🆔 Chat ID: <code>{user.chat_id}</code>\n"
            "✅ Auto-approved"
        )
        for admin_chat_id in self._approved_chat_ids:
            if admin_chat_id == user.chat_id:
                continue  # Don't notify the user themselves
            with contextlib.suppress(Exception):
                await client.post(
                    f"{self._base_url}/sendMessage",
                    json={
                        "chat_id": admin_chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                    },
                )

    async def _update_user_info(self, msg) -> None:
        """Update an approved user's profile info from their latest message."""
        if not self._repository:
            return
        chat_id = str(msg.get("chat", {}).get("id", ""))
        from_user = msg.get("from", {})
        username = from_user.get("username")
        first_name = from_user.get("first_name")
        last_name = from_user.get("last_name")
        if not username and not first_name:
            return
        existing = await self._repository.get_telegram_user_by_chat_id(chat_id)
        if not existing or existing.status != "approved":
            return
        # Update only if info changed
        changed = False
        if username and existing.username != username:
            existing.username = username
            changed = True
        if first_name and existing.first_name != first_name:
            existing.first_name = first_name
            changed = True
        if last_name is not None and existing.last_name != last_name:
            existing.last_name = last_name
            changed = True
        if changed:
            await self._repository.save_telegram_user(existing)

    async def _handle_user_action_callback(self, client, cq, cb_data: str) -> None:
        """Handle approve/reject inline button for a pending user."""
        parts = cb_data.split(":")
        if len(parts) != 3:
            await self.answer_callback_query(cq["id"], "⚠️ Invalid action")
            return
        action = parts[1]  # approve or reject
        target_chat_id = parts[2]

        if not self._repository:
            await self.answer_callback_query(cq["id"], "⚠️ System not ready")
            return

        if action == "approve":
            updated = await self._repository.update_telegram_user_status(
                target_chat_id, "approved"
            )
            if updated:
                self._approved_chat_ids.add(target_chat_id)
                await self.answer_callback_query(cq["id"], "✅ User approved")
                # Notify the approved user
                await self._notify_user_status_change(
                    client, target_chat_id, "approved"
                )
            else:
                await self.answer_callback_query(cq["id"], "⚠️ User not found")
        elif action == "reject":
            updated = await self._repository.update_telegram_user_status(
                target_chat_id, "rejected"
            )
            if updated:
                self._approved_chat_ids.discard(target_chat_id)
                await self.answer_callback_query(cq["id"], "❌ User rejected")
                await self._notify_user_status_change(
                    client, target_chat_id, "rejected"
                )
            else:
                await self.answer_callback_query(cq["id"], "⚠️ User not found")
        else:
            await self.answer_callback_query(cq["id"], "⚠️ Unknown action")
            return

        # Update the admin message to remove buttons
        msg = cq.get("message")
        if msg:
            status_text = "✅ Approved" if action == "approve" else "❌ Rejected"
            original_text = msg.get("text", "")
            new_text = f"{original_text}\n\n<b>→ {status_text}</b>"
            with contextlib.suppress(Exception):
                await client.post(
                    f"{self._base_url}/editMessageText",
                    json={
                        "chat_id": msg["chat"]["id"],
                        "message_id": msg["message_id"],
                        "text": new_text,
                        "parse_mode": "HTML",
                        "reply_markup": {"inline_keyboard": []},
                    },
                )

    async def _notify_user_status_change(
        self, client, chat_id: str, status: str
    ) -> None:
        """Notify a user that their access request status changed."""
        if status == "approved":
            text = (
                "✅ <b>Access approved!</b>\n\n"
                "You can now use all bot commands.\n"
                "Type /commands to see what's available."
            )
        else:
            text = "🚫 Your access request has been declined."
        await self._send_text(client, chat_id, text)

    async def _send_text(self, client, chat_id: str, text: str) -> None:
        """Send a simple text message to a chat."""
        with contextlib.suppress(Exception):
            await client.post(
                f"{self._base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                },
            )

    async def _set_bot_commands(self) -> None:
        """Register or clear bot commands with Telegram (shows in menu)."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                if self._config.bot_enabled:
                    await client.post(
                        f"{self._base_url}/setMyCommands",
                        json={
                            "commands": BOT_COMMANDS,
                        },
                    )
                    _LOGGER.info("Telegram bot commands menu registered")
                else:
                    await client.post(f"{self._base_url}/deleteMyCommands")
                    _LOGGER.info("Telegram bot commands menu cleared (bot disabled)")
        except Exception as exc:
            _LOGGER.debug("Failed to set bot commands: %s", exc)
