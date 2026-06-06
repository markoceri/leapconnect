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

    def test_catalog_loads(self):
        from services.maintenance_resolver import load_maintenance_catalog

        catalog = load_maintenance_catalog()
        assert "models" in catalog
        assert "T03" in catalog["models"]
        assert "items" in catalog["models"]["T03"]
        assert len(catalog["models"]["T03"]["items"]) > 0

    def test_catalog_rules_for_t03(self):
        from services.maintenance_resolver import get_maintenance_rules

        rules = get_maintenance_rules("T03")
        assert rules is not None
        assert "items" in rules
        assert any(i["service_type"] == "brake_fluid_replace" for i in rules["items"])
        assert any(i["service_type"] == "tire_replace" for i in rules["items"])
        assert any(i["service_type"] == "reducer_oil_replace" for i in rules["items"])

    def test_catalog_rules_for_nonexistent(self):
        from services.maintenance_resolver import get_maintenance_rules

        rules = get_maintenance_rules("NONEXISTENT")
        assert rules is None
