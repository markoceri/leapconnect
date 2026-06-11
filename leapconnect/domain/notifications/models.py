"""Notification entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class NotificationChannel:
    """A configured notification channel (e.g. Telegram bot)."""

    id: int | None = None
    channel_type: str = "telegram"  # "telegram", "email", "webhook", ...
    config: dict = None  # type: ignore[assignment]
    enabled: bool = True
    created_at: datetime | None = None

    def __post_init__(self):
        if self.config is None:
            self.config = {}


@dataclass
class NotificationPreference:
    """Per-event notification preference for a channel."""

    id: int | None = None
    channel_id: int = 0
    event_type: str = ""
    enabled: bool = True
    config: dict | None = None  # thresholds, timeouts, etc.


@dataclass
class Geofence:
    """A geographic zone for enter/exit notifications."""

    id: int | None = None
    vin: str | None = None  # None = applies to all vehicles
    name: str = ""
    shape_type: str = "circle"  # "circle" | "polygon"
    latitude: float = 0.0  # circle center, or polygon centroid
    longitude: float = 0.0
    radius_m: float = 200.0  # used only when shape_type == "circle"
    points: list[list[float]] | None = None  # [[lat, lon], ...] for polygons
    notify_on_enter: bool = True
    notify_on_exit: bool = True
    enabled: bool = True


@dataclass
class TelegramUser:
    """A Telegram user that has interacted with the bot."""

    id: int | None = None
    chat_id: str = ""
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    status: str = "pending"  # pending, approved, rejected
    linked_token: str | None = None
    created_at: datetime | None = None
    approved_at: datetime | None = None


@dataclass
class TelegramLinkToken:
    """A temporary token for Telegram deep-link authentication."""

    id: int | None = None
    token: str = ""
    created_at: datetime | None = None
    expires_at: datetime | None = None
    used: bool = False
