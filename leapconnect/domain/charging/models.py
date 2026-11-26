"""Charging cost entities."""

from __future__ import annotations

from dataclasses import dataclass, field
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
    # Where the car charged (its GPS, else the charger's): the charge sites map
    latitude: float | None = None
    longitude: float | None = None
    # Entered by hand: the automatic recalculations leave them alone
    cost_manual: bool = False
    energy_manual: bool = False
    # Price per kWh entered by hand: the cost follows the energy
    manual_price_kwh: float | None = None
    # Imported from a charging provider (e.g. "evdc"): its energy and cost are
    # the billed ones, kept by the automatic recalculations
    external_source: str | None = None
    external_id: str | None = None
    # The provider account it was imported with, and the charging point used
    # (its details are in the stations cache, see ``domain.charging.stations``)
    provider_account_id: int | None = None
    evse_id: str | None = None
    # Unlinked from a provider session by the user: not linked again by the
    # automatic import (can still be linked by hand)
    auto_link_disabled: bool = False
    # Extra costs (session fee, idle fee, parking, ...), in display order
    extras: list[ChargingSessionExtra] = field(default_factory=list)

    @property
    def energy_locked(self) -> bool:
        """Energy not re-measured: entered by hand or billed by a provider."""
        return self.energy_manual or self.external_source is not None

    @property
    def cost_locked(self) -> bool:
        """Cost not re-priced with the tier: entered by hand (a total) or
        billed by a provider."""
        return self.cost_manual or self.external_source is not None

    @property
    def extras_total(self) -> float | None:
        """Extras counted in the session cost; ``None`` when there are none."""
        amounts = [e.cost for e in self.extras if e.included and e.cost is not None]
        return round(sum(amounts), 4) if amounts else None

    @property
    def total_cost(self) -> float | None:
        """Energy cost plus the extras counted in it."""
        if self.cost is None and self.extras_total is None:
            return None
        return round((self.cost or 0) + (self.extras_total or 0), 4)


@dataclass
class ChargingSessionExtra:
    """An extra cost of a charging session, on top of the energy.

    ``kind`` picks how ``cost`` is computed (see ``domain.charging.extras``):
    a fixed ``amount`` (negative for a discount), a ``rate`` per time unit over
    a span of the session, a ``rate`` per kWh, or a percentage of the energy
    cost. ``minutes`` and ``cost`` are the computed result; ``cost`` is
    ``None`` while it can't be computed yet (e.g. the car is still plugged in).
    """

    id: int | None = None
    kind: str = "fixed"
    label: str = ""
    included: bool = True  # counted in the session cost
    amount: float | None = None
    rate: float | None = None
    # Time-based: rate per time unit, billed exactly or per started unit,
    # from a start point (+ offset, e.g. a grace period) to an end point or for
    # a duration entered by hand, up to an optional cap
    time_unit: str = "hour"
    billing: str = "exact"
    start_ref: str = "charge_end"
    start_offset_min: int = 0
    end_ref: str = "unplug"
    duration_min: int | None = None
    cap: float | None = None
    minutes: int | None = None
    cost: float | None = None
    # Provider it comes from (e.g. "evdc"), replaced at each import; None =
    # entered by the user
    source: str | None = None


@dataclass
class ChargingProviderAccount:
    """An account of a charging provider (an e-mobility service provider such
    as EVDC) connected to import its billed sessions.

    ``credentials`` is what the provider's adapter needs to log in again
    (device keys, tokens, ...): opaque here, encrypted at rest; never a
    password.
    """

    id: int | None = None
    provider: str = ""  # its type, e.g. "evdc"
    username: str = ""  # the account it logs in as, shown in the UI
    credentials: dict[str, str] = field(default_factory=dict)
    auto_sync: bool = True
    last_sync: str | None = None  # ISO timestamp
    last_error: str | None = None
