"""Persistence layer data models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

DEFAULT_INTERVAL_MINUTES = 15


@dataclass(frozen=True, slots=True)
class VehicleSnapshot:
    """A single point-in-time snapshot of vehicle telemetry."""

    vin: str
    timestamp: datetime

    # Battery
    battery_soc: int | None = None
    battery_current: float | None = None
    battery_voltage: float | None = None
    battery_charging_power_kw: float | None = None
    battery_discharge_power_kw: float | None = None
    battery_is_charging: bool | None = None
    battery_is_discharging: bool | None = None
    battery_dump_energy: float | None = None
    battery_expected_mileage: int | None = None
    battery_charge_state: int | None = None

    # Drive
    drive_is_parked: bool | None = None
    drive_speed: int | None = None
    drive_total_mileage: int | None = None

    # Ignition
    ignition_is_on1: bool | None = None
    ignition_is_on2: bool | None = None

    # Vehicle
    vehicle_is_charging: bool | None = None
    vehicle_is_plugged: bool | None = None
    vehicle_is_regening: bool | None = None
    vehicle_is_parked: bool | None = None
    vehicle_is_locked: bool | None = None
    vehicle_latitude: float | None = None
    vehicle_longitude: float | None = None

    # Climate
    climate_outdoor_temp: int | None = None

    # Tire
    tire_front_left_pressure: float | None = None
    tire_front_right_pressure: float | None = None
    tire_rear_left_pressure: float | None = None
    tire_rear_right_pressure: float | None = None


@dataclass
class UserPreferences:
    """User-configurable preferences."""

    electricity_price_kwh: float = 0.25
    theme: str = "dark"
    downsampling_enabled: bool = True
    downsampling_max_points: int = 2000
    has_solar_panels: bool = False
    home_pricing_mode: str = "flat"  # "flat" or "time_of_use"


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


@dataclass(frozen=True, slots=True)
class VehicleEvent:
    """A single state-transition event detected for a vehicle."""

    vin: str
    timestamp: datetime
    event_type: str  # e.g. "regen_start", "regen_stop", "charge_start"
    field_name: str  # e.g. "is_regening", "battery_soc"
    old_value: str | None = None
    new_value: str | None = None


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Telegram Users
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Charging Cost Tiers
# ---------------------------------------------------------------------------


@dataclass
class ChargingPriceTier:
    """A pricing tier for charging sessions."""

    id: str = ""
    label: str = ""
    price_kwh: float = 0.0
    enabled: bool = True


@dataclass
class ChargingTimeBand:
    """A time-of-use band with schedule and price."""

    id: int | None = None
    tier_id: str = "home_grid"
    name: str = ""
    price_kwh: float = 0.0
    schedule: list | None = (
        None  # [{days: [0-6], start_hour, start_min, end_hour, end_min}]
    )
    color: str | None = None
    position: int = 0

    def __post_init__(self):
        if self.schedule is None:
            self.schedule = []


@dataclass
class ChargingSessionCost:
    """Cost record for a single charging session."""

    id: int | None = None
    vin: str = ""
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    tier_id: str = ""
    time_band_id: int | None = None
    energy_kwh: float | None = None
    peak_power_kw: float | None = None
    cost: float | None = None
    note: str | None = None


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------


@dataclass
class MaintenancePlanItem:
    """A single maintenance service item in a vehicle's plan (editable)."""

    id: int | None = None
    vin: str = ""
    service_type: str = ""
    label: str = ""
    category: str = ""
    interval_km: int | None = None
    interval_months: int | None = None
    trigger_mode: str = "or"  # "or" | "km" | "time" | "and"
    priority: str = "routine"  # "routine" | "important" | "urgent"
    last_done_km: int | None = None
    last_done_date: datetime | None = None
    enabled: bool = True
    notes: str | None = None
    source: str = "catalog"  # "catalog" | "repo" | "local"
    source_ref: str | None = None  # repo/pack slug the item was imported from


@dataclass
class MaintenanceRecord:
    """A completed maintenance intervention (service log entry)."""

    id: int | None = None
    vin: str = ""
    service_type: str = ""
    label: str = ""
    timestamp: datetime | None = None
    mileage_km: int | None = None
    cost: float | None = None
    provider: str | None = None
    notes: str | None = None


@dataclass
class MaintenanceAlert:
    """Computed alert for an upcoming or overdue maintenance item."""

    plan_item_id: int
    service_type: str
    label: str
    category: str
    priority: str
    status: str  # "upcoming" | "overdue" | "critical"
    due_km: int | None = None
    due_date: datetime | None = None
    current_km: int | None = None
    remaining_km: int | None = None
    remaining_days: int | None = None


@dataclass
class MaintenanceRepo:
    """A community repository the user has added."""

    id: int | None = None
    type: str = "github"  # "github" | "url"
    url: str = ""
    name: str | None = None
    author: str | None = None
    description: str | None = None
    branch: str | None = None
    added_at: datetime | None = None
    last_fetched_at: datetime | None = None
    etag: str | None = None
    status: str = "ok"  # "ok" | "error" | "pending"
    # Cached manifest: list of available packs (slug/file/name/model_compat).
    manifest: list[dict] | None = None


@dataclass
class MaintenancePack:
    """A cached maintenance pack (from a repo, URL, or uploaded file)."""

    id: int | None = None
    repo_id: int | None = None
    slug: str = ""
    name: str | None = None
    version: int | None = None
    author: str | None = None
    model_compat: list[str] | None = None
    # Full pack payload: {schema, name, author, version, model_compat, items[]}.
    payload: dict | None = None
    fetched_at: datetime | None = None
