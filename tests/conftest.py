"""Test configuration and shared fixtures."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with auto-connect disabled."""
    with patch("main._auto_connect", new_callable=AsyncMock):
        from main import app

        with TestClient(app) as c:
            yield c
