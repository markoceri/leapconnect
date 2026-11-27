"""Charging providers (EVDC, ...): matching, applying and importing billed
sessions, charging points and charge sites."""

from dataclasses import replace
from datetime import datetime, timedelta

import pytest
from evdc_network_api import ChargingSession

from leapconnect.api.routers import charging_providers
from leapconnect.application.charging_providers import (
    apply_provider_import,
    charge_sites,
    find_link_candidates,
    find_stations,
    link_provider_session,
    preview_provider_import,
    unlink_provider_record,
)
from leapconnect.application.ports.charging_provider import ChargingProvider
from leapconnect.application.settings_store import recalculate_session
from leapconnect.domain.charging.models import (
    ChargingSessionCost,
    ChargingSessionExtra,
)
from leapconnect.domain.charging.providers import (
    DISMISSED,
    ELSEWHERE,
    IMPORTED,
    MATCHED,
    UNCERTAIN,
    UNMATCHED,
    ProviderFee,
    ProviderSession,
    apply_provider_session,
    match_provider_sessions,
    new_record_for,
)
from leapconnect.domain.charging.sessions import (
    ChargeSessionRow,
    DetectedChargeSession,
)
from leapconnect.domain.charging.stations import ChargingStation
from leapconnect.infrastructure.evdc.service import to_provider_session
from tests.test_charging_costs import COSTS_URL, _Repo, _snaps

T0 = datetime(2026, 10, 24, 15, 40)
END = T0 + timedelta(hours=2)


def _ps(external_id="S1", start=T0, end=END, **kwargs):
    fields = dict(energy_kwh=14.07, cost=6.55, price_kwh=0.43)
    return ProviderSession(
        provider="evdc",
        external_id=external_id,
        started_at=start,
        ended_at=end,
        **{"account_id": 7, **fields, **kwargs},
    )


def _row(start, end, record=None):
    return ChargeSessionRow(start_ts=start, end_ts=end, record=record)


def _record(**kwargs):
    fields = dict(
        id=1, vin="V1", start_ts=T0, end_ts=END, tier_id="home_grid", cost=3.0
    )
    return ChargingSessionCost(**{**fields, **kwargs})


# -- domain: matching ---------------------------------------------------------


def test_sessions_are_matched_by_overlap():
    # The car sees the charge a few minutes after the charger starts it
    row = _row(T0 + timedelta(minutes=4), END - timedelta(minutes=1))
    far = _row(T0 - timedelta(days=1), T0 - timedelta(days=1) + timedelta(hours=1))
    [m] = match_provider_sessions([_ps()], [far, row])
    assert (m.status, m.row) == (MATCHED, row)


def test_a_session_outside_every_row_is_unmatched():
    [m] = match_provider_sessions([_ps()], [_row(END + timedelta(hours=1), None)])
    assert (m.status, m.row) == (UNMATCHED, None)


def test_an_imported_session_stays_with_its_record():
    record = _record(external_source="evdc", external_id="S1")
    row = _row(T0, END, record)
    other = _row(T0, END)  # overlaps too, but the import wins
    [m] = match_provider_sessions([_ps()], [other, row])
    assert (m.status, m.row) == (IMPORTED, row)


def test_one_row_per_provider_session():
    row = _row(T0, END)
    best = _ps("S1")
    worse = _ps("S2", start=END - timedelta(minutes=5), end=END + timedelta(hours=1))
    matches = {
        m.session.external_id: m for m in match_provider_sessions([worse, best], [row])
    }
    assert matches["S1"].status == MATCHED
    assert matches["S2"].status == UNMATCHED


def test_a_merged_session_takes_the_whole_charge():
    # Two runs merged into one record spanning both
    merged = _row(T0, END, _record())
    [m] = match_provider_sessions([_ps()], [merged])
    assert m.row is merged


# -- domain: applying ---------------------------------------------------------


def test_billed_values_replace_the_automatic_ones():
    sc = _record(energy_kwh=12.16)
    ps = _ps(fees=(ProviderFee("Parking fee", 0.5),))
    apply_provider_session(sc, ps)
    assert (sc.energy_kwh, sc.cost) == (14.07, 6.05)  # 6.55 billed − 0.50 fee
    assert [(e.label, e.cost, e.source) for e in sc.extras] == [
        ("Parking fee", 0.5, "evdc")
    ]
    assert sc.total_cost == 6.55
    assert (sc.tier_id, sc.external_source, sc.external_id) == (
        "public_ac",
        "evdc",
        "S1",
    )


def test_values_entered_by_hand_are_kept():
    sc = _record(energy_kwh=14.0, energy_manual=True, cost=8.0, cost_manual=True)
    apply_provider_session(sc, _ps())
    assert (sc.energy_kwh, sc.cost) == (14.0, 8.0)
    priced = _record(energy_kwh=14.0, manual_price_kwh=0.5, cost=7.0)
    apply_provider_session(priced, _ps())
    assert priced.cost == 7.0


def test_a_new_import_replaces_the_provider_extras_only():
    mine = ChargingSessionExtra(kind="fixed", label="Coffee", amount=2.0, cost=2.0)
    sc = _record(tier_id="public_dc")
    apply_provider_session(sc, _ps(fees=(ProviderFee("Time fee", 1.0),)))
    sc.extras.insert(0, mine)
    apply_provider_session(sc, _ps(fees=(ProviderFee("Time fee", 1.5),)))
    assert [(e.label, e.cost) for e in sc.extras] == [
        ("Coffee", 2.0),
        ("Time fee", 1.5),
    ]
    assert sc.tier_id == "public_dc"  # already public: kept


@pytest.mark.parametrize(
    "vehicle_dc, charger_dc, current, expected",
    [
        (True, None, "home_grid", "public_dc"),  # the vehicle saw a DC charge
        (False, True, "public_dc", "public_ac"),  # the vehicle wins
        (None, True, "home_grid", "public_dc"),  # no vehicle data: the charger
        (None, False, "public_dc", "public_ac"),
        (None, None, "public_dc", "public_dc"),  # nobody knows: kept
        (None, None, "home_solar", "public_ac"),
    ],
)
def test_imported_session_gets_the_public_tier_of_its_charge(
    vehicle_dc, charger_dc, current, expected
):
    sc = _record(tier_id=current)
    apply_provider_session(sc, _ps(is_dc=charger_dc), vehicle_dc=vehicle_dc)
    assert sc.tier_id == expected


def test_record_for_an_unmatched_session():
    sc = new_record_for("V1", _ps(operator="Ewiva", location="Via Roma 1, Milano"))
    assert (sc.start_ts, sc.end_ts, sc.tier_id) == (T0, END, "public_ac")
    assert (sc.energy_kwh, sc.cost, sc.note) == (
        14.07,
        6.55,
        "Ewiva · Via Roma 1, Milano",
    )


async def test_recalculation_keeps_the_billed_values():
    # Measured from the snapshots: 10 kWh at 0.25 €/kWh
    sc = ChargingSessionCost(
        vin="V1", start_ts=T0, end_ts=T0 + timedelta(hours=1), tier_id="public_ac"
    )
    apply_provider_session(sc, _ps())
    await recalculate_session(_Repo(snaps=_snaps((45.0, 9.0), start=T0)), sc)
    assert (sc.energy_kwh, sc.cost) == (14.07, 6.55)


# -- infrastructure: EVDC mapping -----------------------------------------------


def _evdc(**overrides):
    data = {
        "_id": "doc1",
        "sessionId": "S1",
        "evseId": "IT*EWI*E1",
        "operator": "Ewiva",
        "amount": 338000.0,
        "currency": "EVDC Token",
        "consumedEnergy": 14.07,
        "notificationDetails": {
            "chargingStart": "2026-10-24T13:40:00Z",
            "chargingEnd": "2026-10-24T15:40:00Z",
        },
        "pricingDetails": {"chargingPrice": 6.55, "Currency": "EUR"},
        "timeDetails": {"durationInMinutes": 120, "timeFee": 0},
        "parkingDetails": {"durationInMinutes": 30, "parkingFee": 0.5},
        "evseDetails": {"address": {"Street": "Via Roma 1", "City": "Milano"}},
        "chargingStation": {
            "EvseData": {
                "EvseID": "IT*EWI*E1",
                "ChargingFacilities": [{"Power": 150, "PowerType": "DC"}],
            }
        },
        "isSessionFailed": False,
        "isTestSession": False,
    }
    return ChargingSession.from_dict({**data, **overrides})


def test_evdc_session_mapping():
    ps = to_provider_session(_evdc())
    assert ps.external_id == "S1"
    # Naive UTC, like every stored timestamp
    assert (ps.started_at, ps.ended_at) == (
        datetime(2026, 10, 24, 13, 40),
        datetime(2026, 10, 24, 15, 40),
    )
    # The real-money price, though it was paid with tokens
    assert (ps.cost, ps.currency, ps.energy_kwh) == (6.55, "EUR", 14.07)
    assert ps.fees == (ProviderFee("Parking fee", 0.5),)  # zero fees left out
    assert ps.location == "Via Roma 1, Milano"
    assert ps.is_dc is True
    assert ps.station.evse_id == "IT*EWI*E1" and ps.station.max_power_kw == 150


@pytest.mark.parametrize(
    "overrides",
    [{"isSessionFailed": True}, {"isTestSession": True}, {"pricingDetails": {}}],
)
def test_failed_test_and_unbilled_evdc_sessions_are_skipped(overrides):
    assert to_provider_session(_evdc(**overrides)) is None


# -- application ----------------------------------------------------------------


class FakeProvider(ChargingProvider):
    provider = "evdc"
    label = "EVDC"

    def __init__(self, sessions, connected=True, account_id=7, stations=(), ongoing=()):
        self.sessions = list(sessions)
        self.ongoing = list(ongoing)
        self._connected = connected
        self._account_id = account_id
        self._auto_sync = True
        self.stations = list(stations)
        self.searches = 0
        self.wallets = []
        self.payments = []
        self._threshold = None
        self._alerted = False

    @property
    def account_id(self):
        return self._account_id

    @property
    def username(self):
        return f"you{self._account_id}@example.com"

    @property
    def connected(self):
        return self._connected

    @property
    def auto_sync(self):
        return self._auto_sync

    async def set_auto_sync(self, enabled):
        self._auto_sync = enabled

    async def disconnect(self):
        self._connected = False

    async def fetch_sessions(self, since):
        return [s for s in self.sessions if s.started_at >= since]

    async def get_ongoing_sessions(self):
        return list(self.ongoing)

    @property
    def low_balance_threshold(self):
        return self._threshold

    @property
    def low_balance_alerted(self):
        return self._alerted

    async def set_low_balance(self, threshold=None, *, alerted=None):
        if alerted is None:
            self._threshold, self._alerted = threshold, False
        else:
            self._alerted = alerted

    async def get_wallets(self):
        return list(self.wallets)

    async def get_payments(self, since):
        return [p for p in self.payments if p.created_at >= since]

    async def get_receipt(self, external_id):
        return "receipt.pdf", b"%PDF-1.4 receipt " + external_id.encode()

    async def get_station(self, evse_id):
        return next((s for s in self.stations if s.evse_id == evse_id), None)

    async def find_stations(self, latitude, longitude, radius_m):
        self.searches += 1
        return list(self.stations)


class FakeRegistry:
    """The registry the router uses, with fake accounts."""

    def __init__(self, *providers):
        self.providers = list(providers)

    def all(self):
        return list(self.providers)

    def connected(self):
        return [p for p in self.providers if p.connected]

    def get(self, account_id):
        return next((p for p in self.providers if p.account_id == account_id), None)

    async def remove(self, account_id):
        p = self.get(account_id)
        if p is None:
            return False
        self.providers.remove(p)
        return True


MONTH = (datetime(2026, 10, 1), datetime(2026, 11, 1))


async def test_preview_and_apply():
    record = _record(energy_kwh=12.16)
    repo = _Repo(costs=[record])
    lost = _ps("S2", start=T0 + timedelta(days=2), end=T0 + timedelta(days=2, hours=1))
    provider = FakeProvider([_ps(), lost])

    preview = await preview_provider_import(repo, [provider], "V1", *MONTH)
    assert [(i.match.status, i.match.session.external_id) for i in preview] == [
        (MATCHED, "S1"),
        (UNMATCHED, "S2"),
    ]
    assert preview[0].proposed.cost == 6.55 and record.cost == 3.0  # not saved

    result = await apply_provider_import(
        repo, [provider], "V1", *MONTH, create_ids={"S2"}
    )
    assert (result.applied, result.created) == (1, 1)
    assert (record.cost, record.external_id) == (6.55, "S1")
    assert record.provider_account_id == 7
    assert sorted(c.external_id for c in repo.costs) == ["S1", "S2"]

    # Importing again doesn't duplicate: both are already imported
    again = await preview_provider_import(repo, [provider], "V1", *MONTH)
    assert [i.match.status for i in again] == [IMPORTED, IMPORTED]
    await apply_provider_import(repo, [provider], "V1", *MONTH)
    assert len(repo.costs) == 2


async def test_apply_without_create_skips_unmatched():
    repo = _Repo()
    result = await apply_provider_import(repo, [FakeProvider([_ps()])], "V1", *MONTH)
    assert (result.applied, result.created, result.skipped) == (0, 0, ["S1"])
    assert repo.costs == []


# -- endpoint -------------------------------------------------------------------


@pytest.fixture
def provider(auth_client):
    fake = FakeProvider([])
    registry = FakeRegistry(fake)
    auth_client.app.dependency_overrides[charging_providers.get_registry] = lambda: (
        registry
    )
    yield fake
    auth_client.app.dependency_overrides.clear()


def _create_record(client):
    response = client.post(
        COSTS_URL,
        json={
            "start_ts": T0.isoformat(),
            "end_ts": END.isoformat(),
            "tier_id": "public_ac",
            "energy_kwh": 12.0,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_import_endpoints(auth_client, provider):
    record = _create_record(auth_client)
    provider.sessions = [_ps(fees=(ProviderFee("Parking fee", 0.5),))]
    url = "/api/vehicles/V1/charging-costs/import"
    preview = auth_client.post(f"{url}/preview", json={"year": 2026, "month": 10})
    assert preview.status_code == 200
    [item] = preview.json()["items"]
    assert item["status"] == "matched" and item["current"]["id"] == record["id"]
    assert item["session"]["provider_label"] == "EVDC"
    assert item["session"]["account_username"] == "you7@example.com"
    assert item["energy_kept"] is True  # entered when created: kept
    assert item["proposed"]["total_cost"] == 6.55

    applied = auth_client.post(f"{url}/apply", json={"year": 2026, "month": 10})
    assert applied.json() == {"applied": 1, "created": 0, "skipped": 0}
    [stored] = auth_client.get(COSTS_URL).json()
    assert (stored["external_source"], stored["external_id"]) == ("evdc", "S1")
    assert stored["energy_kwh"] == 12.0  # manual: kept
    assert stored["extras"][0]["source"] == "evdc"

    # Saving the dialog (cost empty, the user's extras only) keeps the billed
    # cost and the provider's extras
    response = auth_client.put(
        f"{COSTS_URL}/{record['id']}", json={"cost": None, "extras": [], "note": "x"}
    )
    body = response.json()
    assert (body["cost"], len(body["extras"])) == (6.05, 1)
    # Recalculating would replace the billed values
    recalc = auth_client.post(f"{COSTS_URL}/{record['id']}/recalculate")
    assert recalc.status_code == 409

    receipt = auth_client.get(f"{COSTS_URL}/{record['id']}/receipt")
    assert receipt.headers["content-type"] == "application/pdf"
    assert receipt.content.endswith(b"S1")


def test_import_needs_a_connected_account(auth_client, provider):
    provider._connected = False
    url = "/api/vehicles/V1/charging-costs/import/preview"
    response = auth_client.post(url, json={"year": 2026, "month": 10})
    assert response.status_code == 409
    response = auth_client.post(url, json={"year": 2026, "month": 10, "account_id": 99})
    assert response.status_code == 404
    listed = auth_client.get("/api/charging/providers").json()
    assert [t["id"] for t in listed["types"]] == ["evdc"]
    [account] = listed["accounts"]
    assert account["connected"] is False and account["label"] == "EVDC"


def test_provider_account_settings(auth_client, provider):
    response = auth_client.put("/api/charging/providers/7", json={"auto_sync": False})
    assert response.json()["auto_sync"] is False
    assert auth_client.delete("/api/charging/providers/7").status_code == 204
    assert auth_client.get("/api/charging/providers").json()["accounts"] == []
    assert auth_client.delete("/api/charging/providers/7").status_code == 404


# -- other vehicles on the same account -----------------------------------------

MILANO = (45.4642, 9.1900)
TORINO = (45.0703, 7.6869)


def _charged_row(record=None, *, kwh=13.2, pos=MILANO, dc=False):
    part = DetectedChargeSession(
        start_ts=T0 + timedelta(minutes=3),
        end_ts=END,
        energy_kwh=kwh,
        latitude=pos[0],
        longitude=pos[1],
        is_dc=dc,
    )
    return ChargeSessionRow(start_ts=T0, end_ts=END, record=record, parts=(part,))


def _at(pos, **kwargs):
    return _ps(latitude=pos[0], longitude=pos[1], **kwargs)


def test_a_charger_far_from_the_car_is_uncertain():
    # Same time, but EVDC billed a charge in Turin: another vehicle's
    [m] = match_provider_sessions([_at(TORINO)], [_charged_row()])
    assert m.status == UNCERTAIN
    assert "km from where the car charged" in m.problems[0]


def test_swapped_charger_coordinates_still_match():
    # A few EVDC records have latitude and longitude swapped
    swapped = _ps(latitude=MILANO[1], longitude=MILANO[0])
    [m] = match_provider_sessions([swapped], [_charged_row()])
    assert (m.status, m.problems) == (MATCHED, ())


@pytest.mark.parametrize("billed, status", [(14.07, MATCHED), (40.0, UNCERTAIN)])
def test_the_billed_energy_must_fit_the_measured_one(billed, status):
    # The car took 13.2 kWh: 14.07 billed fits (losses), 40 doesn't
    [m] = match_provider_sessions([_at(MILANO, energy_kwh=billed)], [_charged_row()])
    assert m.status == status


def test_a_plausible_session_wins_over_a_larger_overlap():
    other_car = _at(TORINO, external_id="OTHER")  # overlaps the whole charge
    mine = _at(MILANO, external_id="MINE", start=T0 + timedelta(minutes=30), end=END)
    matches = {
        m.session.external_id: m
        for m in match_provider_sessions([other_car, mine], [_charged_row()])
    }
    assert matches["MINE"].status == MATCHED
    assert matches["OTHER"].status == UNMATCHED


def test_a_session_linked_elsewhere_is_left_alone():
    [m] = match_provider_sessions([_at(MILANO)], [_charged_row()], {("evdc", "S1")})
    assert (m.status, m.row) == (ELSEWHERE, None)


def test_a_session_the_user_unlinked_is_dismissed():
    record = _record(auto_link_disabled=True)
    [m] = match_provider_sessions([_at(MILANO)], [_charged_row(record)])
    assert m.status == DISMISSED


class _VinRepo(_Repo):
    """_Repo holding the records of several vehicles."""

    async def get_session_costs(self, vin, **kwargs):
        return [c for c in self.costs if c.vin == vin]


async def test_one_provider_session_for_one_vehicle_only():
    first = _record(id=1, vin="V1", tier_id="public_ac")
    second = _record(id=2, vin="V2", tier_id="public_ac")
    repo = _VinRepo(costs=[first, second])
    provider = FakeProvider([_ps()])
    await apply_provider_import(repo, [provider], "V1", *MONTH)
    await apply_provider_import(repo, [provider], "V2", *MONTH)
    assert (first.external_id, second.external_id) == ("S1", None)
    [item] = await preview_provider_import(repo, [provider], "V2", *MONTH)
    assert item.match.status == ELSEWHERE


async def test_automatic_import_skips_uncertain_and_dismissed_matches():
    dismissed = _record(id=2, start_ts=T0 + timedelta(days=1), auto_link_disabled=True)
    dismissed.end_ts = dismissed.start_ts + timedelta(hours=2)
    repo = _Repo(costs=[dismissed])
    later = _ps("S2", start=dismissed.start_ts, end=dismissed.end_ts)
    provider = FakeProvider([later])
    result = await apply_provider_import(repo, [provider], "V1", *MONTH)
    assert (result.applied, dismissed.external_id) == (0, None)
    # Chosen explicitly in the import dialog: linked
    await apply_provider_import(repo, [provider], "V1", *MONTH, external_ids={"S2"})
    assert dismissed.external_id == "S2" and not dismissed.auto_link_disabled


# -- one session picked by hand ---------------------------------------------------


async def test_candidates_link_and_unlink():
    record = _record(energy_kwh=12.16)
    repo = _Repo(costs=[record])
    near = _ps("NEAR", start=END + timedelta(hours=2), end=END + timedelta(hours=3))
    provider = FakeProvider([_ps(), near])

    candidates = await find_link_candidates(repo, [provider], "V1", cost_id=1)
    assert [c.candidate.session.external_id for c in candidates] == ["S1", "NEAR"]
    assert candidates[0].best and candidates[0].proposed.cost == 6.55
    assert candidates[1].candidate.overlap is None  # close in time only

    linked = await link_provider_session(repo, provider, "V1", "NEAR", cost_id=1)
    assert linked.external_id == "NEAR"  # the user's choice, no overlap needed

    unlinked = await unlink_provider_record(repo, "V1", 1)
    assert unlinked.external_id is None and unlinked.auto_link_disabled
    # Priced with the tier again (home_grid at 0.25 €/kWh)
    assert unlinked.tier_id == "public_ac" and unlinked.cost == 3.5175


async def test_linking_moves_a_provider_session_from_another_record():
    first = _record(id=1, external_source="evdc", external_id="S1", cost=6.55)
    second = _record(id=2, start_ts=T0 + timedelta(minutes=5))
    repo = _Repo(costs=[first, second])
    await link_provider_session(repo, FakeProvider([_ps()]), "V1", "S1", cost_id=2)
    assert (first.external_id, second.external_id) == (None, "S1")
    assert not first.auto_link_disabled  # moved, not unlinked by the user


def test_link_endpoints(auth_client, provider):
    record = _create_record(auth_client)
    provider.sessions = [_ps()]
    url = "/api/vehicles/V1/charging-costs"
    found = auth_client.get(f"{url}/link/candidates", params={"cost_id": record["id"]})
    [candidate] = found.json()["candidates"]
    assert candidate["best"] is True and candidate["overlap_minutes"] == 120
    assert candidate["session"]["account_id"] == 7

    linked = auth_client.post(
        f"{url}/link",
        json={"account_id": 7, "external_id": "S1", "cost_id": record["id"]},
    )
    assert linked.json()["external_id"] == "S1"
    assert linked.json()["provider_account_id"] == 7
    unlinked = auth_client.delete(f"{url}/{record['id']}/link")
    body = unlinked.json()
    assert body["external_id"] is None and body["auto_link_disabled"] is True


# -- several accounts ---------------------------------------------------------------


async def test_sessions_of_several_accounts():
    # Two accounts: each session is imported with the account that read it
    mine = FakeProvider([_ps(account_id=1)], account_id=1)
    partner = FakeProvider(
        [
            _ps(
                "S2",
                start=T0 + timedelta(days=3),
                end=END + timedelta(days=3),
                account_id=2,
            )
        ],
        account_id=2,
    )
    second = _record(id=2, start_ts=T0 + timedelta(days=3))
    second.end_ts = END + timedelta(days=3)
    repo = _Repo(costs=[_record(), second])
    result = await apply_provider_import(repo, [mine, partner], "V1", *MONTH)
    assert result.applied == 2
    assert sorted((c.external_id, c.provider_account_id) for c in repo.costs) == [
        ("S1", 1),
        ("S2", 2),
    ]


async def test_a_session_read_by_two_accounts_counts_once():
    a = FakeProvider([_ps(account_id=1)], account_id=1)
    b = FakeProvider([_ps(account_id=2)], account_id=2)
    preview = await preview_provider_import(_Repo(), [a, b], "V1", *MONTH)
    assert len(preview) == 1


# -- charging points and charge sites ---------------------------------------------

STATION = ChargingStation(
    provider="evdc",
    evse_id="IT*EWI*E1",
    name="Ewiva Milano",
    latitude=MILANO[0],
    longitude=MILANO[1],
    max_power_kw=150,
    is_dc=True,
)


async def test_imported_sessions_cache_their_charging_point():
    repo = _Repo(costs=[_record()])
    ps = _ps(evse_id=STATION.evse_id, station=STATION, latitude=1.0, longitude=2.0)
    await apply_provider_import(repo, [FakeProvider([ps])], "V1", *MONTH)
    [record] = repo.costs
    assert record.evse_id == STATION.evse_id
    # No GPS of its own: the charger's position
    assert (record.latitude, record.longitude) == (1.0, 2.0)
    assert await repo.get_charging_stations() == {("evdc", STATION.evse_id): STATION}


async def test_one_search_per_provider_type():
    a = FakeProvider([], account_id=1, stations=[STATION])
    b = FakeProvider([], account_id=2, stations=[STATION])
    result = await find_stations([a, b], *MILANO, 2000)
    assert result.stations == [STATION]
    assert (a.searches, b.searches) == (1, 0)
    assert (await find_stations([a], *MILANO, 2000, {"other"})).stations == []


async def test_charge_sites_group_sessions_by_place():
    near = (MILANO[0] + 0.0003, MILANO[1])  # ~30 m away
    records = [
        _record(id=1, latitude=MILANO[0], longitude=MILANO[1], energy_kwh=10.0),
        _record(
            id=2,
            start_ts=T0 + timedelta(days=5),
            latitude=near[0],
            longitude=near[1],
            energy_kwh=5.0,
            external_source="evdc",
            evse_id=STATION.evse_id,
        ),
        _record(
            id=3,
            start_ts=T0 + timedelta(days=1),
            latitude=TORINO[0],
            longitude=TORINO[1],
        ),
        _record(id=4),  # no position: not on the map
    ]
    repo = _Repo(costs=records)
    await repo.upsert_charging_stations([STATION])
    milano, torino = await charge_sites(repo, "V1")
    assert (milano.sessions, milano.energy_kwh) == (2, 15.0)
    assert milano.last_ts == T0 + timedelta(days=5) and milano.first_ts == T0
    assert milano.stations == [STATION]
    assert torino.sessions == 1


def test_station_endpoints(auth_client, provider):
    provider.stations = [STATION]
    found = auth_client.get(
        "/api/charging/stations",
        params={"lat": MILANO[0], "lon": MILANO[1], "radius_m": 1000},
    )
    [station] = found.json()["stations"]
    assert station["evse_id"] == STATION.evse_id and station["provider_label"] == "EVDC"
    too_far = auth_client.get(
        "/api/charging/stations",
        params={"lat": MILANO[0], "lon": MILANO[1], "radius_m": 50_000},
    )
    assert too_far.status_code == 422
    details = auth_client.get(f"/api/charging/stations/evdc/{STATION.evse_id}")
    assert details.json()["name"] == "Ewiva Milano"
    assert auth_client.get("/api/charging/stations/evdc/NOPE").status_code == 404
    sites = auth_client.get("/api/vehicles/V1/charge-sites")
    assert sites.status_code == 200 and sites.json() == {"sites": []}


# -- persistence -------------------------------------------------------------------


@pytest.fixture
async def sql_repo(tmp_path):
    from leapconnect.infrastructure.persistence.sqlite_adapter import (
        SqlAlchemyRepository,
    )

    repo = SqlAlchemyRepository(f"sqlite+aiosqlite:///{tmp_path}/providers.db")
    await repo.init_db()
    yield repo
    await repo.close()


async def test_provider_accounts_are_stored_with_encrypted_credentials(sql_repo):
    from sqlalchemy import select

    from leapconnect.domain.charging.models import ChargingProviderAccount
    from leapconnect.infrastructure.charging_providers import ChargingProviderRegistry
    from leapconnect.infrastructure.persistence.tables import (
        ChargingProviderAccountRow,
    )

    account = await sql_repo.save_provider_account(
        ChargingProviderAccount(
            provider="evdc",
            username="you@example.com",
            credentials={"user_id": "u1", "device_key": "SECRET-KEY"},
        )
    )
    async with sql_repo._session_factory() as session:
        raw = (await session.execute(select(ChargingProviderAccountRow))).scalar_one()
    assert "SECRET-KEY" not in raw.credentials
    [loaded] = await sql_repo.get_provider_accounts()
    assert loaded.credentials["device_key"] == "SECRET-KEY"

    # The registry serves it (a device key: connected without a password)
    registry = ChargingProviderRegistry(sql_repo)
    await registry.load()
    [service] = registry.all()
    assert (service.account_id, service.username, service.connected) == (
        account.id,
        "you@example.com",
        True,
    )
    assert await sql_repo.delete_provider_account(account.id)
    assert await sql_repo.get_provider_accounts() == []


async def test_charging_points_cache_keeps_known_details(sql_repo):
    await sql_repo.upsert_charging_stations([STATION])
    # A later read without some details doesn't lose them
    await sql_repo.upsert_charging_stations(
        [ChargingStation(provider="evdc", evse_id=STATION.evse_id, plugs=("CCS",))]
    )
    stored = (await sql_repo.get_charging_stations())[("evdc", STATION.evse_id)]
    assert (stored.name, stored.max_power_kw, stored.plugs) == (
        "Ewiva Milano",
        150,
        ("CCS",),
    )


async def test_session_records_keep_provider_refs_and_position(sql_repo):
    sc = await sql_repo.upsert_session_cost(
        _record(
            id=None,
            external_source="evdc",
            external_id="S1",
            provider_account_id=3,
            evse_id="IT*EWI*E1",
            latitude=45.1,
            longitude=9.2,
        )
    )
    [loaded] = await sql_repo.get_session_costs("V1")
    assert (loaded.id, loaded.provider_account_id, loaded.evse_id) == (
        sc.id,
        3,
        "IT*EWI*E1",
    )
    assert (loaded.latitude, loaded.longitude) == (45.1, 9.2)


async def test_the_first_version_evdc_account_is_moved(sql_repo):
    from leapconnect.infrastructure.charging_providers import ChargingProviderRegistry

    for key, value in {
        "evdc_email": "you@example.com",
        "evdc_user_id": "u1",
        "evdc_device_id": "d1",
        "evdc_device_key": "KEY",
        "evdc_access_token": "AT",
        "evdc_refresh_token": "RT",
        "evdc_auto_sync": "false",
    }.items():
        await sql_repo.save_setting(key, value)
    registry = ChargingProviderRegistry(sql_repo)
    await registry.load()
    [service] = registry.all()
    assert (service.username, service.connected, service.auto_sync) == (
        "you@example.com",
        True,
        False,
    )
    assert service.account.credentials["device_key"] == "KEY"
    assert await sql_repo.get_setting("evdc_device_key") == ""
    # Once only
    await registry.load()
    assert len(await sql_repo.get_provider_accounts()) == 1


# -- sessions in progress --------------------------------------------------------


def test_evdc_ongoing_session_mapping():
    from evdc_network_api import OngoingSession

    from leapconnect.infrastructure.evdc.service import to_ongoing_session

    raw = {
        "sessionId": "S9",
        "evseId": "IT*EWI*E1",
        "operator": "Ewiva",
        "amount": 0,
        "createdAt": "2026-11-26T10:00:00Z",
        "isChargingStarted": True,
        "notificationDetails": {"chargingStart": "2026-11-26T10:02:00Z"},
        "pricingDetails": {"costKwh": 0.59, "PreAuthHoldAmount": 30},
        "chargingStation": {
            "EvseData": {
                "EvseID": "IT*EWI*E1",
                "ChargingFacilities": [{"Power": 150, "PowerType": "DC"}],
            }
        },
    }
    o = to_ongoing_session(OngoingSession.from_dict(raw), account_id=3)
    assert (o.external_id, o.account_id, o.price_kwh, o.pre_auth_amount) == (
        "S9",
        3,
        0.59,
        30,
    )
    assert o.charging_started_at == datetime(2026, 11, 26, 10, 2)  # naive UTC
    assert o.station.is_dc is True
    stopped = OngoingSession.from_dict({**raw, "isStop": True})
    assert to_ongoing_session(stopped) is None


def _ongoing(**kwargs):
    from leapconnect.domain.charging.providers import ProviderOngoingSession

    fields = dict(
        provider="evdc",
        external_id="S9",
        account_id=7,
        created_at=T0,
        charging_started_at=T0,
        price_kwh=0.59,
        evse_id=STATION.evse_id,
    )
    return ProviderOngoingSession(**{**fields, **kwargs})


def test_ongoing_session_plausibility():
    from leapconnect.domain.charging.providers import ongoing_problems

    open_row = ChargeSessionRow(
        start_ts=T0,
        end_ts=None,
        parts=(
            DetectedChargeSession(
                start_ts=T0, end_ts=None, latitude=MILANO[0], longitude=MILANO[1]
            ),
        ),
    )
    assert ongoing_problems(_ongoing(station=STATION), open_row) == ()
    far = replace(STATION, latitude=TORINO[0], longitude=TORINO[1])
    assert (
        "km from where the car charged"
        in (ongoing_problems(_ongoing(station=far), open_row)[0])
    )
    assert ongoing_problems(_ongoing(), None) == ("the car isn't charging",)


async def test_ongoing_sessions_use_case():
    from leapconnect.application.charging_providers import ongoing_provider_sessions

    now = T0 + timedelta(hours=1, minutes=10)
    snaps = _snaps(MILANO, start=T0)  # still charging
    repo = _Repo(snaps=snaps)
    provider = FakeProvider([], ongoing=[_ongoing()], stations=[STATION])
    result = await ongoing_provider_sessions(repo, [provider], "V1", now)
    [item] = result.items
    # The charging point read from the provider (and cached)
    assert item.session.station == STATION
    assert item.row is not None and item.row.end_ts is None
    assert item.plausible
    assert item.estimated_cost == round(0.59 * item.row.energy_kwh, 2)


def test_ongoing_endpoint(auth_client, provider):
    provider.ongoing = [_ongoing(station=STATION)]
    response = auth_client.get("/api/vehicles/V1/charging-costs/ongoing")
    assert response.status_code == 200
    [item] = response.json()["sessions"]
    assert item["price_kwh"] == 0.59 and item["station"]["name"] == "Ewiva Milano"
    # No open charge of the car: not plausible
    assert item["plausible"] is False and item["problems"] == ["the car isn't charging"]


# -- live progress ------------------------------------------------------------------


class _FakeLiveClient:
    """Stands in for EvdcLiveClient: connect/disconnect, progress pushed by
    the test."""

    instances: list = []

    def __init__(self, client, on_progress):
        self.on_progress = on_progress
        self.connected = False
        _FakeLiveClient.instances.append(self)

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False


def _progress(session_id="S9", kwh=12.5):
    from evdc_network_api import SessionProgress

    return SessionProgress.from_dict(
        {
            "SessionID": session_id,
            "EvseID": "IT*EWI*E1",
            "ConsumedEnergyProgress": kwh,
            "Power": 48.0,
            "Time": "2026-11-26T10:30:00Z",
        }
    )


async def test_live_feed_opens_on_demand_and_keeps_progress():
    from leapconnect.infrastructure.evdc.live import EvdcLiveFeed

    _FakeLiveClient.instances = []
    feed = EvdcLiveFeed(lambda: object(), factory=_FakeLiveClient)
    await feed.want({"S9"})
    [live] = _FakeLiveClient.instances
    assert feed.running and live.connected
    live.on_progress(_progress())
    p = feed.progress("S9")
    assert (p.energy_kwh, p.power_kw) == (12.5, 48.0)
    assert p.updated_at == datetime(2026, 11, 26, 10, 30)
    # Asked again: same socket; an ended session's progress is forgotten
    await feed.want(set())
    assert len(_FakeLiveClient.instances) == 1 and feed.progress("S9") is None
    await feed.stop()
    assert not feed.running and not live.connected


async def test_live_feed_waits_after_a_failed_connection():
    from leapconnect.infrastructure.evdc.live import EvdcLiveFeed

    attempts = []

    def failing(client, on_progress):
        attempts.append(1)
        raise ValueError("Connection refused")

    feed = EvdcLiveFeed(lambda: object(), factory=failing)
    await feed.want({"S9"})
    await feed.want({"S9"})
    assert not feed.running and len(attempts) == 1  # no retry storm


async def test_estimate_uses_the_charger_reading():
    from leapconnect.application.charging_providers import OngoingItem
    from leapconnect.domain.charging.providers import ProviderLiveProgress

    row = ChargeSessionRow(start_ts=T0, end_ts=None, energy_kwh=10.0)
    car_only = OngoingItem(_ongoing(), row)
    assert car_only.estimated_cost == 5.9
    with_live = OngoingItem(_ongoing(live=ProviderLiveProgress(energy_kwh=12.0)), row)
    assert with_live.estimated_cost == 7.08


# -- wallets and payments ----------------------------------------------------------


def _wallet(balance, *, token=False, rate=None):
    from leapconnect.domain.charging.wallets import ProviderWallet

    return ProviderWallet(
        provider="evdc",
        currency="EVDC Token" if token else "EUR",
        balance=balance,
        is_token=token,
        token_rate=rate,
    )


def _payment(amount, session_id="S1", *, token=False, pid="P1"):
    from leapconnect.domain.charging.wallets import ProviderPayment

    return ProviderPayment(
        provider="evdc",
        payment_id=pid,
        amount=amount,
        is_token=token,
        category="charging",
        session_id=session_id,
        created_at=T0 + timedelta(hours=3),
    )


def test_spendable_balance_counts_tokens_at_their_rate():
    from leapconnect.domain.charging.wallets import is_low, spendable

    wallets = [_wallet(4.0), _wallet(516030, token=True, rate=51603.0)]
    assert spendable(wallets) == 14.0
    assert is_low(wallets, 15) and not is_low(wallets, 10) and not is_low(wallets, None)
    # Token worth unknown: only the money counts
    assert spendable([_wallet(4.0), _wallet(1000, token=True)]) == 4.0


def test_payments_are_checked_against_the_bill():
    from leapconnect.domain.charging.wallets import (
        PAID_ENERGY,
        PAID_OTHER,
        PAID_TOTAL,
        check_payments,
    )

    rate = 51603.0
    tokens = [_payment(-6.55 * rate, token=True), _payment(-1, "OTHER", pid="P2")]
    paid = check_payments(tokens, "S1", 6.55, 0.5, rate)
    assert (paid.paid, paid.matches, len(paid.payments)) == (6.55, PAID_TOTAL, 1)
    energy_only = check_payments([_payment(-6.05)], "S1", 6.55, 0.5)
    assert energy_only.matches == PAID_ENERGY
    refunded = check_payments([_payment(-10), _payment(3.45, pid="R")], "S1", 6.55)
    assert (refunded.paid, refunded.refunded, refunded.matches) == (
        6.55,
        3.45,
        PAID_TOTAL,
    )
    assert check_payments([_payment(-9)], "S1", 6.55).matches == PAID_OTHER
    assert check_payments([], "S1", 6.55).matches is None


def test_evdc_wallet_and_payment_mapping():
    from evdc_network_api import Wallet, WalletTransaction

    from leapconnect.infrastructure.evdc.service import to_payment, to_wallet

    w = to_wallet(
        Wallet.from_dict(
            {
                "_id": "w1",
                "balance": 516030,
                "currency": "EVDC Token",
                "isToken": True,
                "currencyDetails": {"name": "EVDC Token", "type": "TOKEN"},
            }
        ),
        token_rate=51603.0,
    )
    assert (w.is_token, w.money_value) == (True, 10.0)
    p = to_payment(
        WalletTransaction.from_dict(
            {
                "_id": "t1",
                "transactionAmount": -338000,
                "currency": "EVDC Token",
                "isToken": True,
                "category": "charging",
                "metaData": {"sessionId": "S1"},
                "createdAt": "2026-10-24T15:45:00Z",
            }
        )
    )
    assert (p.amount, p.session_id, p.created_at) == (
        -338000,
        "S1",
        datetime(2026, 10, 24, 15, 45),
    )


async def test_low_balance_alert_once_per_drop():
    from leapconnect.application.charging_providers import check_low_balance

    provider = FakeProvider([])
    provider.wallets = [_wallet(3.0)]
    assert (await check_low_balance(provider)).alert is False  # no threshold
    await provider.set_low_balance(5.0)
    assert (await check_low_balance(provider)).alert is True
    assert (await check_low_balance(provider)).alert is False  # once
    provider.wallets = [_wallet(20.0)]
    await check_low_balance(provider)
    assert provider.low_balance_alerted is False  # re-armed
    provider.wallets = [_wallet(2.0)]
    assert (await check_low_balance(provider)).alert is True


async def test_session_payments():
    from leapconnect.application.charging_providers import session_payments

    record = _record(external_source="evdc", external_id="S1", provider_account_id=7)
    billed = _ps(cost=6.55, fees=(ProviderFee("Parking fee", 0.5),))
    provider = FakeProvider([billed])
    provider.payments = [_payment(-6.55)]
    result = await session_payments(_Repo(costs=[record]), [provider], "V1", 1)
    assert (result.check.paid, result.check.matches) == (6.55, "total")
    assert (result.billed_total, result.billed_fees) == (6.55, 0.5)


def test_wallet_and_payment_endpoints(auth_client, provider):
    provider.wallets = [_wallet(3.0)]
    url = "/api/charging/providers/7"
    body = auth_client.put(url, json={"low_balance_threshold": 5}).json()
    assert body["low_balance_threshold"] == 5 and body["auto_sync"] is True
    wallets = auth_client.get(f"{url}/wallets").json()
    assert (wallets["spendable"], wallets["low"]) == (3.0, True)
    off = auth_client.put(url, json={"low_balance_threshold": None}).json()
    assert off["low_balance_threshold"] is None

    record = _create_record(auth_client)
    provider.sessions = [_ps()]
    auth_client.post(
        "/api/vehicles/V1/charging-costs/link",
        json={"account_id": 7, "external_id": "S1", "cost_id": record["id"]},
    )
    provider.payments = [_payment(-6.55)]
    paid = auth_client.get(f"{COSTS_URL}/{record['id']}/payments").json()
    assert (paid["paid"], paid["matches"]) == (6.55, "total")


async def test_account_low_balance_columns_are_added_to_an_older_table(tmp_path):
    import sqlite3

    from leapconnect.infrastructure.persistence.sqlite_adapter import (
        SqlAlchemyRepository,
    )

    db = tmp_path / "old.db"
    repo = SqlAlchemyRepository(f"sqlite+aiosqlite:///{db}")
    await repo.init_db()
    await repo.close()
    # The table as first released, without the low balance columns
    con = sqlite3.connect(db)
    con.execute("DROP TABLE charging_provider_accounts")
    con.execute(
        "CREATE TABLE charging_provider_accounts (id INTEGER PRIMARY KEY, "
        "provider VARCHAR(16) NOT NULL, username VARCHAR(256) NOT NULL, "
        "credentials TEXT NOT NULL, auto_sync BOOLEAN NOT NULL, "
        "last_sync VARCHAR(40), last_error TEXT, created_at DATETIME NOT NULL)"
    )
    con.commit()
    con.close()
    repo = SqlAlchemyRepository(f"sqlite+aiosqlite:///{db}")
    await repo.init_db()
    from leapconnect.domain.charging.models import ChargingProviderAccount

    saved = await repo.save_provider_account(
        ChargingProviderAccount(provider="evdc", username="a", low_balance_threshold=5)
    )
    [loaded] = await repo.get_provider_accounts()
    assert (loaded.id, loaded.low_balance_threshold) == (saved.id, 5)
    await repo.close()


async def test_scheduler_imports_and_alerts_once_a_day():
    from types import SimpleNamespace

    from leapconnect.application.scheduler import VehicleDataScheduler

    class _Dispatcher:
        def __init__(self):
            self.sent = []

        async def dispatch_system(self, event_type, sender, ctx):
            self.sent.append((event_type, sender, ctx))
            return 1

    record = _record(energy_kwh=12.16)
    repo = _Repo(costs=[record])
    provider = FakeProvider([_ps()])
    provider.wallets = [_wallet(3.0)]
    await provider.set_low_balance(5.0)
    dispatcher = _Dispatcher()
    sched = VehicleDataScheduler(repo=repo, notification_dispatcher=dispatcher)
    sched._vehicles = [SimpleNamespace(vin="V1", vehicle_nickname="Car", car_type=None)]
    sched.set_charging_providers(lambda: [provider])

    now = END + timedelta(days=1)
    await sched._maybe_sync_charging_provider(now=now)
    assert record.external_id == "S1"
    [(event, sender, ctx)] = dispatcher.sent
    assert (event, sender, ctx["balance"], ctx["threshold"]) == (
        "charging_provider_low_balance",
        "EVDC",
        "3.00",
        "5.00",
    )
    # Not due again within the day
    await sched._maybe_sync_charging_provider(now=now + timedelta(hours=1))
    assert len(dispatcher.sent) == 1
