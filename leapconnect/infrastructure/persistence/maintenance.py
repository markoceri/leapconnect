"""Plan items, records, community repos and packs (SQLAlchemy/SQLite)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select

from leapconnect.application.ports.repositories import (
    MaintenanceRepository,
)
from leapconnect.infrastructure.persistence.base import SqlRepositoryBase
from leapconnect.infrastructure.persistence.tables import (
    MaintenancePackRow,
    MaintenancePlanItemRow,
    MaintenanceRecordRow,
    MaintenanceRepoRow,
)


class SqlMaintenanceRepository(SqlRepositoryBase, MaintenanceRepository):
    """Plan items, records, community repos and packs."""

    async def get_maintenance_plan(self, vin: str) -> list:
        """Return all plan items for a vehicle, ordered by priority then category."""
        from leapconnect.domain.maintenance.models import MaintenancePlanItem

        priority_order = {"urgent": 0, "important": 1, "routine": 2}
        async with self._session_factory() as session:
            stmt = (
                select(MaintenancePlanItemRow)
                .where(
                    MaintenancePlanItemRow.vin == vin,
                    MaintenancePlanItemRow.enabled == True,  # noqa: E712
                )
                .order_by(MaintenancePlanItemRow.category, MaintenancePlanItemRow.id)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            items = [
                MaintenancePlanItem(
                    id=r.id,
                    vin=r.vin,
                    service_type=r.service_type,
                    label=r.label,
                    category=r.category,
                    interval_km=r.interval_km,
                    interval_months=r.interval_months,
                    trigger_mode=r.trigger_mode,
                    priority=r.priority,
                    last_done_km=r.last_done_km,
                    last_done_date=r.last_done_date,
                    enabled=r.enabled,
                    notes=r.notes,
                    source=r.source,
                    source_ref=r.source_ref,
                )
                for r in rows
            ]
            # Sort: urgent first, then important, then routine
            items.sort(key=lambda i: priority_order.get(i.priority, 99))
            return items

    async def upsert_maintenance_plan_item(self, vin: str, item) -> None:
        """Insert or update a single plan item (keyed by vin + service_type)."""
        async with self._session_factory() as session:
            stmt = select(MaintenancePlanItemRow).where(
                MaintenancePlanItemRow.vin == vin,
                MaintenancePlanItemRow.service_type == item.service_type,
            )
            result = await session.execute(stmt)
            # .first() (not scalar_one_or_none) so a legacy duplicate row never
            # crashes the upsert; the unique index prevents new duplicates.
            existing = result.scalars().first()

            if existing:
                # Update fields that are provided
                if item.label:
                    existing.label = item.label
                if item.category:
                    existing.category = item.category
                if item.interval_km is not None:
                    existing.interval_km = item.interval_km
                if item.interval_months is not None:
                    existing.interval_months = item.interval_months
                if item.trigger_mode:
                    existing.trigger_mode = item.trigger_mode
                if item.priority:
                    existing.priority = item.priority
                if item.last_done_km is not None:
                    existing.last_done_km = item.last_done_km
                if item.last_done_date is not None:
                    existing.last_done_date = item.last_done_date
                if item.enabled is not None:
                    existing.enabled = item.enabled
                if item.notes is not None:
                    existing.notes = item.notes
                if getattr(item, "source", None):
                    existing.source = item.source
                if getattr(item, "source_ref", None) is not None:
                    existing.source_ref = item.source_ref
            else:
                row = MaintenancePlanItemRow(
                    vin=vin,
                    service_type=item.service_type,
                    label=item.label or item.service_type,
                    category=item.category or "other",
                    interval_km=item.interval_km,
                    interval_months=item.interval_months,
                    trigger_mode=item.trigger_mode or "or",
                    priority=item.priority or "routine",
                    last_done_km=item.last_done_km,
                    last_done_date=item.last_done_date,
                    enabled=item.enabled if item.enabled is not None else True,
                    notes=item.notes,
                    source=getattr(item, "source", None) or "catalog",
                    source_ref=getattr(item, "source_ref", None),
                )
                session.add(row)

            await session.commit()

    async def set_plan_item_last_done(
        self, vin: str, service_type: str, *, last_done_km, last_done_date
    ) -> None:
        """Set a plan item's last_done fields explicitly (``None`` clears them).

        Unlike :meth:`upsert_maintenance_plan_item`, this assigns the values
        unconditionally so the fields can be reset to NULL (e.g. after the last
        service record for an item is deleted).
        """
        async with self._session_factory() as session:
            stmt = select(MaintenancePlanItemRow).where(
                MaintenancePlanItemRow.vin == vin,
                MaintenancePlanItemRow.service_type == service_type,
            )
            row = (await session.execute(stmt)).scalars().first()
            if row is not None:
                row.last_done_km = last_done_km
                row.last_done_date = last_done_date
                await session.commit()

    async def get_maintenance_records(
        self, vin: str, *, service_type: str | None = None, limit: int | None = 20
    ) -> list:
        """Return completed maintenance records, newest first (``limit=None`` = all)."""
        from leapconnect.domain.maintenance.models import MaintenanceRecord

        async with self._session_factory() as session:
            conditions = [MaintenanceRecordRow.vin == vin]
            if service_type:
                conditions.append(MaintenanceRecordRow.service_type == service_type)
            stmt = (
                select(MaintenanceRecordRow)
                .where(*conditions)
                .order_by(MaintenanceRecordRow.timestamp.desc())
            )
            if limit is not None:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                MaintenanceRecord(
                    id=r.id,
                    vin=r.vin,
                    service_type=r.service_type,
                    label=r.label,
                    timestamp=r.timestamp,
                    mileage_km=r.mileage_km,
                    cost=r.cost,
                    provider=r.provider,
                    notes=r.notes,
                )
                for r in rows
            ]

    async def save_maintenance_record(self, record) -> None:
        """Persist a completed maintenance record."""
        async with self._session_factory() as session:
            row = MaintenanceRecordRow(
                vin=record.vin,
                service_type=record.service_type,
                label=record.label,
                timestamp=record.timestamp or datetime.now(UTC),
                mileage_km=record.mileage_km,
                cost=record.cost,
                provider=record.provider,
                notes=record.notes,
            )
            session.add(row)
            await session.commit()
            record.id = row.id

    async def update_maintenance_record(
        self,
        record_id: int,
        *,
        timestamp=None,
        mileage_km=None,
        cost=None,
        provider=None,
        notes=None,
    ) -> object | None:
        """Update an existing record's editable fields. Returns it, or None."""
        from leapconnect.domain.maintenance.models import MaintenanceRecord

        async with self._session_factory() as session:
            row = await session.get(MaintenanceRecordRow, record_id)
            if row is None:
                return None
            if timestamp is not None:
                row.timestamp = timestamp
            row.mileage_km = mileage_km
            row.cost = cost
            row.provider = provider
            row.notes = notes
            await session.commit()
            return MaintenanceRecord(
                id=row.id,
                vin=row.vin,
                service_type=row.service_type,
                label=row.label,
                timestamp=row.timestamp,
                mileage_km=row.mileage_km,
                cost=row.cost,
                provider=row.provider,
                notes=row.notes,
            )

    async def delete_maintenance_record(self, record_id: int) -> None:
        """Delete a maintenance record by id."""
        async with self._session_factory() as session:
            row = await session.get(MaintenanceRecordRow, record_id)
            if row:
                await session.delete(row)
                await session.commit()

    async def get_maintenance_record(self, record_id: int) -> object | None:
        """Get a single maintenance record by id."""
        from leapconnect.domain.maintenance.models import MaintenanceRecord

        async with self._session_factory() as session:
            row = await session.get(MaintenanceRecordRow, record_id)
            if row is None:
                return None
            return MaintenanceRecord(
                id=row.id,
                vin=row.vin,
                service_type=row.service_type,
                label=row.label,
                timestamp=row.timestamp,
                mileage_km=row.mileage_km,
                cost=row.cost,
                provider=row.provider,
                notes=row.notes,
            )

    async def delete_maintenance_plan_item(self, vin: str, service_type: str) -> None:
        """Delete a single plan item (keyed by vin + service_type)."""
        async with self._session_factory() as session:
            stmt = select(MaintenancePlanItemRow).where(
                MaintenancePlanItemRow.vin == vin,
                MaintenancePlanItemRow.service_type == service_type,
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                await session.delete(row)
                await session.commit()

    # -- maintenance repos & packs -------------------------------------------

    @staticmethod
    def _repo_from_row(row: MaintenanceRepoRow):
        from leapconnect.domain.maintenance.models import MaintenanceRepo

        return MaintenanceRepo(
            id=row.id,
            type=row.type,
            url=row.url,
            name=row.name,
            author=row.author,
            description=row.description,
            branch=row.branch,
            added_at=row.added_at,
            last_fetched_at=row.last_fetched_at,
            etag=row.etag,
            status=row.status,
            manifest=json.loads(row.manifest_json) if row.manifest_json else None,
        )

    async def list_maintenance_repos(self) -> list:
        async with self._session_factory() as session:
            stmt = select(MaintenanceRepoRow).order_by(MaintenanceRepoRow.id)
            result = await session.execute(stmt)
            return [self._repo_from_row(r) for r in result.scalars().all()]

    async def get_maintenance_repo(self, repo_id: int):
        async with self._session_factory() as session:
            row = await session.get(MaintenanceRepoRow, repo_id)
            return self._repo_from_row(row) if row else None

    async def get_maintenance_repo_by_url(self, url: str):
        async with self._session_factory() as session:
            stmt = select(MaintenanceRepoRow).where(MaintenanceRepoRow.url == url)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return self._repo_from_row(row) if row else None

    async def save_maintenance_repo(self, repo):
        """Insert or update a repo (keyed by id when set, else by url)."""
        manifest_json = json.dumps(repo.manifest) if repo.manifest is not None else None
        async with self._session_factory() as session:
            row = None
            if repo.id is not None:
                row = await session.get(MaintenanceRepoRow, repo.id)
            if row is None:
                stmt = select(MaintenanceRepoRow).where(
                    MaintenanceRepoRow.url == repo.url
                )
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()

            if row is None:
                row = MaintenanceRepoRow(
                    type=repo.type,
                    url=repo.url,
                    added_at=repo.added_at or datetime.now(UTC),
                )
                session.add(row)

            row.type = repo.type
            row.name = repo.name
            row.author = repo.author
            row.description = repo.description
            row.branch = repo.branch
            row.last_fetched_at = repo.last_fetched_at
            row.etag = repo.etag
            row.status = repo.status
            row.manifest_json = manifest_json

            await session.commit()
            repo.id = row.id
            return repo

    async def delete_maintenance_repo(self, repo_id: int) -> None:
        """Delete a repo and all packs cached from it."""
        async with self._session_factory() as session:
            row = await session.get(MaintenanceRepoRow, repo_id)
            if row:
                await session.delete(row)
            pack_stmt = select(MaintenancePackRow).where(
                MaintenancePackRow.repo_id == repo_id
            )
            pack_result = await session.execute(pack_stmt)
            for pack in pack_result.scalars().all():
                await session.delete(pack)
            await session.commit()

    @staticmethod
    def _pack_from_row(row: MaintenancePackRow):
        from leapconnect.domain.maintenance.models import MaintenancePack

        return MaintenancePack(
            id=row.id,
            repo_id=row.repo_id,
            slug=row.slug,
            name=row.name,
            version=row.version,
            author=row.author,
            model_compat=json.loads(row.model_compat) if row.model_compat else None,
            payload=json.loads(row.payload_json) if row.payload_json else None,
            fetched_at=row.fetched_at,
        )

    async def list_maintenance_packs(self, repo_id: int | None = None) -> list:
        async with self._session_factory() as session:
            stmt = select(MaintenancePackRow)
            if repo_id is not None:
                stmt = stmt.where(MaintenancePackRow.repo_id == repo_id)
            stmt = stmt.order_by(MaintenancePackRow.id)
            result = await session.execute(stmt)
            return [self._pack_from_row(r) for r in result.scalars().all()]

    async def get_maintenance_pack(self, pack_id: int):
        async with self._session_factory() as session:
            row = await session.get(MaintenancePackRow, pack_id)
            return self._pack_from_row(row) if row else None

    async def save_maintenance_pack(self, pack):
        """Insert or update a cached pack (keyed by id, or repo_id + slug)."""
        model_compat_json = (
            json.dumps(pack.model_compat) if pack.model_compat is not None else None
        )
        payload_json = json.dumps(pack.payload or {})
        async with self._session_factory() as session:
            row = None
            if pack.id is not None:
                row = await session.get(MaintenancePackRow, pack.id)
            if row is None:
                stmt = select(MaintenancePackRow).where(
                    MaintenancePackRow.repo_id == pack.repo_id,
                    MaintenancePackRow.slug == pack.slug,
                )
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()

            if row is None:
                row = MaintenancePackRow(repo_id=pack.repo_id, slug=pack.slug)
                session.add(row)

            row.repo_id = pack.repo_id
            row.slug = pack.slug
            row.name = pack.name
            row.version = pack.version
            row.author = pack.author
            row.model_compat = model_compat_json
            row.payload_json = payload_json
            row.fetched_at = pack.fetched_at or datetime.now(UTC)

            await session.commit()
            pack.id = row.id
            return pack

    async def delete_maintenance_pack(self, pack_id: int) -> None:
        async with self._session_factory() as session:
            row = await session.get(MaintenancePackRow, pack_id)
            if row:
                await session.delete(row)
                await session.commit()
