"""Shared API helpers: dependency providers, auth/session, request parsing.

Routers receive their collaborators via FastAPI ``Depends`` (the aliases
below) instead of importing the ``container`` singleton, so tests can swap
them with ``app.dependency_overrides[get_container]``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException
from leapmotor_api.async_client import AsyncLeapmotorApiClient
from leapmotor_api.models import Vehicle

from leapconnect.application.ports.repositories import AppRepository
from leapconnect.container import AppContainer, container

SESSION_COOKIE_NAME = "leapconnect_session"

# Endpoints that do NOT require a session
PUBLIC_PATHS: set[str] = {
    "/api/setup/status",
    "/api/setup/user",
    "/api/auth/session",
}


def get_container() -> AppContainer:
    """Root dependency: the composition root (overridable in tests)."""
    return container


ContainerDep = Annotated[AppContainer, Depends(get_container)]


def get_repo(c: ContainerDep) -> AppRepository:
    """The persistence repository, or 503 if the DB is not initialised."""
    if not c.repo:
        raise HTTPException(status_code=503, detail="DB not ready")
    return c.repo


def repo_required(detail: str):
    """Dependency factory: like ``get_repo`` but with a specific 503 message."""

    def _dep(c: ContainerDep) -> AppRepository:
        if not c.repo:
            raise HTTPException(status_code=503, detail=detail)
        return c.repo

    return Depends(_dep)


def get_client(c: ContainerDep) -> AsyncLeapmotorApiClient:
    """The connected Leapmotor cloud client, or 400 if not logged in."""
    return c.get_client()


def get_vehicle(vin: str, c: ContainerDep) -> Vehicle:
    """The connected vehicle matching the ``vin`` path param, or 404."""
    return c.find_vehicle(vin)


RepoDep = Annotated[AppRepository, Depends(get_repo)]
ClientDep = Annotated[AsyncLeapmotorApiClient, Depends(get_client)]
VehicleDep = Annotated[Vehicle, Depends(get_vehicle)]


def parse_range_date(value: str | None) -> str | None:
    """Normalize supported date inputs to YYYY-MM-DD.

    Accepted formats:
    - YYYY-MM-DD
    - ISO datetime
    - Unix timestamp seconds or milliseconds (string)
    """
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None

    if raw.isdigit():
        ts = int(raw)
        if ts > 10_000_000_000:
            ts = ts / 1000
        return datetime.fromtimestamp(ts, tz=UTC).date().isoformat()

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        # Last fallback for strings like "YYYY-MM-DD HH:MM:SS"
        try:
            return datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S").date().isoformat()
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid date format: {value}",
            ) from exc
