"""Trip segmentation must ignore partial status payloads (issue #33)."""

from datetime import datetime, timedelta

from leapconnect.domain.telemetry.models import VehicleSnapshot
from leapconnect.domain.trips.analysis import (
    build_local_trip_payload,
    build_trip_row,
    flatten_trip_rows,
)

T0 = datetime(2026, 10, 1, 17, 4)


def _snap(minute: int, **kwargs) -> VehicleSnapshot:
    defaults = {
        "battery_soc": 80,
        "battery_dump_energy": 40000.0,
        "drive_total_mileage": 3100,
        "vehicle_latitude": 41.27,
        "vehicle_longitude": 15.94,
        "drive_speed": 50,
        "drive_is_parked": False,
    }
    defaults.update(kwargs)
    ts = T0 + timedelta(minutes=minute)
    return VehicleSnapshot(vin="VIN", timestamp=ts, **defaults)


# Partial payload returned by the vehicle: odometer/SOC/energy/GPS all zeroed.
GLITCH = {
    "battery_soc": 0,
    "battery_dump_energy": None,
    "drive_total_mileage": 0,
    "vehicle_latitude": 0.0,
    "vehicle_longitude": 0.0,
}


def test_zeroed_start_snapshot_is_not_used_as_boundary():
    segment = [
        _snap(0, **GLITCH),
        _snap(1, drive_total_mileage=3100, battery_dump_energy=40000.0),
        _snap(17, drive_total_mileage=3105, battery_dump_energy=39200.0),
    ]
    row = build_trip_row(segment)

    assert row is not None
    assert row["travelMile"] == 5000
    assert row["energyConsumed"] == 800
    assert row["startSoc"] == 80
    assert (row["startLat"], row["startLng"]) == (41.27, 15.94)


def test_zeroed_end_snapshot_is_not_used_as_boundary():
    segment = [
        _snap(0, drive_total_mileage=3100),
        _snap(10, drive_total_mileage=3104, battery_soc=79),
        _snap(17, drive_speed=0, drive_is_parked=True, **GLITCH),
    ]
    row = build_trip_row(segment)

    assert row is not None
    assert row["travelMile"] == 4000
    assert row["endSoc"] == 79
    assert (row["endLat"], row["endLng"]) == (41.27, 15.94)


def test_payload_totals_ignore_glitch():
    snapshots = [
        _snap(0, drive_speed=0, drive_is_parked=True, drive_total_mileage=3100),
        _snap(1, drive_speed=None, drive_is_parked=None, **GLITCH),
        _snap(5, drive_total_mileage=3102),
        _snap(17, drive_total_mileage=3105),
        _snap(18, drive_speed=0, drive_is_parked=True, drive_total_mileage=3105),
    ]
    payload = build_local_trip_payload(snapshots)

    # The glitch is the segment anchor, so the first valid odometer is 3102.
    assert payload["total_mileage"] == 3.0
    assert [t["travelMile"] for t in flatten_trip_rows(payload)] == [3000]


def test_segment_without_any_valid_odometer_is_dropped():
    segment = [_snap(0, **GLITCH), _snap(10, **GLITCH)]
    assert build_trip_row(segment) is None
