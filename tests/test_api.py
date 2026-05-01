"""Tests for the API endpoints."""


def test_status_not_connected(client):
    """When not logged in, /api/status returns connected=False."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is False
    assert data["vehicles"] == []


def test_vehicles_requires_login(client):
    """Accessing vehicles without login returns 400."""
    response = client.get("/api/vehicles")
    assert response.status_code == 400


def test_vehicle_status_requires_login(client):
    """Accessing vehicle status without login returns 400."""
    response = client.get("/api/vehicles/TESTVIN123/status")
    assert response.status_code == 400


def test_setup_status(client):
    """Setup status endpoint is reachable."""
    response = client.get("/api/setup/status")
    # May be 200 or 503 depending on DB state, but should not crash
    assert response.status_code in (200, 503)
