"""Vehicle history repository — port (interface).

Defines the abstract contract for persisting and querying vehicle status
snapshots.  Concrete adapters (e.g. SQLAlchemy/SQLite) implement this.
"""

from __future__ import annotations

import abc

from models import VehicleEvent, VehicleSnapshot


class VehicleHistoryRepository(abc.ABC):
    """Abstract port for vehicle history persistence."""

    @abc.abstractmethod
    async def save_snapshot(self, snapshot: VehicleSnapshot) -> None:
        """Persist a single snapshot."""

    @abc.abstractmethod
    async def get_history(
        self,
        vin: str,
        *,
        days: int = 30,
        from_date: str | None = None,
        to_date: str | None = None,
        max_points: int | None = None,
    ) -> list[VehicleSnapshot]:
        """Return snapshots for *vin* over the last *days* days.

        If from_date/to_date are provided (YYYY-MM-DD), they take precedence
        over the days parameter.

        If max_points is specified, the result is downsampled to at most that
        many snapshots while preserving state-transition boundaries.

        Ordered by timestamp.
        """

    @abc.abstractmethod
    async def get_daily_summary(
        self,
        vin: str,
        *,
        days: int = 30,
    ) -> list[dict]:
        """Return one aggregated row per day for *vin*.

        Each dict contains at least:
        - date (str YYYY-MM-DD)
        - min_soc, max_soc, avg_soc
        - min_range, max_range
        - km_driven (max_mileage - min_mileage for the day)
        - energy_delta (estimated energy consumed)
        - avg_temp
        - charge_sessions (count of snapshots where is_charging is True)
        """

    @abc.abstractmethod
    async def init_db(self) -> None:
        """Create tables / run migrations if necessary."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Release resources."""

    @abc.abstractmethod
    async def save_event(self, event: VehicleEvent) -> None:
        """Persist a single state-transition event."""

    @abc.abstractmethod
    async def get_events(
        self,
        vin: str,
        *,
        days: int = 30,
        event_type: str | None = None,
    ) -> list[VehicleEvent]:
        """Return events for *vin* over the last *days* days."""

    # -- maintenance ----------------------------------------------------------

    @abc.abstractmethod
    async def get_maintenance_plan(self, vin: str) -> list:
        """Return all plan items for a vehicle, ordered by priority then category."""

    @abc.abstractmethod
    async def upsert_maintenance_plan_item(self, vin: str, item) -> None:
        """Insert or update a single plan item (keyed by vin + service_type)."""

    @abc.abstractmethod
    async def set_plan_item_last_done(
        self, vin: str, service_type: str, *, last_done_km, last_done_date
    ) -> None:
        """Set a plan item's last_done fields explicitly (``None`` clears them)."""

    @abc.abstractmethod
    async def get_maintenance_records(
        self, vin: str, *, service_type: str | None = None, limit: int | None = 20
    ) -> list:
        """Return completed maintenance records, newest first (``limit=None`` = all)."""

    @abc.abstractmethod
    async def save_maintenance_record(self, record) -> None:
        """Persist a completed maintenance record."""

    @abc.abstractmethod
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

    @abc.abstractmethod
    async def delete_maintenance_record(self, record_id: int) -> None:
        """Delete a maintenance record by id."""

    @abc.abstractmethod
    async def get_maintenance_record(self, record_id: int) -> object | None:
        """Get a single maintenance record by id."""

    @abc.abstractmethod
    async def delete_maintenance_plan_item(self, vin: str, service_type: str) -> None:
        """Delete a single plan item (keyed by vin + service_type)."""

    # -- maintenance repos & packs -------------------------------------------

    @abc.abstractmethod
    async def list_maintenance_repos(self) -> list:
        """Return all community repositories the user has added."""

    @abc.abstractmethod
    async def get_maintenance_repo(self, repo_id: int) -> object | None:
        """Get a single repository by id."""

    @abc.abstractmethod
    async def get_maintenance_repo_by_url(self, url: str) -> object | None:
        """Get a single repository by its URL."""

    @abc.abstractmethod
    async def save_maintenance_repo(self, repo) -> object:
        """Insert or update a repository; returns it with its id populated."""

    @abc.abstractmethod
    async def delete_maintenance_repo(self, repo_id: int) -> None:
        """Delete a repository and all packs cached from it."""

    @abc.abstractmethod
    async def list_maintenance_packs(self, repo_id: int | None = None) -> list:
        """Return cached packs, optionally filtered by repository."""

    @abc.abstractmethod
    async def get_maintenance_pack(self, pack_id: int) -> object | None:
        """Get a single cached pack by id."""

    @abc.abstractmethod
    async def save_maintenance_pack(self, pack) -> object:
        """Insert or update a cached pack; returns it with its id populated."""

    @abc.abstractmethod
    async def delete_maintenance_pack(self, pack_id: int) -> None:
        """Delete a cached pack by id."""
