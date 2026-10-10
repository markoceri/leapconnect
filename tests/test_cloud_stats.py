"""Tests for the windowed Leapmotor cloud statistics."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from leapmotor_api.models import ConsumptionBreakdown, MileageEnergyHistory

from leapconnect.api import deps
from leapconnect.domain.telemetry.cloud_stats import MAX_WINDOW_DAYS, cloud_window

ROME = ZoneInfo("Europe/Rome")

# -- window ---------------------------------------------------------------------


def test_window_covers_whole_local_days_as_aware_utc():
    start, end = cloud_window(date(2026, 7, 1), date(2026, 7, 31), ROME)
    # Rome is UTC+2 in summer: local midnight is 22:00 UTC of the day before.
    assert start == datetime(2026, 6, 30, 22, 0, tzinfo=UTC)
    assert end == datetime(2026, 7, 31, 22, 0, tzinfo=UTC)


def test_single_day_window():
    start, end = cloud_window(date(2026, 1, 5), date(2026, 1, 5))
    assert (start, end) == (
        datetime(2026, 1, 5, tzinfo=UTC),
        datetime(2026, 1, 6, tzinfo=UTC),
    )


def test_inverted_window_is_rejected():
    with pytest.raises(ValueError, match="must not precede"):
        cloud_window(date(2026, 2, 1), date(2026, 1, 31))


def test_window_longer_than_limit_is_rejected():
    first = date(2025, 1, 1)
    cloud_window(first, date(2026, 1, 1))  # exactly MAX_WINDOW_DAYS days
    assert (date(2026, 1, 1) - first).days + 1 == MAX_WINDOW_DAYS
    with pytest.raises(ValueError, match="cannot exceed"):
        cloud_window(first, date(2026, 1, 2))


# -- endpoint ---------------------------------------------------------------------


@pytest.fixture
def cloud_client(auth_client):
    """Authenticated client with the cloud client and vehicle stubbed out."""
    stub = AsyncMock()
    vehicle = SimpleNamespace(vin="VIN123")
    auth_client.app.dependency_overrides[deps.get_client] = lambda: stub
    auth_client.app.dependency_overrides[deps.get_vehicle] = lambda: vehicle
    yield auth_client, stub
    auth_client.app.dependency_overrides.clear()


def test_consumption_breakdown_for_a_range(cloud_client):
    http, stub = cloud_client
    stub.get_consumption_breakdown.return_value = ConsumptionBreakdown(
        driver_ec=80.5, ac_ec=12.25, other_ec=7.25
    )

    resp = http.get(
        "/api/vehicles/VIN123/consumption/breakdown",
        params={"from_date": "2026-07-01", "to_date": "2026-07-31"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "driver_ec": 80.5,
        "ac_ec": 12.25,
        "other_ec": 7.25,
        "total_ec": 100.0,
        "start": "2026-07-01",
        "end": "2026-07-31",
    }
    kwargs = stub.get_consumption_breakdown.await_args.kwargs
    assert kwargs["start"].tzinfo is not None
    assert kwargs["end"] > kwargs["start"]


def test_consumption_breakdown_rejects_inverted_range(cloud_client):
    http, stub = cloud_client
    resp = http.get(
        "/api/vehicles/VIN123/consumption/breakdown",
        params={"from_date": "2026-07-31", "to_date": "2026-07-01"},
    )
    assert resp.status_code == 422
    stub.get_consumption_breakdown.assert_not_awaited()


def test_daily_mileage_energy_sums_the_window(cloud_client):
    http, stub = cloud_client
    stub.get_mileage_energy_history.return_value = MileageEnergyHistory.from_dict(
        {
            "totalmileage": "12345.6",
            "totalEnergy": "2100.4",
            "deliveryDays": "400",
            "totalAccumulatedMileage": "85",
            "detail": [
                {
                    "day": "2026-07-01",
                    "xDay": 1782856800000,
                    "accumulatedMileage": "60",
                    "accumulatedEnergyConsume": "9",
                },
                {
                    "day": "2026-07-02",
                    "accumulatedMileage": "25",
                    "accumulatedEnergyConsume": "4.5",
                },
                {"day": "2026-07-03", "accumulatedMileage": "0"},
            ],
        }
    )

    resp = http.get(
        "/api/vehicles/VIN123/mileage/daily",
        params={"from_date": "2026-07-01", "to_date": "2026-07-03"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_energy_kwh"] == 2100.4
    assert body["delivery_days"] == 400
    assert body["window_mileage_km"] == 85
    assert body["window_energy_kwh"] == 13.5  # the day without energy is skipped
    assert [d["mileage_km"] for d in body["days"]] == [60, 25, 0]
    assert body["days"][2]["energy_kwh"] is None
    assert body["days"][0]["day_ms"] == 1782856800000


def test_daily_mileage_energy_rejects_too_long_window(cloud_client):
    http, stub = cloud_client
    resp = http.get(
        "/api/vehicles/VIN123/mileage/daily",
        params={"from_date": "2024-01-01", "to_date": "2026-01-01"},
    )
    assert resp.status_code == 422
    stub.get_mileage_energy_history.assert_not_awaited()
