"""Price tiers, time-of-use bands and session costs (SQLAlchemy/SQLite)."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from leapconnect.application.ports.repositories import (
    ChargingRepository,
)
from leapconnect.domain.charging.models import (
    ChargingPriceTier,
    ChargingSessionCost,
    ChargingTimeBand,
)
from leapconnect.infrastructure.persistence.base import SqlRepositoryBase
from leapconnect.infrastructure.persistence.tables import (
    ChargingPriceTierRow,
    ChargingSessionCostRow,
    ChargingTimeBandRow,
)


class SqlChargingRepository(SqlRepositoryBase, ChargingRepository):
    """Price tiers, time-of-use bands and session costs."""

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
