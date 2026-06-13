"""ORM tables (SQLAlchemy declarative rows) for the SQLite adapter.

``Base.metadata`` is also what Alembic autogenerate targets
(see ``migrations/env.py``).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class VehicleSnapshotRow(Base):
    __tablename__ = "vehicle_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vin = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    battery_soc = Column(Integer, nullable=True)
    battery_current = Column(Float, nullable=True)
    battery_voltage = Column(Float, nullable=True)
    charging_power_kw = Column(Float, nullable=True)
    discharge_power_kw = Column(Float, nullable=True)
    expected_mileage = Column(Integer, nullable=True)
    total_mileage = Column(Integer, nullable=True)
    energy_kwh = Column(Float, nullable=True)
    outdoor_temp = Column(Integer, nullable=True)
    is_charging = Column(Boolean, nullable=True)
    is_plugged = Column(Boolean, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    charge_state = Column(Integer, nullable=True)
    speed = Column(Integer, nullable=True)
    is_parked = Column(Boolean, nullable=True)
    is_locked = Column(Boolean, nullable=True)
    tire_fl_pressure = Column(Float, nullable=True)
    tire_fr_pressure = Column(Float, nullable=True)
    tire_rl_pressure = Column(Float, nullable=True)
    tire_rr_pressure = Column(Float, nullable=True)
    is_regening = Column(Boolean, nullable=True)


class VehicleEventRow(Base):
    """Lightweight state-transition event for analytics."""

    __tablename__ = "vehicle_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vin = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    field_name = Column(String(50), nullable=False)
    old_value = Column(String(50), nullable=True)
    new_value = Column(String(50), nullable=True)


class AppSettingRow(Base):
    """Simple key/value store for application settings."""

    __tablename__ = "app_settings"

    key = Column(String(64), primary_key=True)
    value = Column(String(256), nullable=True)


class AccountRow(Base):
    """Stored Leapmotor account credentials."""

    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(256), nullable=False, unique=True)
    password = Column(String(256), nullable=False)
    cert_path = Column(String(512), nullable=False)
    key_path = Column(String(512), nullable=False)
    p12_password = Column(String(256), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))


class LeapConnectUserRow(Base):
    """LeapConnect application user."""

    __tablename__ = "leapconnect_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    display_name = Column(String(256), nullable=False)
    password_hash = Column(String(512), nullable=False)
    salt = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))


class LocalSessionRow(Base):
    """Persisted dashboard session (token hash only — never the raw token).

    Brand-new table: created by ``Base.metadata.create_all`` at startup,
    so no Alembic migration (and no self-healing ALTER fallback) is needed.
    """

    __tablename__ = "local_sessions"

    token_hash = Column(String(64), primary_key=True)
    expires_at = Column(Float, nullable=False)  # epoch seconds
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))


class NotificationChannelRow(Base):
    """Configured notification channel (e.g. Telegram)."""

    __tablename__ = "notification_channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_type = Column(String(32), nullable=False)
    config_json = Column(String(2048), nullable=False, default="{}")
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))


class NotificationPreferenceRow(Base):
    """Per-event notification preference for a channel."""

    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    config_json = Column(String(1024), nullable=True)


class GeofenceRow(Base):
    """Geographic zone for enter/exit notifications."""

    __tablename__ = "geofences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vin = Column(String(20), nullable=True, index=True)
    name = Column(String(128), nullable=False)
    shape_type = Column(String(16), nullable=False, default="circle")
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_m = Column(Float, nullable=False, default=200.0)
    points_json = Column(Text, nullable=True)  # [[lat, lon], ...] for polygons
    notify_on_enter = Column(Boolean, nullable=False, default=True)
    notify_on_exit = Column(Boolean, nullable=False, default=True)
    enabled = Column(Boolean, nullable=False, default=True)


class TelegramUserRow(Base):
    """A Telegram user that has interacted with the bot."""

    __tablename__ = "telegram_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(64), nullable=False, unique=True)
    username = Column(String(256), nullable=True)
    first_name = Column(String(256), nullable=True)
    last_name = Column(String(256), nullable=True)
    status = Column(String(16), nullable=False, default="pending")
    linked_token = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    approved_at = Column(DateTime, nullable=True)


class TelegramLinkTokenRow(Base):
    """A temporary token for Telegram deep-link authentication."""

    __tablename__ = "telegram_link_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(64), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, nullable=False, default=False)


class ChargingPriceTierRow(Base):
    """A configurable charging price tier."""

    __tablename__ = "charging_price_tiers"

    id = Column(String(32), primary_key=True)
    label = Column(String(128), nullable=False)
    price_kwh = Column(Float, nullable=False, default=0.0)
    enabled = Column(Boolean, nullable=False, default=True)


class ChargingTimeBandRow(Base):
    """A time-of-use band with schedule and price."""

    __tablename__ = "charging_time_bands"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tier_id = Column(String(32), nullable=False, default="home_grid")
    name = Column(String(128), nullable=False)
    price_kwh = Column(Float, nullable=False, default=0.0)
    schedule = Column(String(2048), nullable=False, default="[]")
    color = Column(String(32), nullable=True)
    position = Column(Integer, nullable=False, default=0)


class ChargingSessionCostRow(Base):
    """Cost record for a single charging session."""

    __tablename__ = "charging_session_costs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vin = Column(String(20), nullable=False, index=True)
    start_ts = Column(DateTime, nullable=False, index=True)
    end_ts = Column(DateTime, nullable=True)
    tier_id = Column(String(32), nullable=False)
    time_band_id = Column(Integer, nullable=True)
    energy_kwh = Column(Float, nullable=True)
    peak_power_kw = Column(Float, nullable=True)
    cost = Column(Float, nullable=True)
    note = Column(String(256), nullable=True)


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------


class MaintenancePlanItemRow(Base):
    """An editable maintenance plan item for a single vehicle."""

    __tablename__ = "maintenance_plan_items"
    __table_args__ = (
        UniqueConstraint("vin", "service_type", name="uq_vin_service_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    vin = Column(String(20), nullable=False, index=True)
    service_type = Column(String(64), nullable=False)
    label = Column(String(128), nullable=False)
    category = Column(String(32), nullable=False, default="other")
    interval_km = Column(Integer, nullable=True)
    interval_months = Column(Integer, nullable=True)
    trigger_mode = Column(String(8), nullable=False, default="or")
    priority = Column(String(16), nullable=False, default="routine")
    last_done_km = Column(Integer, nullable=True)
    last_done_date = Column(DateTime, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    notes = Column(String(256), nullable=True)
    source = Column(String(16), nullable=False, default="catalog")
    source_ref = Column(String(128), nullable=True)


class MaintenanceRecordRow(Base):
    """A completed maintenance intervention (service log)."""

    __tablename__ = "maintenance_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vin = Column(String(20), nullable=False, index=True)
    service_type = Column(String(64), nullable=False)
    label = Column(String(128), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    mileage_km = Column(Integer, nullable=True)
    cost = Column(Float, nullable=True)
    provider = Column(String(128), nullable=True)
    notes = Column(String(256), nullable=True)


class MaintenanceRepoRow(Base):
    """A community repository the user has added."""

    __tablename__ = "maintenance_repos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(16), nullable=False, default="github")
    url = Column(String(512), nullable=False, unique=True)
    name = Column(String(128), nullable=True)
    author = Column(String(128), nullable=True)
    description = Column(String(512), nullable=True)
    branch = Column(String(64), nullable=True)
    added_at = Column(DateTime, nullable=True)
    last_fetched_at = Column(DateTime, nullable=True)
    etag = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="ok")
    manifest_json = Column(Text, nullable=True)


class MaintenancePackRow(Base):
    """A cached maintenance pack (from a repo, URL, or uploaded file)."""

    __tablename__ = "maintenance_packs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, nullable=True, index=True)
    slug = Column(String(128), nullable=False)
    name = Column(String(128), nullable=True)
    version = Column(Integer, nullable=True)
    author = Column(String(128), nullable=True)
    model_compat = Column(Text, nullable=True)
    payload_json = Column(Text, nullable=False)
    fetched_at = Column(DateTime, nullable=True)
