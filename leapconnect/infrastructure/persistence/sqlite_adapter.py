"""SQLAlchemy/SQLite adapter — thin facade over the per-context repositories.

Each bounded context has its own repository class (``SqlTelemetryRepository``,
``SqlChargingRepository``, …) sharing one async engine/session factory.
``SqlAlchemyRepository`` composes them all and implements the combined
``AppRepository`` port plus the storage lifecycle (create_all + Alembic).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leapconnect.application.ports.repositories import AppRepository
from leapconnect.infrastructure.persistence.account import SqlAccountRepository
from leapconnect.infrastructure.persistence.charging import SqlChargingRepository
from leapconnect.infrastructure.persistence.maintenance import SqlMaintenanceRepository
from leapconnect.infrastructure.persistence.migration import run_alembic_upgrade
from leapconnect.infrastructure.persistence.notifications import (
    SqlNotificationRepository,
)
from leapconnect.infrastructure.persistence.settings import SqlSettingsRepository
from leapconnect.infrastructure.persistence.tables import Base
from leapconnect.infrastructure.persistence.telemetry import SqlTelemetryRepository


class SqlAlchemyRepository(
    SqlTelemetryRepository,
    SqlSettingsRepository,
    SqlAccountRepository,
    SqlNotificationRepository,
    SqlChargingRepository,
    SqlMaintenanceRepository,
    AppRepository,
):
    """Concrete adapter backed by an async SQLAlchemy engine (SQLite)."""

    def __init__(self, database_url: str) -> None:
        # aiosqlite requires the ``sqlite+aiosqlite:///`` scheme
        self._engine = create_async_engine(database_url, echo=False)
        super().__init__(async_sessionmaker(self._engine, expire_on_commit=False))

    # -- lifecycle -----------------------------------------------------------

    async def init_db(self) -> None:
        # Create tables for fresh installs
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Run Alembic migrations (async-compatible)
        async with self._engine.begin() as conn:
            await conn.run_sync(run_alembic_upgrade)

    async def close(self) -> None:
        await self._engine.dispose()
