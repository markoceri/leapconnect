"""Preferences, scheduler, MQTT, ABRP, messages and system DTOs."""

from __future__ import annotations

from leapmotor_api.models import (
    Message,
)
from pydantic import BaseModel


class SchedulerStatusResponse(BaseModel):
    enabled: bool
    interval_minutes: int
    mqtt_interval_seconds: int
    rate_limit_seconds: int = 10
    transition_detection_enabled: bool = True
    transition_poll_interval_seconds: int = 10
    transition_min_event_interval_seconds: int = 10
    is_running: bool
    last_run: str | None = None
    last_error: str | None = None
    total_runs: int
    total_errors: int


class DatabaseSizeResponse(BaseModel):
    """Response for the database size endpoint."""

    size_bytes: int
    size_human: str


class MessageSchema(BaseModel):
    id: int
    vin: str | None = None
    title: str | None = None
    message: str | None = None
    send_time: str | None = None
    is_read: bool = False
    url: str | None = None
    msg_type: int | None = None

    @classmethod
    def from_model(cls, m: Message) -> MessageSchema:
        return cls(
            id=m.id,
            vin=m.vin,
            title=m.title,
            message=m.message,
            send_time=m.send_datetime.isoformat() if m.send_datetime else None,
            is_read=m.is_read,
            url=m.url,
            msg_type=m.msg_type,
        )


class MessageListResponse(BaseModel):
    count: int
    page_no: int
    page_size: int
    messages: list[MessageSchema]


class UnreadCountResponse(BaseModel):
    unread: int


class PreferencesResponse(BaseModel):
    electricity_price_kwh: float = 0.25
    theme: str = "dark"
    downsampling_enabled: bool = True
    downsampling_max_points: int = 2000
    has_solar_panels: bool = False
    home_pricing_mode: str = "flat"


class MqttStatusResponse(BaseModel):
    enabled: bool = False
    connected: bool = False
    broker: str = ""
    port: int = 1883
    username: str = ""
    use_tls: bool = False
    discovery_prefix: str = "homeassistant"
    topic_prefix: str = "leapconnect"
    last_error: str | None = None


class MqttTestResponse(BaseModel):
    status: str
    message: str


class AbrpStatusResponse(BaseModel):
    enabled: bool = False
    user_token: str = ""
    is_running: bool = False
    last_error: str | None = None
    total_sends: int = 0
    total_errors: int = 0
