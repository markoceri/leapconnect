"""Normalise partial vehicle status payloads returned by the Leapmotor API.

The vehicle occasionally reports a partial status where odometer, SOC,
energy and GPS come back as 0.  Those zeros are not real readings: stored
as-is they turn into multi-thousand-km trips, fake "battery low" events,
odometer resets in Home Assistant and a 0 odometer sent to ABRP.  They are
turned into ``None`` ("unknown") as soon as the status is fetched, so every
consumer sees a missing value instead of a wrong one.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from leapmotor_api.async_client import AsyncLeapmotorApiClient
    from leapmotor_api.models import Vehicle, VehicleStatus

_LOGGER = logging.getLogger(__name__)


def sanitize_vehicle_status(status: VehicleStatus) -> VehicleStatus:
    """Replace zeroed readings of a partial payload with ``None`` (in place)."""
    driving, battery, location = status.driving, status.battery, status.location

    # An odometer of 0 is never a real reading: it marks a partial payload.
    partial = driving.total_mileage is not None and driving.total_mileage <= 0
    if partial:
        driving.total_mileage = None
        # A 0% SOC alone could be a genuinely empty battery; only drop it
        # when the payload is known to be partial.
        if battery.soc == 0:
            battery.soc = None
        if battery.precise_soc == 0:
            battery.precise_soc = None
        _LOGGER.debug("Partial vehicle status payload, zeroed readings dropped")

    if battery.dump_energy == 0:
        battery.dump_energy = None

    if (location.latitude, location.longitude) == (0, 0):
        location.latitude = None
        location.longitude = None

    return status


async def fetch_vehicle_status(
    client: AsyncLeapmotorApiClient, vehicle: Vehicle
) -> VehicleStatus:
    """Fetch the vehicle status from the API and sanitise it."""
    return sanitize_vehicle_status(await client.get_vehicle_status(vehicle))
