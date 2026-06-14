"""Scheduler charging-tier-by-zone selection."""

from datetime import UTC, datetime
from types import SimpleNamespace

from leapconnect.application.scheduler import VehicleDataScheduler
from leapconnect.domain.zones import Zone


class _StubRepo:
    """Minimal repo capturing the session cost the scheduler upserts."""

    def __init__(self, zones):
        self._zones = zones
        self.saved = []

    async def get_zones(self, vin=None):
        return list(self._zones)

    async def upsert_session_cost(self, sc):
        self.saved.append(sc)
        return sc


def _status(lat, lon, charge_state):
    battery = SimpleNamespace(
        charge_state=charge_state,
        soc=50,
        expected_mileage=200,
        is_charge_fast_gun_insert=None,
        is_charge_slow_gun_insert=None,
    )
    return SimpleNamespace(latitude=lat, longitude=lon, battery=battery)


def _start_event(vin="V1"):
    return SimpleNamespace(
        vin=vin, timestamp=datetime.now(UTC), event_type="charge_start"
    )


def _home_zone():
    return Zone(
        id=1,
        name="Home",
        shape_type="circle",
        latitude=45.0,
        longitude=9.0,
        radius_m=200.0,
        charging_tier_id="home_solar",
    )


async def test_charge_start_uses_zone_tier_for_ac():
    repo = _StubRepo([_home_zone()])
    sched = VehicleDataScheduler(repo=repo)
    # AC charge (charge_state != 2) inside the tier-assigned zone
    await sched._handle_charging_cost_event(_start_event(), _status(45.0, 9.0, 1))
    assert repo.saved and repo.saved[0].tier_id == "home_solar"


async def test_charge_start_dc_overrides_zone():
    repo = _StubRepo([_home_zone()])
    sched = VehicleDataScheduler(repo=repo)
    # DC fast charge (charge_state == 2) wins even inside a zone
    await sched._handle_charging_cost_event(_start_event(), _status(45.0, 9.0, 2))
    assert repo.saved and repo.saved[0].tier_id == "public_dc"


async def test_charge_start_defaults_home_grid_outside_zones():
    repo = _StubRepo([_home_zone()])
    sched = VehicleDataScheduler(repo=repo)
    # AC charge far from any zone falls back to home_grid
    await sched._handle_charging_cost_event(_start_event(), _status(48.0, 2.0, 1))
    assert repo.saved and repo.saved[0].tier_id == "home_grid"
