"""Tests for the API endpoints."""


def test_status_requires_session(client):
    """Accessing /api/status without a session returns 401."""
    response = client.get("/api/status")
    assert response.status_code == 401


def test_status_not_connected(auth_client):
    """When authenticated but not connected, /api/status returns connected=False."""
    response = auth_client.get("/api/status")
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
    response = auth_client.post("/api/auth/login", json={"password": "wrongpass"})
    assert response.status_code == 401
