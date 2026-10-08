"""Partial vehicle status payloads are normalised to "unknown" on fetch."""

from types import SimpleNamespace

from leapmotor_api.models import (
    BatteryStatus,
    DrivingStatus,
    LocationStatus,
    VehicleStatus,
)

from leapconnect.application.status_sanitizer import sanitize_vehicle_status
from leapconnect.application.vehicle_cache import VehicleStatusCache


def _status(
    *, mileage=3105, soc=80, precise_soc=80.4, energy=40000, lat=41.27, lng=15.94
):
    return VehicleStatus(
        battery=BatteryStatus(soc=soc, precise_soc=precise_soc, dump_energy=energy),
        driving=DrivingStatus(speed=0, total_mileage=mileage),
        location=LocationStatus(latitude=lat, longitude=lng),
    )


def test_valid_status_is_untouched():
    status = sanitize_vehicle_status(_status())

    assert status.driving.total_mileage == 3105
    assert status.battery.soc == 80
    assert status.battery.precise_soc == 80.4
    assert status.battery.dump_energy == 40000
    assert (status.location.latitude, status.location.longitude) == (41.27, 15.94)


def test_partial_payload_becomes_unknown():
    status = sanitize_vehicle_status(
        _status(mileage=0, soc=0, precise_soc=0, energy=0, lat=0.0, lng=0.0)
    )

    assert status.driving.total_mileage is None
    assert status.battery.soc is None
    assert status.battery.precise_soc is None
    assert status.battery.dump_energy is None
    assert (status.location.latitude, status.location.longitude) == (None, None)


def test_zero_soc_with_valid_odometer_is_kept():
    # A genuinely empty battery: the odometer is valid, so 0% is a real reading.
    status = sanitize_vehicle_status(_status(soc=0, precise_soc=0))

    assert status.battery.soc == 0
    assert status.battery.precise_soc == 0


def test_single_zero_coordinate_is_kept():
    # Only the exact (0, 0) pair marks a missing fix.
    status = sanitize_vehicle_status(_status(lat=0.0, lng=15.94))

    assert (status.location.latitude, status.location.longitude) == (0.0, 15.94)


class _FakeClient:
    def __init__(self, status):
        self._status = status

    async def get_vehicle_status(self, vehicle):
        return self._status


async def test_cache_returns_sanitized_status():
    cache = VehicleStatusCache()
    cache.set_client(_FakeClient(_status(mileage=0, soc=0, lat=0.0, lng=0.0)))

    status = await cache.get(SimpleNamespace(vin="VIN"))

    assert status.driving.total_mileage is None
    assert status.battery.soc is None
    assert status.location.latitude is None
