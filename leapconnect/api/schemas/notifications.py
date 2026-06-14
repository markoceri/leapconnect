"""Notification channels, geofences and Telegram user DTOs."""

from __future__ import annotations

from pydantic import BaseModel


class NotificationChannelConfig(BaseModel):
    """Channel-specific configuration (e.g. Telegram bot_token + chat_id)."""

    bot_token: str = ""
    chat_id: str = ""


class NotificationChannelCreate(BaseModel):
    channel_type: str = "telegram"
    config: dict = {}
    enabled: bool = True


class NotificationChannelUpdate(BaseModel):
    config: dict | None = None
    enabled: bool | None = None


class NotificationChannelResponse(BaseModel):
    id: int
    channel_type: str
    config: dict
    enabled: bool
    created_at: str | None = None


class NotificationPreferenceItem(BaseModel):
    event_type: str
    enabled: bool = True
    config: dict | None = None


class NotificationPreferencesUpdate(BaseModel):
    channel_id: int
    preferences: list[NotificationPreferenceItem]


class NotificationEventInfo(BaseModel):
    """Describes an available notification event type."""

    event_type: str
    label: str
    description: str
    category: str
    has_image: bool = False
    configurable: bool = False
    config_schema: dict | None = None


class NotificationEventStatus(BaseModel):
    """Current status of a notification event (enabled + config)."""

    event_type: str
    label: str
    description: str
    category: str
    has_image: bool = False
    configurable: bool = False
    config_schema: dict | None = None
    enabled: bool = False
    config: dict | None = None


class TelegramUserResponse(BaseModel):
    id: int | None = None
    chat_id: str
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    status: str
    created_at: str | None = None
    approved_at: str | None = None


class TelegramLinkTokenResponse(BaseModel):
    token: str
    link: str
    expires_at: str
