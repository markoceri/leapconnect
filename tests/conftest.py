"""Test configuration and shared fixtures."""

import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    """Create a test client with auto-connect disabled and temp DB."""
    db_file = str(tmp_path / "test.db")
    with (
        patch.dict(os.environ, {"DB_PATH": db_file}),
        patch(
            "leapconnect.container.AppContainer.auto_connect",
            new_callable=AsyncMock,
        ),
    ):
        from leapconnect.api.app import app
        from leapconnect.container import container
        from leapconnect.domain.identity.throttle import LoginThrottle

        # The container is a process-wide singleton: reset cross-test state.
        container.login_throttle = LoginThrottle()

        with TestClient(app) as c:
            yield c


@pytest.fixture
def auth_client(client):
    """Create a test client with an authenticated session."""
    resp = client.post(
        "/api/setup/user",
        json={"display_name": "Test User", "password": "testpass"},
    )
    assert resp.status_code == 200
    return client
