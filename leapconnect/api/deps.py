"""Shared API helpers: container access, auth/session, request parsing."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException

from leapconnect.application.ports.repositories import AppRepository
from leapconnect.container import container

SESSION_COOKIE_NAME = "leapconnect_session"

# Endpoints that do NOT require a session
PUBLIC_PATHS: set[str] = {
    "/api/setup/status",
    "/api/setup/user",
    "/api/auth/login",
}


def get_repo() -> AppRepository:
    """Return the history repository or fail with 503 if not initialised."""
    if not container.repo:
        raise HTTPException(status_code=503, detail="DB not ready")
    return container.repo


def get_repo_or_503(detail: str) -> AppRepository:
    """Like get_repo() but with an endpoint-specific 503 message."""
    if not container.repo:
        raise HTTPException(status_code=503, detail=detail)
    return container.repo


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
        return datetime.utcfromtimestamp(ts).date().isoformat()

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
