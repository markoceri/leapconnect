"""Test configuration and shared fixtures."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from main import app

    with TestClient(app) as c:
        yield c
