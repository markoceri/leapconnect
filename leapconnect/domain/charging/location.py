"""Charge-location resolution: which zone and price tier a charge belongs to.

Shared by the live charge-start handler and the bulk "calculate missing costs"
action, so both apply the same precedence.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from leapconnect.domain.zones import Zone, zone_contains

# Battery charge_state reported for a DC fast charge.
DC_CHARGE_STATE = 2


@dataclass(frozen=True)
class ChargeLocation:
    """Where a charge happened and the tier that can be inferred from it.

    ``zone_name`` is the first enabled zone containing the position (a place,
    independent of pricing). ``tier_id`` is ``None`` when the tier cannot be
    determined with confidence — callers decide whether to fall back or skip.
    """

    zone_name: str | None = None
    tier_id: str | None = None


def resolve_charge_location(
    zones: Iterable[Zone],
    lat: float | None,
    lon: float | None,
    *,
    is_dc: bool = False,
) -> ChargeLocation:
    """Resolve zone and tier with precedence: DC → public_dc, else zone tier."""
    zone_name: str | None = None
    zone_tier: str | None = None
    if lat and lon:
        for zone in zones:
            if not zone.enabled or not zone_contains(zone, lat, lon):
                continue
            if zone_name is None:
                zone_name = zone.name
            if zone_tier is None and zone.charging_tier_id:
                zone_tier = zone.charging_tier_id
            if zone_name and zone_tier:
                break
    tier_id = "public_dc" if is_dc else zone_tier
    return ChargeLocation(zone_name=zone_name, tier_id=tier_id)
