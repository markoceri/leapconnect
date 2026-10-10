"""Bulk "calculate missing costs" and the shared charge-location resolver."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from leapconnect.application.charging_costs import (
    SKIP_NO_ENERGY,
    SKIP_NO_TIER,
    SKIP_ONGOING,
    MissingCostSession,
    calculate_missing_costs,
    find_month_missing_costs,
    list_month_sessions,
)
from leapconnect.application.scheduler import (
    MONTH_END_COSTS_SETTING,
    VehicleDataScheduler,
)
from leapconnect.domain.charging.location import resolve_charge_location
from leapconnect.domain.charging.models import (
    ChargingPriceTier,
    ChargingSessionCost,
)
from leapconnect.domain.charging.sessions import (
    detect_charge_sessions,
    month_bounds,
    pair_sessions,
)
from leapconnect.domain.telemetry.models import VehicleSnapshot
from leapconnect.domain.zones import Zone

HOME = (45.0, 9.0)
AWAY = (48.0, 2.0)
T0 = datetime(2026, 9, 10, 20, 0)
COSTS_URL = "/api/vehicles/V1/charging-costs"


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


def _snaps(pos, *, charge_state=1, kwh=(40.0, 50.0), start=T0, charging=True):
    """Two snapshots one hour apart, energy rising from kwh[0] to kwh[1]."""
    return [
        VehicleSnapshot(
            vin="V1",
            timestamp=start + timedelta(hours=i),
            battery_dump_energy=e * 1000,
            battery_charge_state=charge_state,
            battery_is_charging=charging,
            vehicle_latitude=pos[0] if pos else None,
            vehicle_longitude=pos[1] if pos else None,
        )
        for i, e in enumerate(kwh)
    ]


class _Repo:
    """In-memory stand-in for the parts of AppRepository the use case touches."""

    def __init__(self, *, zones=(), snaps=(), costs=(), settings=None):
        self.zones = list(zones)
        self.snaps = list(snaps)
        self.costs = list(costs)
        self.settings = dict(settings or {})
        self._next_id = 100

    async def get_zones(self, vin=None):
        return list(self.zones)

    async def get_history(self, vin, *, from_date=None, to_date=None, **kwargs):
        snaps = self.snaps
        if from_date and to_date:
            since = datetime.fromisoformat(from_date)
            until = datetime.fromisoformat(to_date) + timedelta(days=1)
            snaps = [s for s in snaps if since <= s.timestamp < until]
        return list(snaps)

    async def get_session_costs(self, vin, **kwargs):
        return list(self.costs)

    async def upsert_session_cost(self, sc):
        if sc.id is None:
            self._next_id += 1
            sc.id = self._next_id
            self.costs.append(sc)
        return sc

    async def delete_session_cost(self, cost_id):
        before = len(self.costs)
        self.costs = [c for c in self.costs if c.id != cost_id]
        return len(self.costs) < before

    async def get_time_bands(self, tier_id=None):
        return list(getattr(self, "bands", []))

    async def get_price_tiers(self):
        return [
            ChargingPriceTier(id=t, label=t, price_kwh=0.25)
            for t in ("home_grid", "home_solar", "public_ac", "public_dc")
        ]

    async def get_setting(self, key):
        return self.settings.get(key)

    async def save_setting(self, key, value):
        self.settings[key] = value


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


def _create_session_cost(client, **fields):
    tier = client.put("/api/charging/tiers/public_ac", json={"price_kwh": 0.25})
    assert tier.status_code == 200
    response = client.post(
        COSTS_URL,
        json={
            "start_ts": T0.isoformat(),
            "end_ts": (T0 + timedelta(hours=1)).isoformat(),
            "tier_id": "public_ac",
            "energy_kwh": 10.0,
            **fields,
        },
    )
    assert response.status_code == 201
    return response.json()


def _assert_saved_cost(client, session, expected):
    assert session["cost"] == expected
    response = client.get(COSTS_URL)
    assert response.status_code == 200
    [stored] = response.json()
    assert stored["id"] == session["id"]
    assert stored["cost"] == expected


@pytest.mark.parametrize("cost, energy", [(12.34, 10.0), (0.0, None)])
def test_create_session_cost_override(auth_client, cost, energy):
    session = _create_session_cost(auth_client, cost=cost, energy_kwh=energy)
    _assert_saved_cost(auth_client, session, cost)


@pytest.mark.parametrize("cost", [12.34, 0.0])
def test_update_session_cost_override(auth_client, cost):
    session = _create_session_cost(auth_client)
    assert session["cost"] == 2.5
    response = auth_client.put(f"{COSTS_URL}/{session['id']}", json={"cost": cost})
    assert response.status_code == 200
    _assert_saved_cost(auth_client, response.json(), cost)


@pytest.mark.parametrize("energy, expected", [(10.0, 2.5), (None, None)])
def test_clear_session_cost_override(auth_client, energy, expected):
    session = _create_session_cost(auth_client, cost=12.34, energy_kwh=energy)
    assert session["cost"] == 12.34
    response = auth_client.put(f"{COSTS_URL}/{session['id']}", json={"cost": None})
    assert response.status_code == 200
    _assert_saved_cost(auth_client, response.json(), expected)


def test_create_session_cost_without_override_uses_tariff(auth_client):
    session = _create_session_cost(auth_client)
    _assert_saved_cost(auth_client, session, 2.5)


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


def test_month_sessions_endpoint(auth_client):
    created = auth_client.post(
        "/api/vehicles/V1/charging-costs",
        json={"start_ts": "2026-07-31T22:46:00", "tier_id": "home_grid"},
    )
    assert created.status_code == 201
    assert (
        auth_client.put("/api/preferences", json={"timezone": "Europe/Rome"}).json()[
            "timezone"
        ]
        == "Europe/Rome"
    )

    resp = auth_client.get("/api/vehicles/V1/charging-sessions?year=2026&month=8")
    assert resp.status_code == 200
    body = resp.json()
    assert body["timezone"] == "Europe/Rome"
    [row] = body["sessions"]
    assert (row["id"], row["start_ts"], row["tier_id"]) == (
        created.json()["id"],
        "2026-07-31T22:46:00",
        "home_grid",
    )
    july = auth_client.get("/api/vehicles/V1/charging-sessions?year=2026&month=7")
    assert july.json()["sessions"] == []


def test_sessions_endpoint_takes_a_local_day_range(auth_client):
    auth_client.put("/api/preferences", json={"timezone": "Europe/Rome"})
    auth_client.post(
        "/api/vehicles/V1/charging-costs",
        json={"start_ts": "2026-07-31T22:46:00", "tier_id": "home_grid"},
    )
    day = "/api/vehicles/V1/charging-sessions?from_date={0}&to_date={0}"
    aug1 = auth_client.get(day.format("2026-08-01")).json()
    assert (aug1["start"], aug1["end"]) == (
        "2026-07-31T22:00:00",
        "2026-08-01T22:00:00",
    )
    assert [s["start_ts"] for s in aug1["sessions"]] == ["2026-07-31T22:46:00"]
    assert auth_client.get(day.format("2026-07-31")).json()["sessions"] == []


def test_sessions_endpoint_requires_a_period(auth_client):
    base = "/api/vehicles/V1/charging-sessions"
    assert auth_client.get(base).status_code == 422
    reversed_range = f"{base}?from_date=2026-08-02&to_date=2026-08-01"
    assert auth_client.get(reversed_range).status_code == 422


def test_month_sessions_endpoint_rejects_bad_month(auth_client):
    resp = auth_client.get("/api/vehicles/V1/charging-sessions?year=2026&month=13")
    assert resp.status_code == 422


def test_preferences_reject_unknown_timezone(auth_client):
    resp = auth_client.put("/api/preferences", json={"timezone": "Mars/Base"})
    assert resp.status_code == 422


# -- session detection ------------------------------------------------------


def _idle(ts):
    return VehicleSnapshot(vin="V1", timestamp=ts, battery_is_charging=False)


def test_detect_charge_sessions_splits_runs_and_keeps_open_tail():
    snaps = [
        _idle(T0 - timedelta(hours=1)),
        *_snaps(HOME),
        _idle(T0 + timedelta(hours=2)),
        *_snaps(HOME, start=T0 + timedelta(hours=5)),
    ]
    sessions = detect_charge_sessions(snaps)
    assert [(s.start_ts, s.end_ts) for s in sessions] == [
        (T0, T0 + timedelta(hours=1)),
        (T0 + timedelta(hours=5), None),
    ]


def test_session_row_reports_where_it_charged():
    # Merged session: the latest run has no GPS fix, so the earlier one is used
    runs = detect_charge_sessions(
        [
            *_snaps(HOME, charge_state=2),
            _idle(T0 + timedelta(hours=2)),
            *_snaps(None, start=T0 + timedelta(hours=3)),
        ]
    )
    record = ChargingSessionCost(
        id=1,
        vin="V1",
        start_ts=T0,
        end_ts=T0 + timedelta(hours=4),
        tier_id="public_dc",
    )
    [row] = pair_sessions(runs, [record], T0, T0 + timedelta(days=1))
    assert (row.location, row.is_dc) == (HOME, True)

    [bare] = pair_sessions(runs[1:], [], T0, T0 + timedelta(days=1))
    assert (bare.location, bare.is_dc) == (None, False)


# -- month selection --------------------------------------------------------


async def test_find_month_missing_costs_selects_only_costless_in_month():
    end = T0 + timedelta(hours=1)
    costed = ChargingSessionCost(
        id=1, vin="V1", start_ts=T0, end_ts=end, tier_id="home_grid", cost=1.0
    )
    orphan = ChargingSessionCost(
        id=2, vin="V1", start_ts=T0 + timedelta(days=1), tier_id="home_grid"
    )
    other_month = ChargingSessionCost(
        id=3, vin="V1", start_ts=datetime(2026, 8, 30, 10), tier_id="home_grid"
    )
    snaps = [
        *_snaps(HOME),  # matches the costed record → excluded
        _idle(end + timedelta(minutes=5)),
        *_snaps(HOME, start=T0 + timedelta(days=1)),  # the orphan, now ended
        _idle(T0 + timedelta(days=1, hours=2)),
        *_snaps(HOME, start=T0 + timedelta(days=2)),  # snapshot-only
        _idle(T0 + timedelta(days=2, hours=2)),
    ]
    repo = _Repo(snaps=snaps, costs=[costed, orphan, other_month])
    missing = await find_month_missing_costs(repo, "V1", 2026, 9)
    assert [(m.cost_id, m.start_ts, m.end_ts) for m in missing] == [
        (2, T0 + timedelta(days=1), T0 + timedelta(days=1, hours=1)),
        (None, T0 + timedelta(days=2), T0 + timedelta(days=2, hours=1)),
    ]


async def test_charge_across_month_start_is_not_split():
    """A charge already running at midnight belongs to the previous month only."""
    start = datetime(2026, 8, 31, 22, 46)
    costed = ChargingSessionCost(
        id=1,
        vin="V1",
        start_ts=start,
        end_ts=datetime(2026, 9, 1, 6, 44),
        tier_id="home_grid",
        cost=7.43,
    )
    snaps = [
        _idle(start - timedelta(minutes=5)),
        *_snaps(HOME, start=start, kwh=(40.0, 45.0, 50.0)),
        # telemetry gap across midnight, then the same charge continues
        *_snaps(HOME, start=datetime(2026, 9, 1, 0, 12), kwh=(52.0, 60.0)),
        _idle(datetime(2026, 9, 1, 6, 50)),
    ]
    repo = _Repo(snaps=snaps, costs=[costed])
    assert await find_month_missing_costs(repo, "V1", 2026, 9) == []


ROME = ZoneInfo("Europe/Rome")


def test_month_bounds_follow_the_time_zone():
    assert month_bounds(2026, 8, ROME) == (
        datetime(2026, 7, 31, 22, 0),
        datetime(2026, 8, 31, 22, 0),
    )
    assert month_bounds(2026, 12) == (datetime(2026, 12, 1), datetime(2027, 1, 1))


def _issue31_repo():
    """Overnight charge from 00:46 local (22:46 UTC of the previous day) with a
    telemetry gap; a duplicate record was created at the UTC month start."""
    start = datetime(2026, 7, 31, 22, 46)
    real = ChargingSessionCost(
        id=1,
        vin="V1",
        start_ts=start,
        end_ts=datetime(2026, 8, 1, 6, 47),
        tier_id="home_grid",
        energy_kwh=21.2,
        cost=7.43,
        zone_name="Home",
    )
    snaps = [
        _idle(start - timedelta(minutes=5)),
        *_snaps(HOME, start=start, kwh=(40.0, 45.0)),
        *_snaps(HOME, start=datetime(2026, 8, 1, 1, 36), kwh=(52.0, 61.2)),
        _idle(datetime(2026, 8, 1, 6, 50)),
    ]
    return _Repo(snaps=snaps, costs=[real]), real


async def test_overnight_charge_is_one_session_of_the_local_month():
    repo, real = _issue31_repo()
    august = await list_month_sessions(repo, "V1", 2026, 8, ROME)
    assert [(r.record, r.start_ts) for r in august] == [(real, real.start_ts)]
    assert august[0].detected_end_ts == datetime(2026, 8, 1, 2, 36)
    assert await list_month_sessions(repo, "V1", 2026, 7, ROME) == []


async def test_month_end_job_uses_the_same_local_month():
    repo, _ = _issue31_repo()
    repo.costs[0].cost = None  # left without a cost → only August's run picks it up
    assert await find_month_missing_costs(repo, "V1", 2026, 7, ROME) == []
    [missing] = await find_month_missing_costs(repo, "V1", 2026, 8, ROME)
    assert (missing.cost_id, missing.start_ts) == (1, datetime(2026, 7, 31, 22, 46))


def test_merge_keeps_unmatched_records_and_fills_detected_values():
    detected = detect_charge_sessions(
        [
            *_snaps(HOME, kwh=(40.0, 50.0)),
            _idle(T0 + timedelta(hours=2)),
        ]
    )
    matched = ChargingSessionCost(
        id=1, vin="V1", start_ts=T0 + timedelta(seconds=30), tier_id="home_grid"
    )
    manual = ChargingSessionCost(
        id=2, vin="V1", start_ts=T0 + timedelta(days=3), tier_id="public_ac"
    )
    start, end = month_bounds(2026, 9)
    rows = pair_sessions(detected, [matched, manual], start, end)
    assert [r.record.id for r in rows] == [2, 1]
    assert (rows[1].energy_kwh, rows[1].detected_end_ts) == (
        10.0,
        T0 + timedelta(hours=1),
    )


# -- scheduler month-end trigger --------------------------------------------


class _Dispatcher:
    def __init__(self):
        self.sent = []

    async def dispatch_custom(self, event_type, vin, vehicle_name, ctx, **kwargs):
        self.sent.append((event_type, vin, ctx))


def _scheduler(repo):
    dispatcher = _Dispatcher()
    sched = VehicleDataScheduler(repo=repo, notification_dispatcher=dispatcher)
    sched._vehicles = [SimpleNamespace(vin="V1", vehicle_nickname="Car", car_type=None)]
    return sched, dispatcher


def _month_snaps():
    """One September session in a tier zone, one outside every zone."""
    return [
        *_snaps(HOME),
        _idle(T0 + timedelta(hours=2)),
        *_snaps(AWAY, start=T0 + timedelta(days=1)),
        _idle(T0 + timedelta(days=1, hours=2)),
    ]


async def test_month_end_waits_for_grace_day():
    repo = _Repo(zones=[_zone()], snaps=_month_snaps())
    sched, _ = _scheduler(repo)
    await sched._maybe_run_month_end_costs(now=datetime(2026, 10, 1, 12))
    assert repo.costs == [] and MONTH_END_COSTS_SETTING not in repo.settings


async def test_month_end_costs_previous_month_and_notifies_skipped():
    repo = _Repo(zones=[_zone()], snaps=_month_snaps())
    sched, dispatcher = _scheduler(repo)
    await sched._maybe_run_month_end_costs(now=datetime(2026, 10, 2, 8))

    assert [(c.tier_id, c.cost) for c in repo.costs] == [("home_solar", 2.5)]
    assert repo.settings[MONTH_END_COSTS_SETTING] == "2026-09"
    [(event_type, vin, ctx)] = dispatcher.sent
    assert (event_type, vin) == ("charging_costs_incomplete", "V1")
    assert ctx["calculated"] == 1 and ctx["skipped"] == 1
    assert "tier not inferable" in ctx["sessions_list"]

    # Already done for September → second run is a no-op.
    await sched._maybe_run_month_end_costs(now=datetime(2026, 10, 3, 8))
    assert len(dispatcher.sent) == 1 and len(repo.costs) == 1


async def test_month_end_runs_on_the_local_calendar():
    """With a time zone set, the job's "previous month" is the local one."""
    repo = _Repo(
        zones=[_zone()], snaps=_month_snaps(), settings={"timezone": "Europe/Rome"}
    )
    sched, _ = _scheduler(repo)
    await sched._maybe_run_month_end_costs(now=datetime(2026, 10, 2, 0, 30))
    assert repo.settings[MONTH_END_COSTS_SETTING] == "2026-09"
    assert [(c.tier_id, c.cost) for c in repo.costs] == [("home_solar", 2.5)]


async def test_month_end_respects_disabled_preference():
    repo = _Repo(
        zones=[_zone()],
        snaps=_month_snaps(),
        settings={"auto_calculate_monthly_costs": "false"},
    )
    sched, dispatcher = _scheduler(repo)
    await sched._maybe_run_month_end_costs(now=datetime(2026, 10, 2, 8))
    assert repo.costs == [] and not dispatcher.sent
    assert MONTH_END_COSTS_SETTING not in repo.settings


def test_preferences_expose_auto_monthly_costs(auth_client):
    assert (
        auth_client.get("/api/preferences").json()["auto_calculate_monthly_costs"]
        is True
    )
    resp = auth_client.put(
        "/api/preferences", json={"auto_calculate_monthly_costs": False}
    )
    assert resp.status_code == 200
    assert resp.json()["auto_calculate_monthly_costs"] is False
    bad = auth_client.put("/api/preferences", json={"auto_calculate_monthly_costs": 1})
    assert bad.status_code == 422
