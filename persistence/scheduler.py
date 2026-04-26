"""Background scheduler for periodic vehicle data collection.

Runs as an asyncio task inside the FastAPI process. Polls all connected
vehicles at a configurable interval and persists snapshots via the
repository port.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from leapmotor_api.async_client import AsyncLeapmotorApiClient
    from leapmotor_api.models import Vehicle

    from .repository import VehicleHistoryRepository, VehicleSnapshot

_LOGGER = logging.getLogger(__name__)

DEFAULT_INTERVAL_MINUTES = 15
MIN_INTERVAL_MINUTES = 1
MAX_INTERVAL_MINUTES = 1440  # 24 h


@dataclass
class SchedulerSettings:
    """User-facing scheduler configuration."""

    enabled: bool = False
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES


class VehicleDataScheduler:
    """Periodically polls vehicle status and saves snapshots."""

    def __init__(
        self,
        repo: VehicleHistoryRepository,
    ) -> None:
        self._repo = repo
        self._settings = SchedulerSettings()
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._last_run: datetime | None = None
        self._last_error: str | None = None
        self._total_runs: int = 0
        self._total_errors: int = 0

        # Injected at runtime by main.py when the user logs in
        self._client: AsyncLeapmotorApiClient | None = None
        self._vehicles: list[Vehicle] = []

    # -- public API ----------------------------------------------------------

    @property
    def settings(self) -> SchedulerSettings:
        return self._settings

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def status_dict(self) -> dict:
        return {
            "enabled": self._settings.enabled,
            "interval_minutes": self._settings.interval_minutes,
            "is_running": self.is_running,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "last_error": self._last_error,
            "total_runs": self._total_runs,
            "total_errors": self._total_errors,
        }

    def set_client(self, client: AsyncLeapmotorApiClient | None, vehicles: list[Vehicle]) -> None:
        self._client = client
        self._vehicles = vehicles

    def update_settings(self, *, enabled: bool | None = None, interval_minutes: int | None = None) -> SchedulerSettings:
        if interval_minutes is not None:
            interval_minutes = max(MIN_INTERVAL_MINUTES, min(MAX_INTERVAL_MINUTES, interval_minutes))
            self._settings.interval_minutes = interval_minutes
        if enabled is not None:
            self._settings.enabled = enabled

        # Apply change immediately
        if self._settings.enabled:
            self._ensure_running()
        else:
            self._request_stop()

        return self._settings

    def start(self) -> None:
        if self._settings.enabled:
            self._ensure_running()

    async def stop(self) -> None:
        self._request_stop()
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
        self._task = None

    # -- internals -----------------------------------------------------------

    def _ensure_running(self) -> None:
        if self.is_running:
            # Wake the loop so it picks up new interval immediately
            self._stop_event.set()
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._loop(), name="vehicle-data-scheduler")

    def _request_stop(self) -> None:
        self._stop_event.set()

    async def _loop(self) -> None:
        _LOGGER.info("Scheduler started (interval=%d min)", self._settings.interval_minutes)
        try:
            while self._settings.enabled:
                await self._poll_all()
                # Wait for interval or until settings change
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self._settings.interval_minutes * 60,
                    )
                    # Event was set — either settings changed or stop requested
                    self._stop_event.clear()
                except asyncio.TimeoutError:
                    # Normal timeout — time for next poll
                    pass
        except asyncio.CancelledError:
            pass
        finally:
            _LOGGER.info("Scheduler stopped")

    async def _poll_all(self) -> None:
        if not self._client or not self._vehicles:
            _LOGGER.debug("Scheduler: no client or vehicles, skipping")
            return

        from .repository import VehicleSnapshot

        _LOGGER.info("Scheduler: polling %d vehicle(s)", len(self._vehicles))
        self._total_runs += 1
        self._last_run = datetime.utcnow()
        self._last_error = None

        for vehicle in self._vehicles:
            try:
                status = await self._client.get_vehicle_status(vehicle)
                snapshot = VehicleSnapshot(
                    vin=vehicle.vin,
                    timestamp=status.collect_time or datetime.utcnow(),
                    battery_soc=status.battery.soc,
                    expected_mileage=status.battery.expected_mileage,
                    total_mileage=status.driving.total_mileage,
                    energy_kwh=status.battery.dump_energy_kwh,
                    outdoor_temp=status.climate.outdoor_temp,
                    is_charging=status.battery.is_charging,
                    latitude=status.location.latitude,
                    longitude=status.location.longitude,
                    charge_state=status.battery.charge_state,
                    speed=status.driving.speed,
                )
                await self._repo.save_snapshot(snapshot)
                _LOGGER.info("Scheduler: saved snapshot for %s (SOC=%s%%)", vehicle.vin, status.battery.soc)
            except Exception as exc:
                self._total_errors += 1
                self._last_error = f"{vehicle.vin}: {exc}"
                _LOGGER.exception("Scheduler: failed to poll %s", vehicle.vin)
