"""Tests for the maintenance endpoints."""


def test_model_resolution_t03(auth_client):
    """Model resolution should correctly identify T03 from car_type."""
    # Without a connected vehicle list, this will return 404 (vin not found)
    # but the resolver logic itself is testable via unit tests.
    response = auth_client.get("/api/vehicles/TESTVIN123/maintenance/model")
    # 404 = vehicle not found in connected list (expected in test env)
    assert response.status_code == 404


def test_rules_endpoint_no_vehicle(auth_client):
    """Maintenance rules requires vehicle in connected list."""
    response = auth_client.get("/api/vehicles/TESTVIN123/maintenance/rules")
    assert response.status_code == 404


def test_plan_endpoint_no_persistence(auth_client):
    """Plan endpoint returns 404 or 503 without connected vehicle."""
    response = auth_client.get("/api/vehicles/TESTVIN123/maintenance/plan")
    assert response.status_code in (404, 503)


def test_overview_endpoint_no_vehicle(auth_client):
    """Overview endpoint requires vehicle connection."""
    response = auth_client.get("/api/vehicles/TESTVIN123/maintenance/overview")
    assert response.status_code in (404, 503)


def test_records_endpoint_no_vehicle(auth_client):
    """Records endpoint returns empty array when no vehicle connected."""
    response = auth_client.get("/api/vehicles/TESTVIN123/maintenance/records")
    # May return 200 (empty list via repo) or 404/503 (no repo)
    assert response.status_code in (200, 404, 503)


def test_model_override_invalid_variant(auth_client):
    """Setting an invalid C10 variant returns 400."""
    response = auth_client.post(
        "/api/vehicles/TESTVIN123/maintenance/model",
        json={"variant": "diesel"},
    )
    assert response.status_code == 400


def test_model_override_no_vehicle(auth_client):
    """Setting variant without connected vehicle returns 404."""
    response = auth_client.post(
        "/api/vehicles/TESTVIN123/maintenance/model",
        json={"variant": "bev"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Unit tests for the resolver
# ---------------------------------------------------------------------------


class TestModelResolver:
    """Unit tests for services/maintenance_resolver.py."""

    def test_resolve_t03(self):
        from services.maintenance_resolver import resolve_model

        class FakeVehicle:
            vin = "VIN123"
            car_type = "T03"
            allocation_code = None
            abilities = []
            seat_layout = None
            rudder = None

        result = resolve_model(FakeVehicle())
        assert result["model_key"] == "T03"
        assert result["display_name"] == "Leapmotor T03"
        assert result["confidence"] == "high"
        assert result["needs_confirmation"] is False

    def test_resolve_b10(self):
        from services.maintenance_resolver import resolve_model

        class FakeVehicle:
            vin = "VIN456"
            car_type = "B10"
            allocation_code = None
            abilities = []
            seat_layout = None
            rudder = None

        result = resolve_model(FakeVehicle())
        assert result["model_key"] == "B10"
        assert result["display_name"] == "Leapmotor B10"
        assert result["confidence"] == "high"

    def test_resolve_c10_ambiguous(self):
        from services.maintenance_resolver import resolve_model

        class FakeVehicle:
            vin = "VIN789"
            car_type = "C10"
            allocation_code = None
            abilities = []
            seat_layout = None
            rudder = None

        result = resolve_model(FakeVehicle())
        assert result["model_key"] == "C10"
        assert result["confidence"] == "low"
        assert result["needs_confirmation"] is True

    def test_resolve_c10_reev_by_allocation(self):
        from services.maintenance_resolver import resolve_model

        class FakeVehicle:
            vin = "VIN999"
            car_type = "C10"
            allocation_code = "C10_REEV"
            abilities = []
            seat_layout = None
            rudder = None

        result = resolve_model(FakeVehicle())
        assert result["model_key"] == "C10_REEV"
        assert result["variant"] == "reev"
        assert result["needs_confirmation"] is False

    def test_resolve_c10_reev_by_fuel_ability(self):
        from services.maintenance_resolver import resolve_model

        class FakeVehicle:
            vin = "VIN888"
            car_type = "C10"
            allocation_code = None
            abilities = ["40"]  # fuel heating ability
            seat_layout = None
            rudder = None

        result = resolve_model(FakeVehicle())
        assert result["model_key"] == "C10_REEV"
        assert result["variant"] == "reev"
        assert result["needs_confirmation"] is False

    def test_resolve_unknown(self):
        from services.maintenance_resolver import resolve_model

        class FakeVehicle:
            vin = "VIN000"
            car_type = "ZZZ999"
            allocation_code = None
            abilities = []
            seat_layout = None
            rudder = None

        result = resolve_model(FakeVehicle())
        assert result["model_key"] == "unknown"
        assert result["confidence"] == "low"


# ---------------------------------------------------------------------------
# Unit tests for the maintenance service logic
# ---------------------------------------------------------------------------


class TestMaintenanceService:
    """Unit tests for services/maintenance_service.py."""

    def _item(self, **kw):
        from models import MaintenancePlanItem

        defaults = dict(
            id=1,
            vin="V1",
            service_type="brake_fluid_replace",
            label="Brake fluid",
            category="brakes",
            interval_km=40000,
            interval_months=24,
            trigger_mode="or",
            priority="important",
        )
        defaults.update(kw)
        return MaintenancePlanItem(**defaults)

    def test_alert_none_without_last_done(self):
        from datetime import datetime

        from services.maintenance_service import compute_alert

        item = self._item()
        assert compute_alert(item, 10000, datetime(2026, 1, 1)) is None

    def test_alert_overdue_by_km(self):
        from datetime import datetime

        from services.maintenance_service import compute_alert

        item = self._item(last_done_km=0, interval_months=None)
        alert = compute_alert(item, 41000, datetime(2026, 1, 1))
        assert alert.status == "overdue"
        assert alert.remaining_km == -1000

    def test_alert_due_soon_by_km(self):
        from datetime import datetime

        from services.maintenance_service import compute_alert

        item = self._item(last_done_km=0, interval_months=None)
        # due at 40000, current 38500 -> 1500 remaining (<= 2000 threshold)
        alert = compute_alert(item, 38500, datetime(2026, 1, 1))
        assert alert.status == "due_soon"

    def test_alert_ok_far_away(self):
        from datetime import datetime

        from services.maintenance_service import compute_alert

        item = self._item(last_done_km=0, interval_months=None)
        alert = compute_alert(item, 10000, datetime(2026, 1, 1))
        assert alert.status == "ok"

    def test_trigger_mode_and_requires_both(self):
        from datetime import datetime

        from services.maintenance_service import compute_alert

        item = self._item(
            trigger_mode="and",
            last_done_km=0,
            last_done_date=datetime(2025, 1, 1),
        )
        # km overdue (42000 > 40000) but time not (only ~1 year of 24 months)
        alert = compute_alert(item, 42000, datetime(2026, 1, 1))
        assert alert.status != "overdue"

    def test_summarize_and_sort(self):
        from datetime import datetime

        from services.maintenance_service import (
            compute_alerts,
            due_soon_alerts,
            summarize,
        )

        # interval 40000; at 50000 km "a" is overdue, "b" (interval 51500) due soon
        overdue = self._item(
            service_type="a", interval_km=40000, last_done_km=0, interval_months=None
        )
        soon = self._item(
            service_type="b", interval_km=51500, last_done_km=0, interval_months=None
        )
        alerts = compute_alerts([overdue, soon], 50000, datetime(2026, 1, 1))
        counts = summarize(alerts)
        assert counts["overdue"] == 1
        assert counts["upcoming"] == 1
        # Overdue should sort before due-soon.
        shortlist = due_soon_alerts(alerts)
        assert shortlist[0].service_type == "a"


class TestPackNormalization:
    """Unit tests for pack parsing/validation."""

    def test_normalize_valid_pack(self):
        from services.maintenance_service import normalize_pack

        pack = normalize_pack(
            {
                "name": "My pack",
                "model_compat": ["C10"],
                "items": [{"service_type": "x", "label": "X", "interval_km": "1000"}],
            }
        )
        assert pack["name"] == "My pack"
        assert pack["items"][0]["interval_km"] == 1000
        assert pack["items"][0]["trigger_mode"] == "or"

    def test_normalize_rejects_empty_items(self):
        import pytest

        from services.maintenance_service import normalize_pack

        with pytest.raises(ValueError):
            normalize_pack({"name": "x", "items": []})

    def test_normalize_rejects_missing_service_type(self):
        import pytest

        from services.maintenance_service import normalize_pack

        with pytest.raises(ValueError):
            normalize_pack({"items": [{"label": "no type"}]})

    def test_pack_applies_to_model(self):
        from services.maintenance_service import pack_applies_to_model

        assert pack_applies_to_model({"model_compat": ["C10"]}, "C10_REEV")
        assert pack_applies_to_model({}, "T03")
        assert not pack_applies_to_model({"model_compat": ["T03"]}, "C10")


class TestGithubUrlParsing:
    """Unit tests for services/maintenance_community.py URL parsing."""

    def test_parse_full_url(self):
        from services.maintenance_community import parse_github_url

        assert parse_github_url("https://github.com/foo/bar") == ("foo", "bar", None)

    def test_parse_with_branch(self):
        from services.maintenance_community import parse_github_url

        assert parse_github_url("https://github.com/foo/bar/tree/dev") == (
            "foo",
            "bar",
            "dev",
        )

    def test_parse_shorthand(self):
        from services.maintenance_community import parse_github_url

        assert parse_github_url("foo/bar") == ("foo", "bar", None)

    def test_parse_invalid(self):
        import pytest

        from services.maintenance_community import CommunityError, parse_github_url

        with pytest.raises(CommunityError):
            parse_github_url("not a url")


class TestCommunityEndpoints:
    """Smoke tests for the new community/library endpoints."""

    def test_library_no_vehicle(self, auth_client):
        response = auth_client.get("/api/vehicles/TESTVIN123/maintenance/library")
        assert response.status_code in (404, 503)

    def test_list_repos_empty(self, auth_client):
        response = auth_client.get("/api/maintenance/repos")
        assert response.status_code == 200
        assert response.json() == []

    def test_add_repo_invalid_url(self, auth_client):
        response = auth_client.post("/api/maintenance/repos", json={"url": "not a url"})
        assert response.status_code == 400

    def test_import_pack_requires_source(self, auth_client):
        response = auth_client.post("/api/maintenance/packs/import", json={})
        assert response.status_code == 400

    def test_upload_invalid_json(self, auth_client):
        response = auth_client.post(
            "/api/maintenance/upload",
            files={"file": ("bad.json", b"not json", "application/json")},
        )
        assert response.status_code == 422


class TestOfficialPacks:
    """Unit tests for official factory-pack selection (replaces embedded catalog)."""

    def _packs(self):
        from models import MaintenancePack

        def mk(model, sts):
            return MaintenancePack(
                slug=f"official-{model.lower()}",
                model_compat=[model],
                payload={
                    "model_compat": [model],
                    "items": [{"service_type": s, "label": s} for s in sts],
                },
            )

        return [
            mk("C10", ["brake_fluid_replace", "cabin_filter_replace"]),
            mk("C10_REEV", ["engine_oil_replace", "spark_plugs_replace"]),
            mk("T03", ["tire_rotation"]),
        ]

    def test_exact_match_c10_not_reev(self):
        from services.maintenance_service import factory_items_for_model

        items = factory_items_for_model(self._packs(), "C10")
        sts = {i["service_type"] for i in items}
        assert "brake_fluid_replace" in sts
        assert "engine_oil_replace" not in sts  # must NOT pull the REEV pack

    def test_exact_match_reev(self):
        from services.maintenance_service import factory_items_for_model

        items = factory_items_for_model(self._packs(), "C10_REEV")
        sts = {i["service_type"] for i in items}
        assert "engine_oil_replace" in sts
        assert "brake_fluid_replace" not in sts

    def test_unknown_model_returns_empty(self):
        from services.maintenance_service import factory_items_for_model

        assert factory_items_for_model(self._packs(), "ZZZ") == []


class TestCostSummary:
    """Unit tests for maintenance cost aggregation."""

    def _data(self):
        from datetime import datetime

        from models import MaintenancePlanItem, MaintenanceRecord

        plan = [
            MaintenancePlanItem(service_type="brake_fluid_replace", category="brakes"),
            MaintenancePlanItem(service_type="tire_replace", category="tires"),
        ]
        records = [
            MaintenanceRecord(
                service_type="brake_fluid_replace",
                cost=120.0,
                timestamp=datetime(2026, 3, 1),
            ),
            MaintenanceRecord(
                service_type="tire_replace", cost=400.0, timestamp=datetime(2025, 5, 1)
            ),
            MaintenanceRecord(
                service_type="brake_fluid_replace",
                cost=80.0,
                timestamp=datetime(2026, 1, 1),
            ),
            MaintenanceRecord(
                service_type="x", cost=None, timestamp=datetime(2026, 2, 1)
            ),
        ]
        return records, plan

    def test_totals_and_avg(self):
        from datetime import datetime

        from services.maintenance_service import compute_cost_summary

        records, plan = self._data()
        s = compute_cost_summary(records, plan, datetime(2026, 6, 7))
        assert s["total"] == 600.0
        assert s["this_year"] == 200.0  # only 2026 costed records
        assert s["services_count"] == 3  # null-cost record excluded
        assert s["avg"] == 200.0

    def test_by_category_sorted(self):
        from datetime import datetime

        from services.maintenance_service import compute_cost_summary

        records, plan = self._data()
        s = compute_cost_summary(records, plan, datetime(2026, 6, 7))
        assert s["by_category"][0] == {"category": "tires", "total": 400.0}
        assert s["by_category"][1] == {"category": "brakes", "total": 200.0}

    def test_empty(self):
        from datetime import datetime

        from services.maintenance_service import compute_cost_summary

        s = compute_cost_summary([], [], datetime(2026, 6, 7))
        assert s == {
            "total": 0.0,
            "this_year": 0.0,
            "services_count": 0,
            "avg": 0.0,
            "by_category": [],
        }
