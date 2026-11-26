"""Charging provider accounts and cached charging points (SQLAlchemy/SQLite)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select

from leapconnect.application.ports.repositories import ChargingProviderRepository
from leapconnect.domain.charging.models import ChargingProviderAccount
from leapconnect.domain.charging.stations import ChargingStation
from leapconnect.infrastructure.persistence.base import SqlRepositoryBase
from leapconnect.infrastructure.persistence.tables import (
    ChargingProviderAccountRow,
    ChargingStationRow,
)


def _station(r: ChargingStationRow) -> ChargingStation:
    return ChargingStation(
        provider=r.provider,
        evse_id=r.evse_id,
        name=r.name,
        operator=r.operator,
        address=r.address,
        latitude=r.latitude,
        longitude=r.longitude,
        max_power_kw=r.max_power_kw,
        is_dc=r.is_dc,
        plugs=tuple(json.loads(r.plugs_json)) if r.plugs_json else (),
        is_open_24h=r.is_open_24h,
    )


class SqlChargingProviderRepository(SqlRepositoryBase, ChargingProviderRepository):
    """Connected charging provider accounts and the cached charging points."""

    def _account(self, r: ChargingProviderAccountRow) -> ChargingProviderAccount:
        credentials = {}
        if r.credentials:
            try:
                credentials = json.loads(self._cipher.decrypt(r.credentials))
            except (ValueError, TypeError):
                credentials = {}  # unreadable (key changed): reconnect
        return ChargingProviderAccount(
            id=r.id,
            provider=r.provider,
            username=r.username,
            credentials=credentials,
            auto_sync=bool(r.auto_sync),
            last_sync=r.last_sync,
            last_error=r.last_error,
        )

    async def get_provider_accounts(self) -> list[ChargingProviderAccount]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ChargingProviderAccountRow).order_by(
                    ChargingProviderAccountRow.id
                )
            )
            return [self._account(r) for r in result.scalars().all()]

    async def save_provider_account(
        self, account: ChargingProviderAccount
    ) -> ChargingProviderAccount:
        async with self._session_factory() as session:
            row = (
                await session.get(ChargingProviderAccountRow, account.id)
                if account.id
                else None
            )
            if row is None:
                row = ChargingProviderAccountRow()
                session.add(row)
            row.provider = account.provider
            row.username = account.username
            row.credentials = self._cipher.encrypt(json.dumps(account.credentials))
            row.auto_sync = account.auto_sync
            row.last_sync = account.last_sync
            row.last_error = account.last_error
            await session.commit()
            account.id = row.id
            return account

    async def delete_provider_account(self, account_id: int) -> bool:
        async with self._session_factory() as session:
            row = await session.get(ChargingProviderAccountRow, account_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def upsert_charging_stations(self, stations: list[ChargingStation]) -> None:
        if not stations:
            return
        async with self._session_factory() as session:
            for s in stations:
                row = await session.get(ChargingStationRow, (s.provider, s.evse_id))
                if row is None:
                    row = ChargingStationRow(provider=s.provider, evse_id=s.evse_id)
                    session.add(row)
                # A known value isn't lost when a later read lacks it
                for attr in (
                    "name",
                    "operator",
                    "address",
                    "latitude",
                    "longitude",
                    "max_power_kw",
                    "is_dc",
                    "is_open_24h",
                ):
                    value = getattr(s, attr)
                    if value is not None:
                        setattr(row, attr, value)
                if s.plugs:
                    row.plugs_json = json.dumps(list(s.plugs))
                row.updated_at = datetime.now(UTC)
            await session.commit()

    async def get_charging_stations(
        self, keys: list[tuple[str, str]] | None = None
    ) -> dict[tuple[str, str], ChargingStation]:
        async with self._session_factory() as session:
            result = await session.execute(select(ChargingStationRow))
            rows = result.scalars().all()
        wanted = set(keys) if keys is not None else None
        return {
            (r.provider, r.evse_id): _station(r)
            for r in rows
            if wanted is None or (r.provider, r.evse_id) in wanted
        }
