"""Extra costs of a charging session and the price per kWh entered by hand."""

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from leapconnect.application.charging_costs import (
    list_month_sessions,
    merge_charge_sessions,
)
from leapconnect.domain.charging.extras import (
    extra_cost,
    find_departure,
    find_unplug,
    price_extras,
)
from leapconnect.domain.charging.models import (
    ChargingSessionCost,
    ChargingSessionExtra,
)
from leapconnect.domain.telemetry.models import VehicleSnapshot
from leapconnect.infrastructure.persistence.tables import ChargingSessionExtraRow
from tests.test_charging_costs import COSTS_URL, _create_session_cost, _Repo
from tests.test_charging_merge import R1, R2, _record, _three_runs_repo

T0 = datetime(2026, 9, 12, 10, 0)
END = T0 + timedelta(hours=1)


def _snap(minutes, *, plugged=True, odo=1000, speed=0, charging=False):
    return VehicleSnapshot(
        vin="V1",
        timestamp=END + timedelta(minutes=minutes),
        vehicle_is_plugged=plugged,
        drive_total_mileage=odo,
        drive_speed=speed,
        battery_is_charging=charging,
    )


# Plugged in until END + 105 min, leaves at END + 130 min
AFTER_CHARGE = [
    _snap(0),
    _snap(60),
    _snap(105, plugged=False),
    _snap(120, plugged=False),
    _snap(130, plugged=False, odo=1002, speed=30),
]


def _idle_fee(**kwargs):
    # 6 €/h from 60 minutes after the charge end until the unplug
    fields = dict(kind="time", rate=6.0, start_offset_min=60, end_ref="unplug")
    return ChargingSessionExtra(**{**fields, **kwargs})


def _price(extra, *, unplug=END + timedelta(minutes=105), departure=None):
    price_extras(
        [extra],
        energy_kwh=14.0,
        energy_cost=6.0,
        start_ts=T0,
        end_ts=END,
        unplug_ts=unplug,
        departure_ts=departure,
    )
    return extra


# -- domain -------------------------------------------------------------------


def test_unplug_and_departure_are_found_after_the_charge():
    assert find_unplug(AFTER_CHARGE, END) == END + timedelta(minutes=105)
    assert find_departure(AFTER_CHARGE, END) == END + timedelta(minutes=130)
    assert find_unplug(AFTER_CHARGE[:2], END) is None
    assert find_unplug(AFTER_CHARGE, None) is None


@pytest.mark.parametrize(
    "extra, expected",
    [
        (ChargingSessionExtra(kind="fixed", amount=0.5), 0.5),
        (ChargingSessionExtra(kind="fixed", amount=-2.0), -2.0),  # discount
        (ChargingSessionExtra(kind="per_kwh", rate=0.05), 0.7),
        (ChargingSessionExtra(kind="percent", rate=10), 0.6),
        (ChargingSessionExtra(kind="per_kwh"), None),  # no rate
    ],
)
def test_extra_cost_by_kind(extra, expected):
    assert extra_cost(extra, energy_kwh=14.0, energy_cost=6.0) == expected


def test_idle_fee_after_a_grace_period():
    extra = _price(_idle_fee())
    assert (extra.minutes, extra.cost) == (45, 4.5)


@pytest.mark.parametrize(
    "kwargs, minutes, cost",
    [
        ({"billing": "started"}, 45, 6.0),  # every started hour billed whole
        ({"time_unit": "minute", "rate": 0.2}, 45, 9.0),
        ({"cap": 3.0}, 45, 3.0),
        ({"end_ref": "departure"}, 70, 7.0),
        ({"end_ref": "manual", "duration_min": 30}, 30, 3.0),
        # A per-minute charging fee: from the charge start to its end
        (
            {
                "start_ref": "charge_start",
                "start_offset_min": 0,
                "end_ref": "charge_end",
            },
            60,
            6.0,
        ),
    ],
)
def test_time_based_extra_options(kwargs, minutes, cost):
    extra = _price(_idle_fee(**kwargs), departure=END + timedelta(minutes=130))
    assert (extra.minutes, extra.cost) == (minutes, cost)


def test_unplugged_within_the_grace_period_costs_nothing():
    extra = _price(_idle_fee(), unplug=END + timedelta(minutes=20))
    assert (extra.minutes, extra.cost) == (0, 0.0)


def test_time_based_extra_waits_for_the_unplug():
    extra = _price(_idle_fee(), unplug=None)
    assert (extra.minutes, extra.cost) == (None, None)


def test_session_total_counts_only_included_extras():
    sc = ChargingSessionCost(
        cost=6.0,
        extras=[
            ChargingSessionExtra(kind="fixed", amount=0.5, cost=0.5),
            ChargingSessionExtra(kind="fixed", amount=3.0, cost=3.0, included=False),
            ChargingSessionExtra(kind="time", rate=6.0, cost=None),  # pending
        ],
    )
    assert (sc.extras_total, sc.total_cost) == (0.5, 6.5)
    assert ChargingSessionCost().total_cost is None


# -- application ----------------------------------------------------------------


async def test_session_list_prices_extras_waiting_for_the_unplug():
    charge = [
        VehicleSnapshot(
            vin="V1",
            timestamp=T0 + timedelta(minutes=m),
            battery_is_charging=True,
            vehicle_is_plugged=True,
            battery_dump_energy=e * 1000,
        )
        for m, e in ((0, 40.0), (60, 54.0))
    ]
    record = ChargingSessionCost(
        id=1, vin="V1", start_ts=T0, end_ts=END, tier_id="public_ac", cost=6.0
    )
    record.extras = [_idle_fee()]
    repo = _Repo(snaps=charge + AFTER_CHARGE[1:], costs=[record])
    [row] = await list_month_sessions(repo, "V1", 2026, 9)
    assert row.unplug_ts == END + timedelta(minutes=105)
    assert row.departure_ts == END + timedelta(minutes=130)
    assert record.extras[0].cost == 4.5


async def test_merge_keeps_the_extras_of_every_part():
    first, second = _record(1, R1, R1 + timedelta(hours=1)), _record(2, R2, R2)
    second.end_ts = R2 + timedelta(hours=1)
    first.extras = [ChargingSessionExtra(kind="fixed", label="Session", amount=0.5)]
    second.extras = [ChargingSessionExtra(kind="fixed", label="Parking", amount=2.0)]
    first.manual_price_kwh = 0.43
    repo = _three_runs_repo(costs=[first, second])
    merged = await merge_charge_sessions(repo, "V1", [R1, R2])
    assert [e.label for e in merged.extras] == ["Session", "Parking"]
    assert merged.extras_total == 2.5 and merged.manual_price_kwh is None
    assert merged.total_cost == merged.cost + 2.5


# -- endpoint -------------------------------------------------------------------


def test_price_per_kwh_follows_the_energy(auth_client):
    session = _create_session_cost(auth_client, energy_kwh=14.0, manual_price_kwh=0.43)
    assert (session["cost"], session["manual_price_kwh"]) == (6.02, 0.43)
    assert session["cost_manual"] is False
    response = auth_client.put(
        f"{COSTS_URL}/{session['id']}", json={"energy_kwh": 15.0}
    )
    assert response.json()["cost"] == 6.45


def test_a_total_cost_replaces_the_price_per_kwh(auth_client):
    session = _create_session_cost(auth_client, manual_price_kwh=0.43)
    response = auth_client.put(
        f"{COSTS_URL}/{session['id']}", json={"cost": 5.0, "manual_price_kwh": None}
    )
    body = response.json()
    assert (body["cost"], body["cost_manual"], body["manual_price_kwh"]) == (
        5.0,
        True,
        None,
    )
    # Both empty: back to the tier's price
    response = auth_client.put(
        f"{COSTS_URL}/{session['id']}", json={"cost": None, "manual_price_kwh": None}
    )
    assert response.json()["cost"] == 2.5


def test_cost_and_price_per_kwh_together_are_rejected(auth_client):
    session = _create_session_cost(auth_client)
    response = auth_client.put(
        f"{COSTS_URL}/{session['id']}", json={"cost": 5.0, "manual_price_kwh": 0.4}
    )
    assert response.status_code == 422


EXTRAS = [
    {"kind": "fixed", "label": "Session fee", "amount": 0.5},
    {
        "kind": "time",
        "label": "Idle fee",
        "rate": 6.0,
        "start_offset_min": 60,
        "end_ref": "manual",
        "duration_min": 45,
    },
    {"kind": "fixed", "label": "Parking", "amount": 3.0, "included": False},
]


def test_extras_are_saved_and_added_to_the_total(auth_client):
    session = _create_session_cost(auth_client)
    response = auth_client.put(f"{COSTS_URL}/{session['id']}", json={"extras": EXTRAS})
    assert response.status_code == 200
    [stored] = auth_client.get(COSTS_URL).json()
    assert [(e["label"], e["cost"]) for e in stored["extras"]] == [
        ("Session fee", 0.5),
        ("Idle fee", 4.5),
        ("Parking", 3.0),
    ]
    assert (stored["cost"], stored["extras_total"], stored["total_cost"]) == (
        2.5,
        5.0,
        7.5,
    )
    # Omitted: kept; empty list: removed
    auth_client.put(f"{COSTS_URL}/{session['id']}", json={"note": "receipt"})
    assert len(auth_client.get(COSTS_URL).json()[0]["extras"]) == 3
    auth_client.put(f"{COSTS_URL}/{session['id']}", json={"extras": []})
    assert auth_client.get(COSTS_URL).json()[0]["extras"] == []


@pytest.mark.parametrize(
    "extra",
    [
        {"kind": "fixed"},  # no amount
        {"kind": "time", "end_ref": "manual", "rate": 1.0},  # no duration
        {"kind": "percent"},  # no rate
        {"kind": "per_kwh", "rate": -1},
        {"kind": "tip", "amount": 1},
    ],
)
def test_invalid_extras_are_rejected(auth_client, extra):
    session = _create_session_cost(auth_client)
    response = auth_client.put(f"{COSTS_URL}/{session['id']}", json={"extras": [extra]})
    assert response.status_code == 422


def test_deleting_a_session_deletes_its_extras(auth_client):
    session = _create_session_cost(auth_client, extras=EXTRAS)
    assert auth_client.delete(f"{COSTS_URL}/{session['id']}").status_code == 200
    # Imported here: the container must be built inside the client fixture
    from leapconnect.container import container

    async def count_extras():
        async with container.repo._session_factory() as db:
            result = await db.execute(select(func.count(ChargingSessionExtraRow.id)))
            return result.scalar()

    assert asyncio.run(count_extras()) == 0
