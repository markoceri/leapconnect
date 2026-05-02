"""Vehicle history repository — port (interface).

Defines the abstract contract for persisting and querying vehicle status
snapshots.  Concrete adapters (e.g. SQLAlchemy/SQLite) implement this.
"""

from __future__ import annotations

import abc

from models import VehicleSnapshot


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
    ) -> list[VehicleSnapshot]:
        """Return snapshots for *vin* over the last *days* days.

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
