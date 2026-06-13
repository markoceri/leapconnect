"""Notification pipeline (application layer).

- ``dispatcher`` — orchestrator (channels, preferences, cooldowns, dispatch)
- ``policies`` — stateful custom-event detection policies
- ``tracking`` — periodic location tracking mode
- ``telegram_admin`` — Telegram user approve/decline notifications
"""

from leapconnect.application.notifications.dispatcher import NotificationDispatcher

__all__ = ["NotificationDispatcher"]
