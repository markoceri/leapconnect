"""SQLAlchemy/SQLite adapter for the vehicle history repository."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    func,
    select,
    text,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from models import (
    ChargingPriceTier,
    ChargingSessionCost,
    ChargingTimeBand,
    Geofence,
    NotificationChannel,
    NotificationPreference,
    SchedulerSettings,
    TelegramUser,
    VehicleEvent,
    VehicleSnapshot,
)

from .repository import VehicleHistoryRepository

# ---------------------------------------------------------------------------
# ORM model
# ---------------------------------------------------------------------------


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
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_m = Column(Float, nullable=False, default=200.0)
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
# Adapter
# ---------------------------------------------------------------------------


class SQLAlchemyVehicleHistoryRepository(VehicleHistoryRepository):
    """Concrete adapter backed by an async SQLAlchemy engine (SQLite)."""

    def __init__(self, database_url: str) -> None:
        # aiosqlite requires the ``sqlite+aiosqlite:///`` scheme
        self._engine = create_async_engine(database_url, echo=False)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    # -- lifecycle -----------------------------------------------------------

    async def init_db(self) -> None:
        # Create tables for fresh installs
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Run Alembic migrations (async-compatible)
        async with self._engine.begin() as conn:
            await conn.run_sync(self._run_alembic_upgrade)

    @staticmethod
    def _run_alembic_upgrade(sync_conn) -> None:
        """Run pending Alembic migrations on a sync connection."""
        from pathlib import Path

        import sqlalchemy
        from alembic.config import Config
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        from alembic.script import ScriptDirectory

        base_dir = Path(__file__).resolve().parent.parent
        alembic_cfg = Config(str(base_dir / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(base_dir / "migrations"))
        script = ScriptDirectory.from_config(alembic_cfg)

        # If alembic_version doesn't exist, determine if this is a fresh DB
        # (created by create_all with full schema) or a pre-alembic DB.
        inspector = sqlalchemy.inspect(sync_conn)
        if not inspector.has_table("alembic_version"):
            sync_conn.execute(
                text(
                    "CREATE TABLE alembic_version (  version_num VARCHAR(32) NOT NULL)"
                )
            )
            # If the table already has columns from later migrations,
            # it was created by create_all — stamp at head.
            columns = {c["name"] for c in inspector.get_columns("vehicle_snapshots")}
            if inspector.has_table("vehicle_events"):
                stamp_rev = script.get_current_head()
            elif "is_regening" in columns:
                stamp_rev = "0003"
            elif "charging_power_kw" in columns:
                stamp_rev = "0002"
            else:
                stamp_rev = "0001"
            sync_conn.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:rev)"),
                {"rev": stamp_rev},
            )

        # Run pending migrations
        context = MigrationContext.configure(sync_conn, opts={"render_as_batch": True})
        current_rev = context.get_current_revision()
        head_rev = script.get_current_head()

        if current_rev != head_rev:

            def do_upgrade(revision, context):
                return script._upgrade_revs(head_rev, revision)

            with Operations.context(context):
                context._migrations_fn = do_upgrade
                context.run_migrations()

    async def close(self) -> None:
        await self._engine.dispose()

    # -- write ---------------------------------------------------------------

    async def save_snapshot(self, snapshot: VehicleSnapshot) -> None:
        row = VehicleSnapshotRow(
            vin=snapshot.vin,
            timestamp=snapshot.timestamp,
            battery_soc=snapshot.battery_soc,
            battery_current=snapshot.battery_current,
            battery_voltage=snapshot.battery_voltage,
            charging_power_kw=snapshot.battery_charging_power_kw,
            discharge_power_kw=snapshot.battery_discharge_power_kw,
            expected_mileage=snapshot.battery_expected_mileage,
            total_mileage=snapshot.drive_total_mileage,
            energy_kwh=snapshot.battery_dump_energy,
            outdoor_temp=snapshot.climate_outdoor_temp,
            is_charging=snapshot.battery_is_charging,
            is_plugged=snapshot.vehicle_is_plugged,
            latitude=snapshot.vehicle_latitude,
            longitude=snapshot.vehicle_longitude,
            charge_state=snapshot.battery_charge_state,
            speed=snapshot.drive_speed,
            is_parked=snapshot.drive_is_parked,
            is_locked=snapshot.vehicle_is_locked,
            tire_fl_pressure=snapshot.tire_front_left_pressure,
            tire_fr_pressure=snapshot.tire_front_right_pressure,
            tire_rl_pressure=snapshot.tire_rear_left_pressure,
            tire_rr_pressure=snapshot.tire_rear_right_pressure,
            is_regening=snapshot.vehicle_is_regening,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()

    async def save_event(self, event: VehicleEvent) -> None:
        """Persist a single state-transition event."""
        row = VehicleEventRow(
            vin=event.vin,
            timestamp=event.timestamp,
            event_type=event.event_type,
            field_name=event.field_name,
            old_value=event.old_value,
            new_value=event.new_value,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()

    async def get_events(
        self,
        vin: str,
        *,
        days: int = 30,
        event_type: str | None = None,
    ) -> list[VehicleEvent]:
        """Return events for *vin* over the last *days* days."""
        since = datetime.now(UTC) - timedelta(days=days)
        conditions = [
            VehicleEventRow.vin == vin,
            VehicleEventRow.timestamp >= since,
        ]
        if event_type:
            conditions.append(VehicleEventRow.event_type == event_type)
        stmt = (
            select(VehicleEventRow)
            .where(*conditions)
            .order_by(VehicleEventRow.timestamp.asc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [
            VehicleEvent(
                vin=r.vin,
                timestamp=r.timestamp,
                event_type=r.event_type,
                field_name=r.field_name,
                old_value=r.old_value,
                new_value=r.new_value,
            )
            for r in rows
        ]

    # -- read ----------------------------------------------------------------

    async def get_history(
        self,
        vin: str,
        *,
        days: int = 30,
        from_date: str | None = None,
        to_date: str | None = None,
        max_points: int | None = None,
    ) -> list[VehicleSnapshot]:
        if from_date and to_date:
            # Use explicit date range (YYYY-MM-DD)
            since = datetime.fromisoformat(f"{from_date}T00:00:00+00:00")
            until = datetime.fromisoformat(f"{to_date}T23:59:59+00:00")
            stmt = (
                select(VehicleSnapshotRow)
                .where(
                    VehicleSnapshotRow.vin == vin,
                    VehicleSnapshotRow.timestamp >= since,
                    VehicleSnapshotRow.timestamp <= until,
                )
                .order_by(VehicleSnapshotRow.timestamp.asc())
            )
        elif days == 1:
            # "Today": from midnight of the current day
            now = datetime.now(UTC)
            since = now.replace(hour=0, minute=0, second=0, microsecond=0)
            stmt = (
                select(VehicleSnapshotRow)
                .where(
                    VehicleSnapshotRow.vin == vin, VehicleSnapshotRow.timestamp >= since
                )
                .order_by(VehicleSnapshotRow.timestamp.asc())
            )
        else:
            since = datetime.now(UTC) - timedelta(days=days)
            stmt = (
                select(VehicleSnapshotRow)
                .where(
                    VehicleSnapshotRow.vin == vin, VehicleSnapshotRow.timestamp >= since
                )
                .order_by(VehicleSnapshotRow.timestamp.asc())
            )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()

        # Downsample if max_points is specified and we have more rows
        if max_points and len(rows) > max_points:
            rows = self._downsample_rows(rows, max_points)

        return [
            VehicleSnapshot(
                vin=r.vin,
                timestamp=r.timestamp,
                battery_soc=r.battery_soc,
                battery_current=r.battery_current,
                battery_voltage=r.battery_voltage,
                battery_charging_power_kw=r.charging_power_kw
                if r.charging_power_kw
                else (
                    round(abs(r.battery_current) * r.battery_voltage / 1000, 2)
                    if r.battery_current
                    and r.battery_voltage
                    and (r.is_charging or r.is_regening)
                    else None
                ),
                battery_discharge_power_kw=r.discharge_power_kw
                if r.discharge_power_kw
                else (
                    round(r.battery_current * r.battery_voltage / 1000, 2)
                    if r.battery_current
                    and r.battery_voltage
                    and r.battery_current > 0
                    and not r.is_charging
                    and not r.is_regening
                    else None
                ),
                battery_expected_mileage=r.expected_mileage,
                drive_total_mileage=r.total_mileage,
                battery_dump_energy=r.energy_kwh,
                climate_outdoor_temp=r.outdoor_temp,
                battery_is_charging=r.is_charging,
                vehicle_is_plugged=r.is_plugged,
                vehicle_latitude=r.latitude,
                vehicle_longitude=r.longitude,
                battery_charge_state=r.charge_state,
                drive_speed=r.speed,
                drive_is_parked=r.is_parked,
                vehicle_is_locked=r.is_locked,
                tire_front_left_pressure=r.tire_fl_pressure,
                tire_front_right_pressure=r.tire_fr_pressure,
                tire_rear_left_pressure=r.tire_rl_pressure,
                tire_rear_right_pressure=r.tire_rr_pressure,
                vehicle_is_regening=r.is_regening,
            )
            for r in rows
        ]

    @staticmethod
    def _downsample_rows(rows: list, max_points: int) -> list:
        """Downsample rows to max_points while preserving state transitions.

        Always keeps: first row, last row, and any row where charging/plugged
        state changes compared to the previous row (critical for KPI accuracy).
        Remaining budget is filled with evenly-spaced samples.
        """
        n = len(rows)
        # Mark transition boundary indices (always keep these)
        keep = {0, n - 1}
        for i in range(1, n):
            if rows[i].is_charging != rows[i - 1].is_charging:
                keep.add(i)
                keep.add(i - 1)
            if rows[i].is_plugged != rows[i - 1].is_plugged:
                keep.add(i)
                keep.add(i - 1)

        # Fill remaining budget with evenly-spaced samples
        remaining_budget = max_points - len(keep)
        if remaining_budget > 0:
            step = max(1, n / (remaining_budget + 1))
            pos = step
            while pos < n and len(keep) < max_points:
                keep.add(int(pos))
                pos += step

        return [rows[i] for i in sorted(keep)]

    async def get_daily_summary(
        self,
        vin: str,
        *,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        since = datetime.now(UTC) - timedelta(days=days)
        date_label = func.strftime("%Y-%m-%d", VehicleSnapshotRow.timestamp).label(
            "date"
        )

        stmt = (
            select(
                date_label,
                func.min(VehicleSnapshotRow.battery_soc).label("min_soc"),
                func.max(VehicleSnapshotRow.battery_soc).label("max_soc"),
                func.round(func.avg(VehicleSnapshotRow.battery_soc)).label("avg_soc"),
                func.min(VehicleSnapshotRow.expected_mileage).label("min_range"),
                func.max(VehicleSnapshotRow.expected_mileage).label("max_range"),
                func.min(VehicleSnapshotRow.total_mileage).label("min_mileage"),
                func.max(VehicleSnapshotRow.total_mileage).label("max_mileage"),
                func.round(func.avg(VehicleSnapshotRow.outdoor_temp)).label("avg_temp"),
                func.sum(
                    func.iif(VehicleSnapshotRow.is_charging == True, 1, 0)  # noqa: E712
                ).label("charge_sessions"),
                func.count().label("sample_count"),
            )
            .where(VehicleSnapshotRow.vin == vin, VehicleSnapshotRow.timestamp >= since)
            .group_by(date_label)
            .order_by(date_label.asc())
        )

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.all()

        summaries: list[dict[str, Any]] = []
        for r in rows:
            km_driven = 0
            if r.max_mileage is not None and r.min_mileage is not None:
                km_driven = max(0, r.max_mileage - r.min_mileage)

            # Rough energy estimate: ~0.15 kWh/km
            energy_delta = round(km_driven * 0.15, 1) if km_driven else 0

            summaries.append(
                {
                    "date": r.date,
                    "min_soc": r.min_soc,
                    "max_soc": r.max_soc,
                    "avg_soc": int(r.avg_soc) if r.avg_soc is not None else None,
                    "min_range": r.min_range,
                    "max_range": r.max_range,
                    "km_driven": km_driven,
                    "energy_delta": energy_delta,
                    "avg_temp": int(r.avg_temp) if r.avg_temp is not None else None,
                    "charge_sessions": r.charge_sessions or 0,
                    "sample_count": r.sample_count,
                }
            )

        return summaries

    # -- settings ------------------------------------------------------------

    async def load_scheduler_settings(self) -> SchedulerSettings:
        """Load scheduler settings from the DB, returning defaults if missing."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(AppSettingRow).where(
                    AppSettingRow.key.in_(
                        [
                            "scheduler_enabled",
                            "scheduler_interval",
                            "scheduler_mqtt_interval_seconds",
                            "scheduler_rate_limit_seconds",
                            "scheduler_transition_detection_enabled",
                            "scheduler_transition_poll_interval",
                            "scheduler_transition_min_event_interval",
                        ]
                    )
                )
            )
            rows = {r.key: r.value for r in result.scalars().all()}

        return SchedulerSettings(
            enabled=rows.get("scheduler_enabled", "0") == "1",
            interval_minutes=int(rows.get("scheduler_interval", "15")),
            mqtt_interval_seconds=int(
                rows.get("scheduler_mqtt_interval_seconds", "60")
            ),
            rate_limit_seconds=int(rows.get("scheduler_rate_limit_seconds", "10")),
            transition_detection_enabled=rows.get(
                "scheduler_transition_detection_enabled", "1"
            )
            == "1",
            transition_poll_interval_seconds=int(
                rows.get("scheduler_transition_poll_interval", "10")
            ),
            transition_min_event_interval_seconds=int(
                rows.get("scheduler_transition_min_event_interval", "10")
            ),
        )

    async def save_scheduler_settings(self, settings: SchedulerSettings) -> None:
        """Persist scheduler settings (upsert)."""
        pairs = {
            "scheduler_enabled": "1" if settings.enabled else "0",
            "scheduler_interval": str(settings.interval_minutes),
            "scheduler_mqtt_interval_seconds": str(settings.mqtt_interval_seconds),
            "scheduler_rate_limit_seconds": str(settings.rate_limit_seconds),
            "scheduler_transition_detection_enabled": "1"
            if settings.transition_detection_enabled
            else "0",
            "scheduler_transition_poll_interval": str(
                settings.transition_poll_interval_seconds
            ),
            "scheduler_transition_min_event_interval": str(
                settings.transition_min_event_interval_seconds
            ),
        }
        async with self._session_factory() as session:
            for key, value in pairs.items():
                existing = await session.get(AppSettingRow, key)
                if existing:
                    existing.value = value
                else:
                    session.add(AppSettingRow(key=key, value=value))
            await session.commit()

    # -- account credentials -------------------------------------------------

    async def save_account(
        self,
        username: str,
        password: str,
        cert_path: str,
        key_path: str,
        p12_password: str | None = None,
    ) -> None:
        """Save or update account credentials."""
        async with self._session_factory() as session:
            stmt = select(AccountRow).where(AccountRow.username == username)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                existing.password = password
                existing.cert_path = cert_path
                existing.key_path = key_path
                existing.p12_password = p12_password
            else:
                session.add(
                    AccountRow(
                        username=username,
                        password=password,
                        cert_path=cert_path,
                        key_path=key_path,
                        p12_password=p12_password,
                        created_at=datetime.now(UTC),
                    )
                )
            await session.commit()

    async def get_account(self) -> dict | None:
        """Return the first saved account or None."""
        async with self._session_factory() as session:
            stmt = select(AccountRow).order_by(AccountRow.id.asc()).limit(1)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return None
            return {
                "username": row.username,
                "password": row.password,
                "cert_path": row.cert_path,
                "key_path": row.key_path,
                "p12_password": row.p12_password,
            }

    async def delete_account(self, username: str) -> None:
        """Remove an account."""
        async with self._session_factory() as session:
            stmt = select(AccountRow).where(AccountRow.username == username)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                await session.delete(row)
                await session.commit()

    async def get_setting(self, key: str) -> str | None:
        """Get a single app setting value."""
        async with self._session_factory() as session:
            row = await session.get(AppSettingRow, key)
            return row.value if row else None

    async def save_setting(self, key: str, value: str) -> None:
        """Save a single app setting (upsert)."""
        async with self._session_factory() as session:
            existing = await session.get(AppSettingRow, key)
            if existing:
                existing.value = value
            else:
                session.add(AppSettingRow(key=key, value=value))
            await session.commit()

    # -- LeapConnect user management -----------------------------------------

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 100_000
        ).hex()

    async def create_user(self, display_name: str, password: str) -> dict:
        """Create a new LeapConnect user. Returns user dict."""
        salt = secrets.token_hex(16)
        pw_hash = self._hash_password(password, salt)
        async with self._session_factory() as session:
            row = LeapConnectUserRow(
                display_name=display_name,
                password_hash=pw_hash,
                salt=salt,
                created_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
            return {"id": row.id, "display_name": row.display_name}

    async def get_user(self) -> dict | None:
        """Return the first LeapConnect user or None."""
        async with self._session_factory() as session:
            stmt = (
                select(LeapConnectUserRow)
                .order_by(LeapConnectUserRow.id.asc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return None
            return {"id": row.id, "display_name": row.display_name}

    async def verify_user_password(self, password: str) -> bool:
        """Verify the LeapConnect user password."""
        async with self._session_factory() as session:
            stmt = (
                select(LeapConnectUserRow)
                .order_by(LeapConnectUserRow.id.asc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return False
            return self._hash_password(password, row.salt) == row.password_hash

    async def update_user(
        self, display_name: str | None = None, password: str | None = None
    ) -> dict | None:
        """Update LeapConnect user display name and/or password."""
        async with self._session_factory() as session:
            stmt = (
                select(LeapConnectUserRow)
                .order_by(LeapConnectUserRow.id.asc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return None
            if display_name is not None:
                row.display_name = display_name
            if password is not None:
                row.salt = secrets.token_hex(16)
                row.password_hash = self._hash_password(password, row.salt)
            await session.commit()
            return {"id": row.id, "display_name": row.display_name}

    # -- notification channels -----------------------------------------------

    async def get_notification_channels(self) -> list[NotificationChannel]:
        """Return all notification channels."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(NotificationChannelRow).order_by(NotificationChannelRow.id.asc())
            )
            rows = result.scalars().all()
        return [
            NotificationChannel(
                id=r.id,
                channel_type=r.channel_type,
                config=json.loads(r.config_json) if r.config_json else {},
                enabled=r.enabled,
                created_at=r.created_at,
            )
            for r in rows
        ]

    async def get_notification_channel(
        self, channel_id: int
    ) -> NotificationChannel | None:
        """Return a single notification channel by ID."""
        async with self._session_factory() as session:
            row = await session.get(NotificationChannelRow, channel_id)
            if not row:
                return None
            return NotificationChannel(
                id=row.id,
                channel_type=row.channel_type,
                config=json.loads(row.config_json) if row.config_json else {},
                enabled=row.enabled,
                created_at=row.created_at,
            )

    async def save_notification_channel(
        self, channel: NotificationChannel
    ) -> NotificationChannel:
        """Create or update a notification channel. Returns the saved channel."""
        async with self._session_factory() as session:
            if channel.id:
                row = await session.get(NotificationChannelRow, channel.id)
                if row:
                    row.channel_type = channel.channel_type
                    row.config_json = json.dumps(channel.config)
                    row.enabled = channel.enabled
                    await session.commit()
                    channel.id = row.id
                    return channel
            # Create new
            row = NotificationChannelRow(
                channel_type=channel.channel_type,
                config_json=json.dumps(channel.config),
                enabled=channel.enabled,
                created_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
            channel.id = row.id
            channel.created_at = row.created_at
            return channel

    async def delete_notification_channel(self, channel_id: int) -> bool:
        """Delete a notification channel and its preferences."""
        async with self._session_factory() as session:
            row = await session.get(NotificationChannelRow, channel_id)
            if not row:
                return False
            # Delete associated preferences
            prefs = await session.execute(
                select(NotificationPreferenceRow).where(
                    NotificationPreferenceRow.channel_id == channel_id
                )
            )
            for pref in prefs.scalars().all():
                await session.delete(pref)
            await session.delete(row)
            await session.commit()
            return True

    # -- notification preferences --------------------------------------------

    async def get_notification_preferences(
        self, channel_id: int
    ) -> list[NotificationPreference]:
        """Return all preferences for a channel."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(NotificationPreferenceRow).where(
                    NotificationPreferenceRow.channel_id == channel_id
                )
            )
            rows = result.scalars().all()
        return [
            NotificationPreference(
                id=r.id,
                channel_id=r.channel_id,
                event_type=r.event_type,
                enabled=r.enabled,
                config=json.loads(r.config_json) if r.config_json else None,
            )
            for r in rows
        ]

    async def save_notification_preferences(
        self, channel_id: int, preferences: list[NotificationPreference]
    ) -> None:
        """Upsert notification preferences for a channel (replaces all)."""
        async with self._session_factory() as session:
            # Delete existing
            existing = await session.execute(
                select(NotificationPreferenceRow).where(
                    NotificationPreferenceRow.channel_id == channel_id
                )
            )
            for row in existing.scalars().all():
                await session.delete(row)
            # Insert new
            for pref in preferences:
                session.add(
                    NotificationPreferenceRow(
                        channel_id=channel_id,
                        event_type=pref.event_type,
                        enabled=pref.enabled,
                        config_json=json.dumps(pref.config) if pref.config else None,
                    )
                )
            await session.commit()

    # -- geofences -----------------------------------------------------------

    async def get_geofences(self, vin: str | None = None) -> list[Geofence]:
        """Return geofences, optionally filtered by VIN."""
        conditions = []
        if vin:
            conditions.append((GeofenceRow.vin == vin) | (GeofenceRow.vin.is_(None)))
        stmt = select(GeofenceRow).order_by(GeofenceRow.id.asc())
        if conditions:
            stmt = stmt.where(*conditions)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [
            Geofence(
                id=r.id,
                vin=r.vin,
                name=r.name,
                latitude=r.latitude,
                longitude=r.longitude,
                radius_m=r.radius_m,
                notify_on_enter=r.notify_on_enter,
                notify_on_exit=r.notify_on_exit,
                enabled=r.enabled,
            )
            for r in rows
        ]

    async def save_geofence(self, geofence: Geofence) -> Geofence:
        """Create or update a geofence."""
        async with self._session_factory() as session:
            if geofence.id:
                row = await session.get(GeofenceRow, geofence.id)
                if row:
                    row.vin = geofence.vin
                    row.name = geofence.name
                    row.latitude = geofence.latitude
                    row.longitude = geofence.longitude
                    row.radius_m = geofence.radius_m
                    row.notify_on_enter = geofence.notify_on_enter
                    row.notify_on_exit = geofence.notify_on_exit
                    row.enabled = geofence.enabled
                    await session.commit()
                    return geofence
            # Create new
            row = GeofenceRow(
                vin=geofence.vin,
                name=geofence.name,
                latitude=geofence.latitude,
                longitude=geofence.longitude,
                radius_m=geofence.radius_m,
                notify_on_enter=geofence.notify_on_enter,
                notify_on_exit=geofence.notify_on_exit,
                enabled=geofence.enabled,
            )
            session.add(row)
            await session.commit()
            geofence.id = row.id
            return geofence

    async def delete_geofence(self, geofence_id: int) -> bool:
        """Delete a geofence by ID."""
        async with self._session_factory() as session:
            row = await session.get(GeofenceRow, geofence_id)
            if not row:
                return False
            await session.delete(row)
            await session.commit()
            return True

    # -- telegram users ------------------------------------------------------

    async def get_telegram_users(self, status: str | None = None) -> list[TelegramUser]:
        """Return all telegram users, optionally filtered by status."""
        async with self._session_factory() as session:
            stmt = select(TelegramUserRow)
            if status:
                stmt = stmt.where(TelegramUserRow.status == status)
            stmt = stmt.order_by(TelegramUserRow.created_at.desc())
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                TelegramUser(
                    id=r.id,
                    chat_id=r.chat_id,
                    username=r.username,
                    first_name=r.first_name,
                    last_name=r.last_name,
                    status=r.status,
                    linked_token=r.linked_token,
                    created_at=r.created_at,
                    approved_at=r.approved_at,
                )
                for r in rows
            ]

    async def get_telegram_user_by_chat_id(self, chat_id: str) -> TelegramUser | None:
        """Return a single telegram user by chat_id, or None."""
        async with self._session_factory() as session:
            stmt = select(TelegramUserRow).where(TelegramUserRow.chat_id == chat_id)
            result = await session.execute(stmt)
            r = result.scalar_one_or_none()
            if not r:
                return None
            return TelegramUser(
                id=r.id,
                chat_id=r.chat_id,
                username=r.username,
                first_name=r.first_name,
                last_name=r.last_name,
                status=r.status,
                linked_token=r.linked_token,
                created_at=r.created_at,
                approved_at=r.approved_at,
            )

    async def save_telegram_user(self, user: TelegramUser) -> TelegramUser:
        """Create or update a telegram user."""
        async with self._session_factory() as session:
            # Check if user already exists
            stmt = select(TelegramUserRow).where(
                TelegramUserRow.chat_id == user.chat_id
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                row.username = user.username
                row.first_name = user.first_name
                row.last_name = user.last_name
                row.status = user.status
                row.linked_token = user.linked_token
                row.approved_at = user.approved_at
            else:
                row = TelegramUserRow(
                    chat_id=user.chat_id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    status=user.status,
                    linked_token=user.linked_token,
                    created_at=user.created_at or datetime.now(UTC),
                    approved_at=user.approved_at,
                )
                session.add(row)
            await session.commit()
            user.id = row.id
            return user

    async def update_telegram_user_status(self, chat_id: str, status: str) -> bool:
        """Update status of a telegram user. Returns False if not found."""
        async with self._session_factory() as session:
            stmt = select(TelegramUserRow).where(TelegramUserRow.chat_id == chat_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return False
            row.status = status
            if status == "approved":
                row.approved_at = datetime.now(UTC)
            await session.commit()
            return True

    async def delete_telegram_user(self, chat_id: str) -> bool:
        """Remove a telegram user entirely."""
        async with self._session_factory() as session:
            stmt = select(TelegramUserRow).where(TelegramUserRow.chat_id == chat_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def get_approved_chat_ids(self) -> set[str]:
        """Return the set of all approved Telegram chat IDs."""
        async with self._session_factory() as session:
            stmt = select(TelegramUserRow.chat_id).where(
                TelegramUserRow.status == "approved"
            )
            result = await session.execute(stmt)
            return {r[0] for r in result.all()}

    # -- telegram link tokens ------------------------------------------------

    async def create_link_token(self, expires_minutes: int = 10) -> str:
        """Generate a new deep-link token. Returns the token string."""
        token = secrets.token_urlsafe(24)
        now = datetime.utcnow()
        row = TelegramLinkTokenRow(
            token=token,
            created_at=now,
            expires_at=now + timedelta(minutes=expires_minutes),
            used=False,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
        return token

    async def validate_link_token(self, token: str) -> bool:
        """Validate and consume a token. Returns True if valid."""
        async with self._session_factory() as session:
            stmt = select(TelegramLinkTokenRow).where(
                TelegramLinkTokenRow.token == token
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return False
            if row.used:
                return False
            if row.expires_at < datetime.utcnow():
                return False
            row.used = True
            await session.commit()
            return True

    # -- charging price tiers ------------------------------------------------

    async def get_price_tiers(self) -> list[ChargingPriceTier]:
        """Return all charging price tiers."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ChargingPriceTierRow).order_by(ChargingPriceTierRow.id)
            )
            rows = result.scalars().all()
        return [
            ChargingPriceTier(
                id=r.id,
                label=r.label,
                price_kwh=r.price_kwh,
                enabled=r.enabled,
            )
            for r in rows
        ]

    async def upsert_price_tier(self, tier: ChargingPriceTier) -> ChargingPriceTier:
        """Create or update a price tier."""
        async with self._session_factory() as session:
            row = await session.get(ChargingPriceTierRow, tier.id)
            if row:
                row.label = tier.label
                row.price_kwh = tier.price_kwh
                row.enabled = tier.enabled
            else:
                row = ChargingPriceTierRow(
                    id=tier.id,
                    label=tier.label,
                    price_kwh=tier.price_kwh,
                    enabled=tier.enabled,
                )
                session.add(row)
            await session.commit()
        return tier

    # -- charging time bands -------------------------------------------------

    async def get_time_bands(
        self, tier_id: str = "home_grid"
    ) -> list[ChargingTimeBand]:
        """Return time bands for a tier, ordered by position."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ChargingTimeBandRow)
                .where(ChargingTimeBandRow.tier_id == tier_id)
                .order_by(ChargingTimeBandRow.position)
            )
            rows = result.scalars().all()
        return [
            ChargingTimeBand(
                id=r.id,
                tier_id=r.tier_id,
                name=r.name,
                price_kwh=r.price_kwh,
                schedule=json.loads(r.schedule) if r.schedule else [],
                color=r.color,
                position=r.position,
            )
            for r in rows
        ]

    async def upsert_time_band(self, band: ChargingTimeBand) -> ChargingTimeBand:
        """Create or update a time band."""
        async with self._session_factory() as session:
            if band.id:
                row = await session.get(ChargingTimeBandRow, band.id)
                if row:
                    row.tier_id = band.tier_id
                    row.name = band.name
                    row.price_kwh = band.price_kwh
                    row.schedule = json.dumps(band.schedule)
                    row.color = band.color
                    row.position = band.position
                    await session.commit()
                    return band
            # Create new
            row = ChargingTimeBandRow(
                tier_id=band.tier_id,
                name=band.name,
                price_kwh=band.price_kwh,
                schedule=json.dumps(band.schedule),
                color=band.color,
                position=band.position,
            )
            session.add(row)
            await session.commit()
            band.id = row.id
            return band

    async def delete_time_band(self, band_id: int) -> bool:
        """Delete a time band by ID."""
        async with self._session_factory() as session:
            row = await session.get(ChargingTimeBandRow, band_id)
            if not row:
                return False
            await session.delete(row)
            await session.commit()
            return True

    # -- charging session costs ----------------------------------------------

    async def get_session_costs(
        self,
        vin: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[ChargingSessionCost]:
        """Return session costs for a VIN, optionally filtered by date range."""
        conditions = [ChargingSessionCostRow.vin == vin]
        if start:
            conditions.append(ChargingSessionCostRow.start_ts >= start)
        if end:
            conditions.append(ChargingSessionCostRow.start_ts <= end)
        stmt = (
            select(ChargingSessionCostRow)
            .where(*conditions)
            .order_by(ChargingSessionCostRow.start_ts.desc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [
            ChargingSessionCost(
                id=r.id,
                vin=r.vin,
                start_ts=r.start_ts,
                end_ts=r.end_ts,
                tier_id=r.tier_id,
                time_band_id=r.time_band_id,
                energy_kwh=r.energy_kwh,
                peak_power_kw=r.peak_power_kw,
                cost=r.cost,
                note=r.note,
            )
            for r in rows
        ]

    async def upsert_session_cost(self, sc: ChargingSessionCost) -> ChargingSessionCost:
        """Create or update a session cost record."""
        async with self._session_factory() as session:
            if sc.id:
                row = await session.get(ChargingSessionCostRow, sc.id)
                if row:
                    row.vin = sc.vin
                    row.start_ts = sc.start_ts
                    row.end_ts = sc.end_ts
                    row.tier_id = sc.tier_id
                    row.time_band_id = sc.time_band_id
                    row.energy_kwh = sc.energy_kwh
                    row.peak_power_kw = sc.peak_power_kw
                    row.cost = sc.cost
                    row.note = sc.note
                    await session.commit()
                    return sc
            # Create new
            row = ChargingSessionCostRow(
                vin=sc.vin,
                start_ts=sc.start_ts,
                end_ts=sc.end_ts,
                tier_id=sc.tier_id,
                time_band_id=sc.time_band_id,
                energy_kwh=sc.energy_kwh,
                peak_power_kw=sc.peak_power_kw,
                cost=sc.cost,
                note=sc.note,
            )
            session.add(row)
            await session.commit()
            sc.id = row.id
            return sc

    async def delete_session_cost(self, cost_id: int) -> bool:
        """Delete a session cost record."""
        async with self._session_factory() as session:
            row = await session.get(ChargingSessionCostRow, cost_id)
            if not row:
                return False
            await session.delete(row)
            await session.commit()
            return True
