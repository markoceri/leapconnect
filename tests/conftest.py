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
        patch.dict(os.environ, {"HISTORY_DB_PATH": db_file}),
        patch("main._auto_connect", new_callable=AsyncMock),
    ):
        from main import app

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
