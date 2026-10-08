"""Battery SOH estimate from the energy reported at full charge."""

from datetime import date, datetime, timedelta

import pytest

from leapconnect.application.battery_health import (
    get_battery_health,
    load_reference_kwh,
    save_reference_kwh,
)
from leapconnect.domain.telemetry.battery_health import (
    WINDOW,
    FullChargeSample,
    estimate_battery_health,
    smooth_capacity,
)
from leapconnect.domain.telemetry.models import VehicleSnapshot
from leapconnect.infrastructure.persistence.sqlite_adapter import (
    SqlAlchemyRepository,
)

DAY0 = date(2026, 5, 1)


def _samples(*kwh: float) -> list[FullChargeSample]:
    return [FullChargeSample(DAY0 + timedelta(days=i), v) for i, v in enumerate(kwh)]


def test_too_few_full_charges_give_no_estimate():
    assert estimate_battery_health(_samples(38.2, 38.1)) is None


def test_rolling_median_ignores_a_cold_day():
    smoothed = smooth_capacity(_samples(38.2, 38.2, 38.2, 37.6, 38.2))
    assert smoothed[-1] == 38.2


def test_observed_reference_is_the_peak_smoothed_capacity():
    # A cold first day must not drag the reference down, nor a lone
    # early high reading push it up.
    health = estimate_battery_health(
        _samples(37.8, 38.6, *[38.2] * (WINDOW - 2), *[37.8] * WINDOW)
    )
    assert health.reference_source == "observed"
    assert health.reference_kwh == 38.2
    assert health.capacity_kwh == 37.8
    assert health.soh_pct == 99.0
    assert health.last_full_charge == DAY0 + timedelta(days=2 * WINDOW - 1)
    assert max(p.soh_pct for p in health.series) == 100.0


def test_user_reference_overrides_the_observed_one():
    health = estimate_battery_health(_samples(38.0, 38.0, 38.0), reference_kwh=40.0)
    assert health.reference_source == "user"
    assert health.soh_pct == 95.0


def test_out_of_range_user_reference_is_ignored():
    health = estimate_battery_health(_samples(38.0, 38.0, 38.0), reference_kwh=1.0)
    assert health.reference_source == "observed"


@pytest.fixture
async def repo(tmp_path):
    repo = SqlAlchemyRepository(f"sqlite+aiosqlite:///{tmp_path}/soh.db")
    await repo.init_db()
    rows = [
        # day, hour, soc, Wh — the day's highest reading at 100% counts.
        (1, 8, 100, 38_100),
        (1, 9, 100, 38_200),
        (1, 10, 99, 38_900),  # not a full charge
        (2, 8, 100, 38_200),
        (3, 8, 100, 0),  # sanitized glitch
        (4, 8, 100, 38_000),
    ]
    for day, hour, soc, wh in rows:
        await repo.save_snapshot(
            VehicleSnapshot(
                vin="V1",
                timestamp=datetime(2026, 5, day, hour),
                battery_soc=soc,
                battery_dump_energy=wh,
            )
        )
    return repo


async def test_repo_returns_daily_full_charge_maxima(repo):
    samples = await repo.get_full_charge_samples("V1")
    assert samples == [
        FullChargeSample(date(2026, 5, 1), 38.2),
        FullChargeSample(date(2026, 5, 2), 38.2),
        FullChargeSample(date(2026, 5, 4), 38.0),
    ]
    assert await repo.get_full_charge_samples("OTHER") == []


async def test_reference_round_trip(repo):
    assert await load_reference_kwh(repo, "V1") is None
    await save_reference_kwh(repo, "V1", 40.0)
    assert await load_reference_kwh(repo, "V1") == 40.0
    health = await get_battery_health(repo, "V1")
    assert health.reference_source == "user"
    await save_reference_kwh(repo, "V1", None)
    assert await load_reference_kwh(repo, "V1") is None
    with pytest.raises(ValueError):
        await save_reference_kwh(repo, "V1", 5.0)


def test_api_without_data(auth_client):
    resp = auth_client.get("/api/vehicles/V1/battery/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["soh_pct"] is None
    assert body["samples"] == 0

    resp = auth_client.put(
        "/api/vehicles/V1/battery/health/reference", json={"reference_kwh": 37.3}
    )
    assert resp.status_code == 200
    assert resp.json()["user_reference_kwh"] == 37.3

    resp = auth_client.put(
        "/api/vehicles/V1/battery/health/reference", json={"reference_kwh": 5}
    )
    assert resp.status_code == 422
