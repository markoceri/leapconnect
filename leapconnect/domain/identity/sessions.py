"""Session policy — token store with expiry.

The store keeps only SHA-256 hashes of the tokens, so a snapshot (or the
database table it is persisted to) never contains usable session tokens.
Persistence is wired outside the domain: callers restore the store from the
repository at startup and write through on create/invalidate.
"""

from __future__ import annotations

import hashlib
import secrets
import time

SESSION_MAX_AGE = 7 * 24 * 3600  # 7 days


def hash_token(token: str) -> str:
    """Hash a session token for at-rest storage/lookup."""
    return hashlib.sha256(token.encode()).hexdigest()


class SessionStore:
    """Session token store with expiry, keyed by token hash."""

    def __init__(self, max_age_seconds: int = SESSION_MAX_AGE) -> None:
        self._max_age = max_age_seconds
        self._sessions: dict[str, float] = {}  # token hash -> expiry timestamp

    def create(self) -> str:
        """Create a new session token and store it."""
        token = secrets.token_urlsafe(32)
        self._sessions[hash_token(token)] = time.time() + self._max_age
        return token

    def validate(self, token: str | None) -> bool:
        """Check if a session token is valid and not expired."""
        if not token:
            return False
        key = hash_token(token)
        expiry = self._sessions.get(key)
        if expiry is None:
            return False
        if time.time() > expiry:
            self._sessions.pop(key, None)
            return False
        return True

    def invalidate(self, token: str | None) -> None:
        """Remove a session token."""
        if token:
            self._sessions.pop(hash_token(token), None)

    def expiry_of(self, token: str) -> float | None:
        """Expiry timestamp of a token, if known."""
        return self._sessions.get(hash_token(token))

    def restore(self, entries: dict[str, float]) -> None:
        """Load persisted sessions (token hash -> expiry), skipping expired."""
        now = time.time()
        self._sessions.update(
            {key: expiry for key, expiry in entries.items() if expiry > now}
        )
