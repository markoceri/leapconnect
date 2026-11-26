"""Charging provider port: an account of an e-mobility service provider (eMSP,
"charging provider" in the UI) such as EVDC, which bills public charges."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from leapconnect.domain.charging.providers import ProviderSession
    from leapconnect.domain.charging.stations import ChargingStation


class ChargingProviderError(Exception):
    """The provider refused or failed a request. ``auth``: the account's
    credentials were refused (reconnect it)."""

    def __init__(self, message: str, *, auth: bool = False) -> None:
        super().__init__(message)
        self.auth = auth


class ChargingProvider(ABC):
    """Read-only access to one connected account of a charging provider."""

    #: Provider type, stored on the imported records (e.g. ``"evdc"``)
    provider: str = ""
    #: Provider type shown in the UI (e.g. ``"EVDC"``)
    label: str = ""

    @property
    @abstractmethod
    def account_id(self) -> int | None:
        """The stored account (``None`` while it is being connected)."""

    @property
    @abstractmethod
    def username(self) -> str | None:
        """The account it logs in as (shown in the UI)."""

    @property
    @abstractmethod
    def connected(self) -> bool:
        """Whether sessions can be fetched."""

    @property
    @abstractmethod
    def auto_sync(self) -> bool:
        """Import the recent sessions automatically (scheduler)."""

    @abstractmethod
    async def set_auto_sync(self, enabled: bool) -> None:
        """Turn the automatic import on or off (saved)."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Revoke this client's access to the account."""

    @abstractmethod
    async def fetch_sessions(self, since: datetime) -> list[ProviderSession]:
        """Billed sessions started since ``since`` (naive UTC), oldest first."""

    @abstractmethod
    async def get_receipt(self, external_id: str) -> tuple[str | None, bytes]:
        """The PDF receipt of a billed session: ``(filename, content)``."""

    @abstractmethod
    async def get_station(self, evse_id: str) -> ChargingStation | None:
        """A charging point with its live status and price."""

    @abstractmethod
    async def find_stations(
        self, latitude: float, longitude: float, radius_m: float
    ) -> list[ChargingStation]:
        """The network's charging points within ``radius_m`` of a point,
        nearest first, with their live status and price."""
