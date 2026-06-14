"""Tests for the API endpoints."""


def test_status_requires_session(client):
    """Accessing /api/status without a session returns 401."""
    response = client.get("/api/cloud/status")
    assert response.status_code == 401


def test_status_not_connected(auth_client):
    """When authenticated but not connected, /api/status returns connected=False."""
    response = auth_client.get("/api/cloud/status")
    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is False
    assert data["vehicles"] == []


def test_vehicles_requires_session(client):
    """Accessing vehicles without session returns 401."""
    response = client.get("/api/vehicles")
    assert response.status_code == 401


def test_vehicles_requires_login(auth_client):
    """Accessing vehicles without Leapmotor connection returns 400."""
    response = auth_client.get("/api/vehicles")
    assert response.status_code == 400


def test_vehicle_status_requires_login(auth_client):
    """Accessing vehicle status without login returns 400."""
    response = auth_client.get("/api/vehicles/TESTVIN123/status")
    assert response.status_code == 400


def test_setup_status(client):
    """Setup status endpoint is reachable without session."""
    response = client.get("/api/setup/status")
    # May be 200 or 503 depending on DB state, but should not crash
    assert response.status_code in (200, 503)


def test_auth_login_wrong_password(auth_client):
    """Login with wrong password returns 401."""
    response = auth_client.post("/api/auth/session", json={"password": "wrongpass"})
    assert response.status_code == 401


def test_similar_trips_no_history(client):
    """Similar trips endpoint returns 401 without session."""
    response = client.get("/api/vehicles/TESTVIN123/trips/similar?gpskey=1_2")
    assert response.status_code == 401


def test_similar_trips_gpskey_not_found(auth_client):
    """Similar trips with unknown gpskey returns 404."""
    response = auth_client.get(
        "/api/vehicles/TESTVIN123/trips/similar?gpskey=9999999999_9999999999"
    )
    # 404 from _find_vehicle (vin not in vehicle list in test)
    assert response.status_code == 404


def test_scoring_haversine():
    """Haversine distance between same point is 0."""
    from leapconnect.domain.trips.analysis import haversine_km as _haversine_km

    d = _haversine_km(45.0, 9.0, 45.0, 9.0)
    assert d == 0.0


def test_scoring_haversine_known():
    """Haversine returns known approximate distance Milan-Rome."""
    from leapconnect.domain.trips.analysis import haversine_km as _haversine_km

    d = _haversine_km(45.464, 9.190, 41.903, 12.496)
    assert 470 < d < 490  # ~480 km


def test_zones_crud_round_trip(auth_client):
    """Zone CRUD over /api/zones, including charging_tier_id round-trip."""
    resp = auth_client.post(
        "/api/zones",
        json={
            "name": "Home",
            "shape_type": "circle",
            "latitude": 45.0,
            "longitude": 9.0,
            "radius_m": 150.0,
            "charging_tier_id": "home_solar",
        },
    )
    assert resp.status_code == 200
    created = resp.json()
    assert created["charging_tier_id"] == "home_solar"
    zone_id = created["id"]

    # List includes the new zone
    listing = auth_client.get("/api/zones").json()
    assert any(z["id"] == zone_id for z in listing)

    # Update the assigned tier
    resp = auth_client.put(
        f"/api/zones/{zone_id}", json={"charging_tier_id": "public_dc"}
    )
    assert resp.status_code == 200
    assert resp.json()["charging_tier_id"] == "public_dc"

    # Delete
    assert auth_client.delete(f"/api/zones/{zone_id}").status_code == 200
    listing = auth_client.get("/api/zones").json()
    assert not any(z["id"] == zone_id for z in listing)


def test_similarity_identical_trip():
    """Breakdown for identical trips scores 1.0."""
    from leapconnect.domain.trips.analysis import (
        trip_similarity_breakdown as _trip_similarity_breakdown,
    )

    trip = {
        "beginTime": "2026-06-01 08:30:00",
        "endTime": "2026-06-01 09:15:00",
        "travelMile": 15000,
        "energyConsumed": 2500,
        "energyRecovered": 300,
        "maxSpeed": 95,
        "startSoc": 75,
        "endSoc": 68,
        "outdoorTemp": 18,
        "startLat": 45.0,
        "startLng": 9.0,
        "endLat": 45.1,
        "endLng": 9.1,
        "gpskey": "1_2",
    }
    result = _trip_similarity_breakdown(trip, trip)
    assert result["score"] == 1.0
    assert result["breakdown"]["route"] == 1.0
    assert result["breakdown"]["time"] == 1.0
    assert result["breakdown"]["distance"] == 1.0


def test_similarity_different_trips():
    """Breakdown for very different trips returns low score."""
    from leapconnect.domain.trips.analysis import (
        trip_similarity_breakdown as _trip_similarity_breakdown,
    )

    ref = {
        "beginTime": "2026-06-01 08:30:00",
        "endTime": "2026-06-01 09:15:00",
        "travelMile": 15000,
        "energyConsumed": 2500,
        "energyRecovered": 300,
        "maxSpeed": 95,
        "startSoc": 75,
        "endSoc": 68,
        "outdoorTemp": 18,
        "startLat": 45.0,
        "startLng": 9.0,
        "endLat": 45.1,
        "endLng": 9.1,
        "gpskey": "1_2",
    }
    cand = {
        "beginTime": "2026-06-01 20:00:00",
        "endTime": "2026-06-01 20:10:00",
        "travelMile": 3000,
        "energyConsumed": 600,
        "energyRecovered": 0,
        "maxSpeed": 50,
        "startSoc": 80,
        "endSoc": 78,
        "outdoorTemp": 10,
        "startLat": 46.0,
        "startLng": 10.0,
        "endLat": 46.0,
        "endLng": 10.0,
        "gpskey": "3_4",
    }
    result = _trip_similarity_breakdown(ref, cand)
    assert 0.0 <= result["score"] <= 1.0
    # Time should be very low (08:30 vs 20:00)
    assert result["breakdown"]["time"] <= 0.2
    # Route should be low (different start/end)
    assert result["breakdown"]["route"] <= 0.5


def test_compare_metrics_structure():
    """Compare metrics returns expected keys."""
    from leapconnect.domain.trips.analysis import (
        trip_compare_metrics as _trip_compare_metrics,
    )

    ref = {
        "beginTime": "2026-06-01 08:30:00",
        "endTime": "2026-06-01 09:15:00",
        "travelMile": 15000,
        "energyConsumed": 2500,
        "energyRecovered": 300,
        "maxSpeed": 95,
        "avgSpeed": 33.3,
        "startSoc": 75,
        "endSoc": 68,
        "outdoorTemp": 18,
        "gpskey": "1_2",
    }
    cand = dict(ref, gpskey="3_4")
    metrics = _trip_compare_metrics(ref, cand)
    assert "efficiency" in metrics
    assert "performance" in metrics
    assert "conditions" in metrics
    assert metrics["efficiency"]["consumption_kwh_100km"]["delta"] == 0.0


def test_vehicle_pin_is_write_only(auth_client):
    """The vehicle PIN is never echoed back by the API, only has_pin."""
    resp = auth_client.put("/api/cloud/pin", json={"pin": "1234"})
    assert resp.status_code == 200
    assert resp.json() == {"has_pin": True}

    resp = auth_client.get("/api/cloud/pin")
    assert resp.status_code == 200
    assert resp.json() == {"has_pin": True}

    # Clearing the PIN reports has_pin=False
    resp = auth_client.put("/api/cloud/pin", json={"pin": ""})
    assert resp.status_code == 200
    assert resp.json() == {"has_pin": False}


def test_container_dependency_is_overridable(client):
    """Routers resolve the container via Depends, so tests can swap it."""
    from leapconnect.api import deps

    class StubContainer:
        repo = None  # simulates "DB not ready"

    client.app.dependency_overrides[deps.get_container] = StubContainer
    try:
        resp = client.get("/api/setup/status")
        assert resp.status_code == 503
        assert resp.json()["detail"] == "DB not ready"
    finally:
        client.app.dependency_overrides.clear()


def test_local_session_delete_logs_out(auth_client):
    """DELETE /api/auth/session invalidates the session cookie."""
    resp = auth_client.delete("/api/auth/session")
    assert resp.status_code == 200

    resp = auth_client.get("/api/cloud/status")
    assert resp.status_code == 401
