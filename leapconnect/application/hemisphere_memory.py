"""Persist the GPS hemisphere memory across restarts.

The Leapmotor client keeps the last trusted coordinate sign per VIN in a
``HemisphereGuard`` (leapmotor-api #17), so West/South cars on signal-based
vehicles don't jump to the wrong hemisphere when the cloud drops the sign.
That memory is in-process: without it, the first polls after a restart can
place the car in the wrong hemisphere again. It is saved as JSON in the
settings table and handed back to the guard on the next connect.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from leapmotor_api.hemisphere import HemisphereGuard

if TYPE_CHECKING:
    from leapconnect.application.ports.repositories import AppRepository

_LOGGER = logging.getLogger(__name__)

SETTING_KEY = "hemisphere_guard_state"


class HemisphereMemory:
    """Loads and saves a ``HemisphereGuard`` state, writing only on change."""

    def __init__(self, repo: AppRepository) -> None:
        self._repo = repo
        self._saved: dict[str, Any] | None = None

    async def load_guard(self) -> HemisphereGuard:
        """Return a guard seeded with the saved state (empty if none or invalid)."""
        raw = await self._repo.get_setting(SETTING_KEY)
        state: dict[str, Any] = {}
        if raw:
            try:
                parsed = json.loads(raw)
            except ValueError:
                _LOGGER.warning("Ignoring unreadable hemisphere memory")
            else:
                if isinstance(parsed, dict):
                    state = parsed
        guard = HemisphereGuard(state)
        self._saved = guard.export_state()
        return guard

    async def save(self, guard: HemisphereGuard | None) -> None:
        """Persist the guard's state if it changed since the last load/save."""
        if guard is None:
            return
        state = guard.export_state()
        if state == self._saved:
            return
        await self._repo.save_setting(SETTING_KEY, json.dumps(state))
        self._saved = state
