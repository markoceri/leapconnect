"""SQLAlchemy/SQLite adapter for the vehicle history repository."""

from __future__ import annotations

import asyncio
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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .repository import VehicleHistoryRepository, VehicleSnapshot
from .scheduler import SchedulerSettings


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
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    charge_state = Column(Integer, nullable=True)
    speed = Column(Integer, nullable=True)


class AppSettingRow(Base):
    """Simple key/value store for application settings."""
    __tablename__ = "app_settings"

    key = Column(String(64), primary_key=True)
    value = Column(String(256), nullable=True)


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
        date_label = func.strftime("%Y-%m-%d", VehicleSnapshotRow.timestamp).label("date")

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

            summaries.append({
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
            })

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

