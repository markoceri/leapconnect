"""Price tiers, time-of-use bands and session costs (SQLAlchemy/SQLite)."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import delete, select

from leapconnect.application.ports.repositories import (
    ChargingRepository,
)
from leapconnect.domain.charging.models import (
    ChargingPriceTier,
    ChargingSessionCost,
    ChargingSessionExtra,
    ChargingTimeBand,
)
from leapconnect.infrastructure.persistence.base import SqlRepositoryBase
from leapconnect.infrastructure.persistence.tables import (
    ChargingPriceTierRow,
    ChargingSessionCostRow,
    ChargingSessionExtraRow,
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
            extras: dict[int, list[ChargingSessionExtra]] = {}
            if rows:
                result = await session.execute(
                    select(ChargingSessionExtraRow)
                    .where(
                        ChargingSessionExtraRow.session_cost_id.in_(
                            [r.id for r in rows]
                        )
                    )
                    .order_by(
                        ChargingSessionExtraRow.position, ChargingSessionExtraRow.id
                    )
                )
                for e in result.scalars().all():
                    extras.setdefault(e.session_cost_id, []).append(_extra(e))
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
                zone_name=r.zone_name,
                latitude=r.latitude,
                longitude=r.longitude,
                cost_manual=bool(r.cost_manual),
                energy_manual=bool(r.energy_manual),
                manual_price_kwh=r.manual_price_kwh,
                external_source=r.external_source,
                external_id=r.external_id,
                provider_account_id=r.provider_account_id,
                evse_id=r.evse_id,
                auto_link_disabled=bool(r.auto_link_disabled),
                extras=extras.get(r.id, []),
            )
            for r in rows
        ]

    async def upsert_session_cost(self, sc: ChargingSessionCost) -> ChargingSessionCost:
        """Create or update a session cost record and its extras."""
        async with self._session_factory() as session:
            row = await session.get(ChargingSessionCostRow, sc.id) if sc.id else None
            if row is None:
                row = ChargingSessionCostRow()
                session.add(row)
            row.vin = sc.vin
            row.start_ts = sc.start_ts
            row.end_ts = sc.end_ts
            row.tier_id = sc.tier_id
            row.time_band_id = sc.time_band_id
            row.energy_kwh = sc.energy_kwh
            row.peak_power_kw = sc.peak_power_kw
            row.cost = sc.cost
            row.note = sc.note
            row.zone_name = sc.zone_name
            row.latitude = sc.latitude
            row.longitude = sc.longitude
            row.cost_manual = sc.cost_manual
            row.energy_manual = sc.energy_manual
            row.manual_price_kwh = sc.manual_price_kwh
            row.external_source = sc.external_source
            row.external_id = sc.external_id
            row.provider_account_id = sc.provider_account_id
            row.evse_id = sc.evse_id
            row.auto_link_disabled = sc.auto_link_disabled
            await session.flush()
            sc.id = row.id
            # The extras are part of the record: replaced as a whole
            await session.execute(
                delete(ChargingSessionExtraRow).where(
                    ChargingSessionExtraRow.session_cost_id == sc.id
                )
            )
            extra_rows = [_extra_row(sc.id, i, e) for i, e in enumerate(sc.extras)]
            session.add_all(extra_rows)
            await session.flush()
            for extra, extra_row in zip(sc.extras, extra_rows, strict=True):
                extra.id = extra_row.id
            await session.commit()
            return sc

    async def get_external_links(self, source: str) -> dict[str, tuple[str, int]]:
        """Records imported from a provider, any vehicle:
        ``{external_id: (vin, record id)}``."""
        stmt = select(
            ChargingSessionCostRow.external_id,
            ChargingSessionCostRow.vin,
            ChargingSessionCostRow.id,
        ).where(
            ChargingSessionCostRow.external_source == source,
            ChargingSessionCostRow.external_id.is_not(None),
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return {eid: (vin, cid) for eid, vin, cid in result.all()}

    async def delete_session_cost(self, cost_id: int) -> bool:
        """Delete a session cost record and its extras."""
        async with self._session_factory() as session:
            row = await session.get(ChargingSessionCostRow, cost_id)
            if not row:
                return False
            await session.execute(
                delete(ChargingSessionExtraRow).where(
                    ChargingSessionExtraRow.session_cost_id == cost_id
                )
            )
            await session.delete(row)
            await session.commit()
            return True


_EXTRA_FIELDS = (
    "kind",
    "label",
    "included",
    "amount",
    "rate",
    "time_unit",
    "billing",
    "start_ref",
    "start_offset_min",
    "end_ref",
    "duration_min",
    "cap",
    "minutes",
    "cost",
    "source",
)


def _extra(row: ChargingSessionExtraRow) -> ChargingSessionExtra:
    return ChargingSessionExtra(
        id=row.id, **{f: getattr(row, f) for f in _EXTRA_FIELDS}
    )


def _extra_row(
    session_cost_id: int, position: int, extra: ChargingSessionExtra
) -> ChargingSessionExtraRow:
    return ChargingSessionExtraRow(
        session_cost_id=session_cost_id,
        position=position,
        **{f: getattr(extra, f) for f in _EXTRA_FIELDS},
    )
