"""Failed-login throttling policy (pure, in-memory).

After ``max_attempts`` consecutive failures for a key (e.g. the client IP),
further attempts are blocked for ``base_lockout_seconds``, doubling with each
additional failure up to ``max_lockout_seconds``. A successful login clears
the key.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class _Entry:
    failures: int = 0
    blocked_until: float = 0.0


@dataclass
class LoginThrottle:
    """Tracks failed login attempts per key and enforces a lockout."""

    max_attempts: int = 5
    base_lockout_seconds: float = 30.0
    max_lockout_seconds: float = 900.0
    clock: Callable[[], float] = time.monotonic
    _entries: dict[str, _Entry] = field(default_factory=dict)

    def retry_after(self, key: str) -> float | None:
        """Seconds until the key may try again, or None if not blocked."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        remaining = entry.blocked_until - self.clock()
        return remaining if remaining > 0 else None

    def record_failure(self, key: str) -> None:
        """Register a failed attempt; starts/extends the lockout when over limit."""
        entry = self._entries.setdefault(key, _Entry())
        entry.failures += 1
        over = entry.failures - self.max_attempts
        if over >= 0:
            lockout = min(
                self.base_lockout_seconds * (2**over), self.max_lockout_seconds
            )
            entry.blocked_until = self.clock() + lockout

    def record_success(self, key: str) -> None:
        """Clear the failure history for a key after a successful login."""
        self._entries.pop(key, None)
