"""Telegram user-administration notifications (approve/decline flow)."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from leapconnect.application.ports.repositories import AppRepository
    from leapconnect.infrastructure.telegram.notifier import TelegramNotifier

_LOGGER = logging.getLogger(__name__)


async def notify_user_status(
    notifier: TelegramNotifier,
    repo: AppRepository,
    chat_id: str,
    status: str,
) -> None:
    """Send a status notification to a Telegram user and admins."""
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
    user = await repo.get_telegram_user_by_chat_id(chat_id)
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
