"""Charging provider port: an e-mobility app that bills public charges."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from leapconnect.domain.charging.providers import ProviderSession


class ChargingProvider(ABC):
    """Read-only access to the charging sessions a provider billed."""

    #: Short id stored on the imported records (e.g. ``"evdc"``)
    name: str = ""
    #: Shown in the UI (e.g. ``"EVDC"``)
    label: str = ""
    #: Import the recent sessions automatically (scheduler)
    auto_sync: bool = False

    @property
    @abstractmethod
    def connected(self) -> bool:
        """Whether an account is connected and sessions can be fetched."""

    @abstractmethod
    async def fetch_sessions(self, since: datetime) -> list[ProviderSession]:
        """Billed sessions started since ``since`` (naive UTC), oldest first."""
