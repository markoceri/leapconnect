"""Session policy — in-memory token store with expiry.

Sessions are deliberately ephemeral: a restart logs everyone out.
"""

from __future__ import annotations

import secrets
import time

SESSION_MAX_AGE = 7 * 24 * 3600  # 7 days


class SessionStore:
    """In-memory session token store with expiry."""

    def __init__(self, max_age_seconds: int = SESSION_MAX_AGE) -> None:
        self._max_age = max_age_seconds
        self._sessions: dict[str, float] = {}  # token -> expiry timestamp

    def create(self) -> str:
        """Create a new session token and store it."""
        token = secrets.token_urlsafe(32)
        self._sessions[token] = time.time() + self._max_age
        return token

    def validate(self, token: str | None) -> bool:
        """Check if a session token is valid and not expired."""
        if not token or token not in self._sessions:
            return False
        if time.time() > self._sessions[token]:
            self._sessions.pop(token, None)
            return False
        return True

    def invalidate(self, token: str | None) -> None:
        """Remove a session token."""
        if token:
            self._sessions.pop(token, None)
