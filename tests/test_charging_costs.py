"""Bulk "calculate missing costs" and the shared charge-location resolver."""

from datetime import datetime, timedelta

from leapconnect.application.charging_costs import (
    SKIP_NO_ENERGY,
    SKIP_NO_TIER,
    SKIP_ONGOING,
    MissingCostSession,
    calculate_missing_costs,
)
from leapconnect.domain.charging.location import resolve_charge_location
from leapconnect.domain.charging.models import (
    ChargingPriceTier,
    ChargingSessionCost,
)
from leapconnect.domain.telemetry.models import VehicleSnapshot
from leapconnect.domain.zones import Zone

HOME = (45.0, 9.0)
AWAY = (48.0, 2.0)
T0 = datetime(2026, 9, 10, 20, 0)


def _zone(tier="home_solar"):
    return Zone(
        id=1,
        name="Home",
        shape_type="circle",
        latitude=HOME[0],
        longitude=HOME[1],
        radius_m=200.0,
        charging_tier_id=tier,
    )


def _snaps(pos, *, charge_state=1, kwh=(40.0, 50.0), start=T0):
    """Two snapshots one hour apart, energy rising from kwh[0] to kwh[1]."""
    return [
        VehicleSnapshot(
            vin="V1",
            timestamp=start + timedelta(hours=i),
            battery_dump_energy=e * 1000,
            battery_charge_state=charge_state,
            vehicle_latitude=pos[0] if pos else None,
            vehicle_longitude=pos[1] if pos else None,
        )
        for i, e in enumerate(kwh)
    ]


class _Repo:
    """In-memory stand-in for the parts of AppRepository the use case touches."""

    def __init__(self, *, zones=(), snaps=(), costs=()):
        self.zones = list(zones)
        self.snaps = list(snaps)
        self.costs = list(costs)
        self._next_id = 100

    async def get_zones(self, vin=None):
        return list(self.zones)

    async def get_history(self, vin, **kwargs):
        return list(self.snaps)

    async def get_session_costs(self, vin, **kwargs):
        return list(self.costs)

    async def upsert_session_cost(self, sc):
        if sc.id is None:
            self._next_id += 1
            sc.id = self._next_id
            self.costs.append(sc)
        return sc

    async def get_price_tiers(self):
        return [
            ChargingPriceTier(id=t, label=t, price_kwh=0.25)
            for t in ("home_grid", "home_solar", "public_ac", "public_dc")
        ]

    async def get_setting(self, key):
        return None


# -- resolver ---------------------------------------------------------------


def test_resolver_dc_wins_over_zone():
    loc = resolve_charge_location([_zone()], *HOME, is_dc=True)
    assert loc.tier_id == "public_dc"
    assert loc.zone_name == "Home"


def test_resolver_zone_without_tier_keeps_place_but_no_tier():
    loc = resolve_charge_location([_zone(tier=None)], *HOME)
    assert loc.zone_name == "Home"
    assert loc.tier_id is None


def test_resolver_outside_zones_is_unknown():
    loc = resolve_charge_location([_zone()], *AWAY)
    assert loc == resolve_charge_location([], None, None)
    assert loc.tier_id is None and loc.zone_name is None


# -- use case ---------------------------------------------------------------


def _detected(end=T0 + timedelta(hours=1)):
    return MissingCostSession(start_ts=T0, end_ts=end)


async def test_detected_session_in_tier_zone_is_created_and_costed():
    repo = _Repo(zones=[_zone()], snaps=_snaps(HOME))
    result = await calculate_missing_costs(repo, "V1", [_detected()])
    assert result.calculated == 1 and not result.skipped
    sc = repo.costs[0]
    assert (sc.tier_id, sc.zone_name, sc.energy_kwh) == ("home_solar", "Home", 10.0)
    assert sc.cost == 2.5


async def test_unknown_tier_is_skipped_without_fallback():
    repo = _Repo(zones=[_zone()], snaps=_snaps(AWAY))
    result = await calculate_missing_costs(repo, "V1", [_detected()])
    assert result.calculated == 0
    assert [s.reason for s in result.skipped] == [SKIP_NO_TIER]
    assert repo.costs == []


async def test_unknown_tier_uses_fallback():
    repo = _Repo(zones=[_zone(tier=None)], snaps=_snaps(HOME))
    result = await calculate_missing_costs(
        repo, "V1", [_detected()], fallback_tier_id="home_grid"
    )
    assert result.calculated == 1
    assert repo.costs[0].tier_id == "home_grid"
    assert repo.costs[0].zone_name == "Home"  # place recorded independently


async def test_dc_snapshot_resolves_public_dc():
    repo = _Repo(snaps=_snaps(None, charge_state=2))
    result = await calculate_missing_costs(repo, "V1", [_detected()])
    assert result.calculated == 1
    assert repo.costs[0].tier_id == "public_dc"


async def test_ongoing_detected_session_is_skipped():
    repo = _Repo(zones=[_zone()], snaps=_snaps(HOME))
    result = await calculate_missing_costs(repo, "V1", [_detected(end=None)])
    assert [s.reason for s in result.skipped] == [SKIP_ONGOING]


async def test_unmeasurable_detected_session_is_not_persisted():
    repo = _Repo(zones=[_zone()], snaps=_snaps(HOME)[:1])
    result = await calculate_missing_costs(repo, "V1", [_detected()])
    assert [s.reason for s in result.skipped] == [SKIP_NO_ENERGY]
    assert repo.costs == []


async def test_stored_record_without_cost_is_recalculated():
    sc = ChargingSessionCost(
        id=1, vin="V1", start_ts=T0, end_ts=T0 + timedelta(hours=1), tier_id="home_grid"
    )
    repo = _Repo(snaps=_snaps(HOME), costs=[sc])
    result = await calculate_missing_costs(
        repo, "V1", [MissingCostSession(start_ts=T0, cost_id=1)]
    )
    assert result.calculated == 1
    assert sc.cost == 2.5


async def test_orphan_is_skipped_unless_close_requested():
    def orphan():
        return ChargingSessionCost(id=1, vin="V1", start_ts=T0, tier_id="home_grid")

    item = MissingCostSession(start_ts=T0, end_ts=T0 + timedelta(hours=1), cost_id=1)

    repo = _Repo(snaps=_snaps(HOME), costs=[orphan()])
    result = await calculate_missing_costs(repo, "V1", [item])
    assert [s.reason for s in result.skipped] == [SKIP_ONGOING]
    assert repo.costs[0].end_ts is None

    repo = _Repo(snaps=_snaps(HOME), costs=[orphan()])
    result = await calculate_missing_costs(repo, "V1", [item], close_orphans=True)
    assert result.calculated == 1
    assert repo.costs[0].end_ts == T0 + timedelta(hours=1)
    assert repo.costs[0].cost == 2.5


async def test_detected_session_matching_stored_record_is_not_duplicated():
    sc = ChargingSessionCost(
        id=1,
        vin="V1",
        start_ts=T0 - timedelta(seconds=30),
        end_ts=T0 + timedelta(hours=1),
        tier_id="public_ac",
    )
    repo = _Repo(snaps=_snaps(AWAY), costs=[sc])
    result = await calculate_missing_costs(repo, "V1", [_detected()])
    assert result.calculated == 1
    assert len(repo.costs) == 1 and repo.costs[0].tier_id == "public_ac"


# -- endpoint ---------------------------------------------------------------


def test_endpoint_rejects_unknown_fallback_tier(auth_client):
    resp = auth_client.post(
        "/api/vehicles/V1/charging-costs/calculate-missing",
        json={"sessions": [], "fallback_tier_id": "nope"},
    )
    assert resp.status_code == 422


def test_endpoint_reports_skipped_sessions(auth_client):
    resp = auth_client.post(
        "/api/vehicles/V1/charging-costs/calculate-missing",
        json={"sessions": [{"start_ts": "2026-09-10T20:00:00"}]},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "calculated": 0,
        "skipped": [{"start_ts": "2026-09-10T20:00:00", "reason": "ongoing"}],
    }
