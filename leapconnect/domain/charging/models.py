"""Charging cost entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChargingPriceTier:
    """A pricing tier for charging sessions."""

    id: str = ""
    label: str = ""
    price_kwh: float = 0.0
    enabled: bool = True


@dataclass
class ChargingTimeBand:
    """A time-of-use band with schedule and price."""

    id: int | None = None
    tier_id: str = "home_grid"
    name: str = ""
    price_kwh: float = 0.0
    schedule: list | None = (
        None  # [{days: [0-6], start_hour, start_min, end_hour, end_min}]
    )
    color: str | None = None
    position: int = 0

    def __post_init__(self):
        if self.schedule is None:
            self.schedule = []


@dataclass
class ChargingSessionCost:
    """Cost record for a single charging session (aggregate root)."""

    id: int | None = None
    vin: str = ""
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    tier_id: str = ""
    time_band_id: int | None = None
    energy_kwh: float | None = None
    peak_power_kw: float | None = None
    cost: float | None = None
    note: str | None = None
    zone_name: str | None = None  # zone the charge happened in (analytics)
