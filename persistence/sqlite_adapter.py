"""SQLAlchemy/SQLite adapter for the vehicle history repository."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
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
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from models import SchedulerSettings, VehicleSnapshot

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
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class LeapConnectUserRow(Base):
    """LeapConnect application user."""

    __tablename__ = "leapconnect_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    display_name = Column(String(256), nullable=False)
    password_hash = Column(String(512), nullable=False)
    salt = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


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
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self._engine.dispose()

    # -- write ---------------------------------------------------------------

    async def save_snapshot(self, snapshot: VehicleSnapshot) -> None:
        row = VehicleSnapshotRow(
            vin=snapshot.vin,
            timestamp=snapshot.timestamp,
            battery_soc=snapshot.battery_soc,
            expected_mileage=snapshot.expected_mileage,
            total_mileage=snapshot.total_mileage,
            energy_kwh=snapshot.energy_kwh,
            outdoor_temp=snapshot.outdoor_temp,
            is_charging=snapshot.is_charging,
            is_plugged=snapshot.is_plugged,
            latitude=snapshot.latitude,
            longitude=snapshot.longitude,
            charge_state=snapshot.charge_state,
            speed=snapshot.speed,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()

    # -- read ----------------------------------------------------------------

    async def get_history(
        self,
        vin: str,
        *,
        days: int = 30,
    ) -> list[VehicleSnapshot]:
        since = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(VehicleSnapshotRow)
            .where(VehicleSnapshotRow.vin == vin, VehicleSnapshotRow.timestamp >= since)
            .order_by(VehicleSnapshotRow.timestamp.asc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [
            VehicleSnapshot(
                vin=r.vin,
                timestamp=r.timestamp,
                battery_soc=r.battery_soc,
                expected_mileage=r.expected_mileage,
                total_mileage=r.total_mileage,
                energy_kwh=r.energy_kwh,
                outdoor_temp=r.outdoor_temp,
                is_charging=r.is_charging,
                is_plugged=r.is_plugged,
                latitude=r.latitude,
                longitude=r.longitude,
                charge_state=r.charge_state,
                speed=r.speed,
            )
            for r in rows
        ]

    async def get_daily_summary(
        self,
        vin: str,
        *,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        since = datetime.utcnow() - timedelta(days=days)
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
                    AppSettingRow.key.in_(["scheduler_enabled", "scheduler_interval"])
                )
            )
            rows = {r.key: r.value for r in result.scalars().all()}

        return SchedulerSettings(
            enabled=rows.get("scheduler_enabled", "0") == "1",
            interval_minutes=int(rows.get("scheduler_interval", "15")),
        )

    async def save_scheduler_settings(self, settings: SchedulerSettings) -> None:
        """Persist scheduler settings (upsert)."""
        pairs = {
            "scheduler_enabled": "1" if settings.enabled else "0",
            "scheduler_interval": str(settings.interval_minutes),
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
                        created_at=datetime.utcnow(),
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
                created_at=datetime.utcnow(),
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
