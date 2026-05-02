"""Persistence layer data models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

DEFAULT_INTERVAL_MINUTES = 15


@dataclass(frozen=True, slots=True)
class VehicleSnapshot:
    """A single point-in-time snapshot of vehicle telemetry."""

    vin: str
    timestamp: datetime
    battery_soc: int | None = None
    expected_mileage: int | None = None
    total_mileage: int | None = None
    energy_kwh: float | None = None
    outdoor_temp: int | None = None
    is_charging: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    charge_state: int | None = None
    speed: int | None = None


@dataclass
class SchedulerSettings:
    """User-facing scheduler configuration."""

    enabled: bool = False
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES
