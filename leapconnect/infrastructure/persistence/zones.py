"""Zone persistence (SQLAlchemy/SQLite).

The table is still named ``geofences`` (see ``ZoneRow``) so no data migration
is required; only the domain/ORM vocabulary moved to "zone".
"""

from __future__ import annotations

import json

from sqlalchemy import select

from leapconnect.application.ports.repositories import ZoneRepository
from leapconnect.domain.zones.models import Zone
from leapconnect.infrastructure.persistence.base import SqlRepositoryBase
from leapconnect.infrastructure.persistence.tables import ZoneRow


class SqlZoneRepository(SqlRepositoryBase, ZoneRepository):
    """CRUD for geographic zones."""

    async def get_zones(self, vin: str | None = None) -> list[Zone]:
        """Return zones, optionally filtered by VIN."""
        conditions = []
        if vin:
            conditions.append((ZoneRow.vin == vin) | (ZoneRow.vin.is_(None)))
        stmt = select(ZoneRow).order_by(ZoneRow.id.asc())
        if conditions:
            stmt = stmt.where(*conditions)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [
            Zone(
                id=r.id,
                vin=r.vin,
                name=r.name,
                shape_type=r.shape_type or "circle",
                latitude=r.latitude,
                longitude=r.longitude,
                radius_m=r.radius_m,
                points=json.loads(r.points_json) if r.points_json else None,
                notify_on_enter=r.notify_on_enter,
                notify_on_exit=r.notify_on_exit,
                enabled=r.enabled,
                charging_tier_id=r.charging_tier_id,
            )
            for r in rows
        ]

    async def save_zone(self, zone: Zone) -> Zone:
        """Create or update a zone."""
        async with self._session_factory() as session:
            if zone.id:
                row = await session.get(ZoneRow, zone.id)
                if row:
                    row.vin = zone.vin
                    row.name = zone.name
                    row.shape_type = zone.shape_type
                    row.latitude = zone.latitude
                    row.longitude = zone.longitude
                    row.radius_m = zone.radius_m
                    row.points_json = json.dumps(zone.points) if zone.points else None
                    row.notify_on_enter = zone.notify_on_enter
                    row.notify_on_exit = zone.notify_on_exit
                    row.enabled = zone.enabled
                    row.charging_tier_id = zone.charging_tier_id
                    await session.commit()
                    return zone
            # Create new
            row = ZoneRow(
                vin=zone.vin,
                name=zone.name,
                shape_type=zone.shape_type,
                latitude=zone.latitude,
                longitude=zone.longitude,
                radius_m=zone.radius_m,
                points_json=json.dumps(zone.points) if zone.points else None,
                notify_on_enter=zone.notify_on_enter,
                notify_on_exit=zone.notify_on_exit,
                enabled=zone.enabled,
                charging_tier_id=zone.charging_tier_id,
            )
            session.add(row)
            await session.commit()
            zone.id = row.id
            return zone

    async def delete_zone(self, zone_id: int) -> bool:
        """Delete a zone by ID."""
        async with self._session_factory() as session:
            row = await session.get(ZoneRow, zone_id)
            if not row:
                return False
            await session.delete(row)
            await session.commit()
            return True
