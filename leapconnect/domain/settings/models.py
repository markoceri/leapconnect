"""User-configurable settings models."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_INTERVAL_MINUTES = 15


@dataclass
class UserPreferences:
    """User-configurable preferences."""

    electricity_price_kwh: float = 0.25
    theme: str = "dark"
    downsampling_enabled: bool = True
    downsampling_max_points: int = 2000
    has_solar_panels: bool = False
    home_pricing_mode: str = "flat"  # "flat" or "time_of_use"
    auto_theme_from_vehicle: bool = False  # auto-pick accent colour from the vehicle


@dataclass
class SchedulerSettings:
    """User-facing scheduler configuration."""

    enabled: bool = False
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES
    mqtt_interval_seconds: int = 60
    rate_limit_seconds: int = 10
    # Transition detection settings
    transition_detection_enabled: bool = True
    transition_poll_interval_seconds: int = 10
    transition_min_event_interval_seconds: int = 10


@dataclass
class LiveRefreshSettings:
    """Live refresh configuration for WebSocket-connected clients."""

    interval_seconds: int = 30  # 0 = disabled, default 30s


@dataclass
class MqttSettings:
    """MQTT connection settings for Home Assistant integration."""

    enabled: bool = False
    broker: str = ""
    port: int = 1883
    username: str = ""
    password: str = ""
    use_tls: bool = False
    discovery_prefix: str = "homeassistant"
    topic_prefix: str = "leapconnect"


@dataclass
class AbrpSettings:
    """ABRP (A Better Route Planner) telemetry settings."""

    enabled: bool = False
    user_token: str = ""
