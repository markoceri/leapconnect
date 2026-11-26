"""Charging points and the places where the vehicle charged (pure domain).

A charging provider knows the charging points of its network: where they
are, who runs them, their power and plugs, and — when asked live — their
status and price. The ones a session was billed on are cached with the
session's ``evse_id``; the charge sites group the sessions by place.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from leapconnect.domain.charging.models import ChargingSessionCost
from leapconnect.domain.zones.geometry import haversine_distance_m

# Sessions this close together are the same charge site
SITE_RADIUS_M = 100.0


@dataclass(frozen=True)
class ChargingStation:
    """A charging point (EVSE: one connector) of a provider's network."""

    provider: str
    evse_id: str
    name: str | None = None
    operator: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    max_power_kw: float | None = None
    is_dc: bool | None = None
    plugs: tuple[str, ...] = ()
    is_open_24h: bool | None = None
    # Live, only when read from the provider (not cached)
    status: str | None = None  # Available, Occupied, OutOfService, ...
    price: float | None = None
    price_unit: str | None = None  # e.g. "kWh"
    currency: str | None = None
    distance_m: float | None = None  # from the searched point


@dataclass
class ChargeSite:
    """A place where the vehicle charged, and its sessions there."""

    latitude: float
    longitude: float
    sessions: int = 0
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    energy_kwh: float = 0.0
    cost: float = 0.0
    zone_name: str | None = None
    tier_id: str | None = None  # of the latest session
    # Charging points billed there (latest first)
    stations: list[ChargingStation] = field(default_factory=list)


def group_charge_sites(
    records: Iterable[ChargingSessionCost],
    stations: Mapping[tuple[str, str], ChargingStation] | None = None,
    radius_m: float = SITE_RADIUS_M,
) -> list[ChargeSite]:
    """Group the sessions with a position by place, latest site first.

    A session joins the first site (by its latest session) within
    ``radius_m``; a site's position is the one of its first session.
    ``stations`` (by ``(provider, evse_id)``) adds the charging points the
    sessions were billed on.
    """
    stations = stations or {}
    located = sorted(
        (r for r in records if r.latitude is not None and r.longitude is not None),
        key=lambda r: r.start_ts or datetime.min,
        reverse=True,
    )
    sites: list[ChargeSite] = []
    for r in located:
        site = next(
            (
                s
                for s in sites
                if haversine_distance_m(
                    s.latitude, s.longitude, r.latitude, r.longitude
                )
                <= radius_m
            ),
            None,
        )
        if site is None:
            site = ChargeSite(
                latitude=r.latitude,
                longitude=r.longitude,
                last_ts=r.start_ts,
                zone_name=r.zone_name,
                tier_id=r.tier_id,
            )
            sites.append(site)
        site.sessions += 1
        site.first_ts = r.start_ts
        site.energy_kwh = round(site.energy_kwh + (r.energy_kwh or 0), 3)
        site.cost = round(site.cost + (r.total_cost or 0), 4)
        site.zone_name = site.zone_name or r.zone_name
        station = (
            stations.get((r.external_source, r.evse_id))
            if r.external_source and r.evse_id
            else None
        )
        if station is not None and station not in site.stations:
            site.stations.append(station)
    return sites


def unique_by_evse(stations: Sequence[ChargingStation]) -> list[ChargingStation]:
    """The charging points without repeats (the same network read through
    several accounts), in order."""
    seen: set[tuple[str, str]] = set()
    result = []
    for s in stations:
        key = (s.provider, s.evse_id)
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result
