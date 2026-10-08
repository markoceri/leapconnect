"""Merging charging sessions interrupted and resumed in place."""

from datetime import datetime, timedelta

import pytest

from leapconnect.application.charging_costs import (
    MergeError,
    find_month_missing_costs,
    list_month_sessions,
    merge_charge_sessions,
    plan_merge,
)
from leapconnect.domain.charging.models import ChargingSessionCost, ChargingTimeBand
from leapconnect.domain.charging.sessions import (
    MERGE_DIFFERENT_PLACE,
    MERGE_ONGOING,
    MERGE_TIER_CONFLICT,
    MERGE_TOO_FAR_APART,
    MERGE_VEHICLE_MOVED,
)
from leapconnect.domain.telemetry.models import VehicleSnapshot
from tests.test_charging_costs import AWAY, HOME, _Repo, _zone

T0 = datetime(2026, 9, 10, 21, 0)


def _snap(ts, *, charging, kwh, odo=1000, pos=HOME):
    return VehicleSnapshot(
        vin="V1",
        timestamp=ts,
        battery_is_charging=charging,
        battery_dump_energy=kwh * 1000,
        drive_total_mileage=odo,
        vehicle_latitude=pos[0],
        vehicle_longitude=pos[1],
    )


def _run(start, kwh=(40.0, 45.0), *, odo=1000, pos=HOME, end_idle=True):
    """A one-hour charging run, followed by an idle snapshot (charge stopped)."""
    snaps = [
        _snap(start + timedelta(hours=i), charging=True, kwh=e, odo=odo, pos=pos)
        for i, e in enumerate(kwh)
    ]
    if end_idle:
        snaps.append(
            _snap(
                start + timedelta(hours=1, minutes=5),
                charging=False,
                kwh=kwh[-1],
                odo=odo,
                pos=pos,
            )
        )
    return snaps


def _record(cid, start, end, *, tier="home_grid", note=None):
    return ChargingSessionCost(
        id=cid, vin="V1", start_ts=start, end_ts=end, tier_id=tier, note=note
    )


R1, R2, R3 = T0, T0 + timedelta(hours=1, minutes=30), T0 + timedelta(hours=3)


def _three_runs_repo(**kwargs):
    snaps = [
        *_run(R1, (40.0, 45.0)),
        *_run(R2, (45.0, 50.0)),
        *_run(R3, (50.0, 52.0)),
    ]
    return _Repo(zones=[_zone("home_grid")], snaps=snaps, **kwargs)


async def test_merge_keeps_first_record_and_sums_runs():
    repo = _three_runs_repo(
        costs=[
            _record(1, R1, R1 + timedelta(hours=1), note="unlocked car"),
            _record(2, R2, R2 + timedelta(hours=1)),
        ]
    )
    merged = await merge_charge_sessions(repo, "V1", [R1, R2])
    assert merged.id == 1
    assert (merged.start_ts, merged.end_ts) == (R1, R2 + timedelta(hours=1))
    assert merged.energy_kwh == 10.0 and merged.cost == 2.5
    assert merged.zone_name == "Home" and merged.note == "unlocked car"
    assert [c.id for c in repo.costs] == [1]

    [single, merged_row] = await list_month_sessions(repo, "V1", 2026, 9)
    assert (merged_row.record.id, len(merged_row.parts)) == (1, 2)
    assert (single.record, len(single.parts)) == (None, 1)


async def test_sessions_in_between_are_included():
    repo = _three_runs_repo()
    merged = await merge_charge_sessions(repo, "V1", [R1, R3])
    assert merged.energy_kwh == 12.0
    [row] = await list_month_sessions(repo, "V1", 2026, 9)
    assert len(row.parts) == 3


async def test_deleting_the_merged_record_splits_it_again():
    repo = _three_runs_repo()
    merged = await merge_charge_sessions(repo, "V1", [R1, R2])
    repo.costs.remove(merged)
    rows = await list_month_sessions(repo, "V1", 2026, 9)
    assert [len(r.parts) for r in rows] == [1, 1, 1]


@pytest.mark.parametrize(
    ("second", "reason"),
    [
        (_run(R2, (45.0, 50.0), odo=1012), MERGE_VEHICLE_MOVED),
        (_run(R2, (45.0, 50.0), pos=AWAY), MERGE_DIFFERENT_PLACE),
        (_run(R1 + timedelta(hours=4), (45.0, 50.0)), MERGE_TOO_FAR_APART),
        (_run(R2, (45.0, 50.0), end_idle=False), MERGE_ONGOING),
    ],
)
async def test_merge_is_refused(second, reason):
    repo = _Repo(zones=[_zone("home_grid")], snaps=[*_run(R1), *second])
    with pytest.raises(MergeError) as err:
        await merge_charge_sessions(repo, "V1", [R1, second[0].timestamp])
    assert err.value.reason == reason
    assert repo.costs == []


async def test_different_tiers_need_a_choice():
    repo = _three_runs_repo(
        costs=[
            _record(1, R1, R1 + timedelta(hours=1), tier="home_grid"),
            _record(2, R2, R2 + timedelta(hours=1), tier="home_solar"),
        ]
    )
    with pytest.raises(MergeError) as err:
        await merge_charge_sessions(repo, "V1", [R1, R2])
    assert err.value.reason == MERGE_TIER_CONFLICT
    merged = await merge_charge_sessions(repo, "V1", [R1, R2], tier_id="home_solar")
    assert merged.tier_id == "home_solar"


async def test_merged_session_is_priced_run_by_run():
    """The pause between runs must not be billed at the band it falls in."""
    night = ChargingTimeBand(
        id=1,
        name="Night",
        price_kwh=0.10,
        schedule=[
            {
                "days": list(range(7)),
                "start_hour": 23,
                "start_min": 0,
                "end_hour": 7,
                "end_min": 0,
            }
        ],
    )
    late = T0 + timedelta(hours=2)  # 23:00, night band
    repo = _Repo(
        zones=[_zone("home_grid")],
        snaps=[*_run(T0, (40.0, 45.0)), *_run(late, (45.0, 50.0))],
        settings={"home_pricing_mode": "time_of_use"},
    )
    repo.bands = [night]
    merged = await merge_charge_sessions(repo, "V1", [T0, late])
    # 5 kWh at the flat 0.25 + 5 kWh at the night 0.10 (whole window: 2.0)
    assert merged.cost == 1.75


async def test_max_gap_is_chosen_per_merge():
    late = R1 + timedelta(hours=4)  # 3 h pause after the first run
    repo = _Repo(zones=[_zone("home_grid")], snaps=[*_run(R1), *_run(late)])
    with pytest.raises(MergeError):
        await merge_charge_sessions(repo, "V1", [R1, late])
    merged = await merge_charge_sessions(
        repo, "V1", [R1, late], max_gap=timedelta(hours=3)
    )
    assert merged.energy_kwh == 10.0


def test_merge_endpoint_validates_max_gap(auth_client):
    resp = auth_client.post(
        "/api/vehicles/V1/charging-costs/merge",
        json={"start_ts": ["2026-09-10T21:00:00"], "max_gap_minutes": 0},
    )
    assert resp.status_code == 422


def test_merge_endpoint_reports_the_reason(auth_client):
    resp = auth_client.post(
        "/api/vehicles/V1/charging-costs/merge",
        json={"start_ts": ["2026-09-10T21:00:00"]},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Can't merge: select at least two sessions"


async def test_preview_lists_included_sessions_and_gap_checks():
    repo = _three_runs_repo(costs=[_record(1, R1, R1 + timedelta(hours=1))])
    plan = await plan_merge(repo, "V1", [R1, R3])
    assert [(r.start_ts, r.record is not None) for r in plan.rows] == [
        (R1, True),
        (R2, False),  # in between: included although not selected
        (R3, False),
    ]
    assert [
        (g.minutes, g.within_max_gap, g.same_odometer, g.same_place) for g in plan.gaps
    ] == [
        (30, True, True, True),
        (30, True, True, True),
    ]
    assert (plan.reason, plan.tier_id, plan.zone_name) == (None, "home_grid", "Home")
    assert (plan.energy_kwh, plan.cost) == (12.0, 3.0)
    assert repo.costs[0].energy_kwh is None  # nothing saved


async def test_preview_flags_the_failing_pause():
    moved = _run(R2, (45.0, 50.0), odo=1012)
    repo = _Repo(zones=[_zone("home_grid")], snaps=[*_run(R1), *moved])
    plan = await plan_merge(repo, "V1", [R1, R2], max_gap=timedelta(minutes=10))
    [gap] = plan.gaps
    assert (gap.within_max_gap, gap.same_odometer, gap.same_place) == (
        False,
        False,
        True,
    )
    assert plan.reason == MERGE_VEHICLE_MOVED


async def test_preview_asks_for_a_tier_when_they_differ():
    repo = _three_runs_repo(
        costs=[
            _record(1, R1, R1 + timedelta(hours=1), tier="home_grid"),
            _record(2, R2, R2 + timedelta(hours=1), tier="home_solar"),
        ]
    )
    plan = await plan_merge(repo, "V1", [R1, R2])
    assert (plan.reason, plan.tier_id, plan.tiers) == (
        MERGE_TIER_CONFLICT,
        None,
        ["home_grid", "home_solar"],
    )
    chosen = await plan_merge(repo, "V1", [R1, R2], tier_id="home_solar")
    assert (chosen.reason, chosen.tier_id) == (None, "home_solar")


def test_merge_preview_endpoint(auth_client):
    resp = auth_client.post(
        "/api/vehicles/V1/charging-costs/merge/preview",
        json={"start_ts": ["2026-09-10T21:00:00", "2026-09-10T23:00:00"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert (body["reason"], body["sessions"], body["max_gap_minutes"]) == (
        "too_few",
        [],
        120,
    )


async def test_run_goes_to_the_closest_record():
    """A run 6 s after one record and 97 s before the next belongs to the first."""
    run_start = R1
    near = _record(1, run_start + timedelta(seconds=6), run_start + timedelta(hours=1))
    later = _record(2, run_start + timedelta(seconds=97), None)
    repo = _Repo(snaps=_run(run_start), costs=[later, near])
    rows = await list_month_sessions(repo, "V1", 2026, 9)
    assert {r.record.id: len(r.parts) for r in rows} == {1: 1, 2: 0}


async def test_stale_first_gps_fix_does_not_change_the_place():
    """The first fix of a run can be left over from before the car woke up."""
    stale = [_snap(R1, charging=True, kwh=40.0, pos=AWAY)]
    first = stale + _run(R1 + timedelta(minutes=1), (41.0, 45.0))
    repo = _Repo(zones=[_zone("home_grid")], snaps=[*first, *_run(R2)])
    plan = await plan_merge(repo, "V1", [R1, R2])
    assert plan.reason is None and plan.zone_name == "Home"


async def test_runless_record_inside_another_session_is_a_duplicate():
    """Issue #31: a record created at the UTC month start for a charge that
    another record already covers."""
    real = _record(1, R1, R1 + timedelta(hours=1))
    dup = _record(2, R1 + timedelta(minutes=40), R1 + timedelta(minutes=58))
    repo = _Repo(snaps=_run(R1), costs=[real, dup])
    rows = {r.record.id: r for r in await list_month_sessions(repo, "V1", 2026, 9)}
    assert rows[2].duplicate_of is real and rows[1].duplicate_of is None
    # Never costed by the month-end calculation
    missing = await find_month_missing_costs(repo, "V1", 2026, 9)
    assert [m.cost_id for m in missing] == [1]


async def test_preview_points_at_the_session_with_a_problem():
    """Issue #31 duplicate selected for a merge: the preview names it and still
    proposes the tier the sessions share."""
    real = _record(1, R1, R1 + timedelta(hours=1))
    dup = _record(2, R1 + timedelta(minutes=40), R1 + timedelta(minutes=58))
    repo = _Repo(zones=[_zone("home_grid")], snaps=_run(R1), costs=[real, dup])
    plan = await plan_merge(repo, "V1", [R1, dup.start_ts])
    assert plan.problems == [None, "duplicate"]
    assert (plan.reason, plan.tier_id) == ("duplicate", "home_grid")
