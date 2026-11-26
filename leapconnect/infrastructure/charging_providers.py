"""The connected charging provider accounts, of every supported type.

Each account is served by its type's adapter (EVDC only, for now). A new
account is connected in two steps when the provider asks for a two-factor
code: the login waits, under a pending id, for the code.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from leapconnect.application.ports.charging_provider import (
    ChargingProvider,
    ChargingProviderError,
)
from leapconnect.domain.charging.models import ChargingProviderAccount
from leapconnect.infrastructure.evdc.service import EvdcService

if TYPE_CHECKING:
    from leapconnect.application.ports.repositories import AppRepository

# A login waiting for its two-factor code is dropped after this long
PENDING_TTL = 600.0  # seconds

# The single EVDC account of the first version, kept in the settings
_LEGACY_EVDC_KEYS = {
    "username": "evdc_email",
    "user_id": "evdc_user_id",
    "device_id": "evdc_device_id",
    "device_key": "evdc_device_key",
    "access_token": "evdc_access_token",
    "refresh_token": "evdc_refresh_token",
    "auto_sync": "evdc_auto_sync",
    "last_sync": "evdc_last_sync",
}


@dataclass(frozen=True)
class ProviderType:
    """A supported charging provider."""

    id: str
    label: str
    url: str
    username_label: str = "E-mail"
    note: str | None = None  # shown on the connect form
    has_stations: bool = False  # can search its charging points


PROVIDER_TYPES: dict[str, ProviderType] = {
    "evdc": ProviderType(
        id="evdc",
        label="EVDC",
        url="https://evdc.network",
        note=(
            "Accounts created with Google or Apple sign-in have no EVDC password"
            " and can't be connected."
        ),
        has_stations=True,
    ),
}

_FACTORIES = {"evdc": EvdcService}


@dataclass
class PendingLogin:
    service: EvdcService
    method: str  # "email" | "totp"
    created: float


class ChargingProviderRegistry:
    """The connected accounts and the logins waiting for a code."""

    def __init__(self, repo: AppRepository) -> None:
        self._repo = repo
        self._services: dict[int, ChargingProvider] = {}
        self._pending: dict[str, PendingLogin] = {}

    async def load(self) -> None:
        await self._move_legacy_evdc_account()
        self._services = {}
        for account in await self._repo.get_provider_accounts():
            factory = _FACTORIES.get(account.provider)
            if factory is not None and account.id is not None:
                self._services[account.id] = factory(self._repo, account)

    async def _move_legacy_evdc_account(self) -> None:
        """Move the EVDC account the first version kept in the settings to
        the accounts table (once: the settings are then cleared)."""
        legacy = {
            k: await self._repo.get_setting(key) or ""
            for k, key in _LEGACY_EVDC_KEYS.items()
        }
        if not (legacy["username"] and legacy["device_key"] and legacy["user_id"]):
            return
        if not any(
            a.provider == "evdc" and a.username.lower() == legacy["username"].lower()
            for a in await self._repo.get_provider_accounts()
        ):
            await self._repo.save_provider_account(
                ChargingProviderAccount(
                    provider="evdc",
                    username=legacy["username"],
                    credentials={
                        k: legacy[k]
                        for k in (
                            "user_id",
                            "device_id",
                            "device_key",
                            "access_token",
                            "refresh_token",
                        )
                    },
                    auto_sync=legacy["auto_sync"] != "false",
                    last_sync=legacy["last_sync"] or None,
                )
            )
        for key in (*_LEGACY_EVDC_KEYS.values(), "evdc_last_error"):
            await self._repo.save_setting(key, "")

    # -- read -------------------------------------------------------------------

    def all(self) -> list[ChargingProvider]:
        """Every account, oldest first."""
        return [self._services[k] for k in sorted(self._services)]

    def connected(self) -> list[ChargingProvider]:
        return [p for p in self.all() if p.connected]

    def get(self, account_id: int) -> ChargingProvider | None:
        return self._services.get(account_id)

    def account(self, account_id: int) -> ChargingProviderAccount | None:
        service = self._services.get(account_id)
        return getattr(service, "account", None)

    # -- connect / disconnect ---------------------------------------------------

    def _check_new(self, provider: str, username: str) -> None:
        if any(
            p.provider == provider and (p.username or "").lower() == username.lower()
            for p in self.all()
        ):
            raise ChargingProviderError(
                f"{PROVIDER_TYPES[provider].label} account {username} is already"
                " connected"
            )

    async def login(
        self, provider: str, username: str, password: str
    ) -> tuple[ChargingProvider | None, str | None, str | None]:
        """Connect an account: ``(account, None, None)``, or ``(None, pending
        id, two-factor method)`` when a code is needed (then :meth:`verify`)."""
        factory = _FACTORIES.get(provider)
        if factory is None:
            raise ChargingProviderError(f"Unknown charging provider: {provider}")
        self._check_new(provider, username.strip())
        self._drop_expired()
        service = factory(self._repo)
        method = await service.login(username.strip(), password)
        if method is not None:
            pending_id = secrets.token_urlsafe(16)
            self._pending[pending_id] = PendingLogin(service, method, time.monotonic())
            return None, pending_id, method
        return self._add(service), None, None

    async def verify(self, pending_id: str, code: str) -> ChargingProvider:
        self._drop_expired()
        pending = self._pending.get(pending_id)
        if pending is None:
            raise ChargingProviderError(
                "The login expired: connect the account again", auth=True
            )
        await pending.service.verify(code)
        del self._pending[pending_id]
        return self._add(pending.service)

    def _add(self, service: EvdcService) -> ChargingProvider:
        assert service.account_id is not None  # saved by the login
        self._services[service.account_id] = service
        return service

    def _drop_expired(self) -> None:
        now = time.monotonic()
        for pid in [
            k for k, p in self._pending.items() if now - p.created > PENDING_TTL
        ]:
            del self._pending[pid]

    async def close(self) -> None:
        """Close what the accounts keep open (the live sockets)."""
        for service in self._services.values():
            live = getattr(service, "live", None)
            if live is not None:
                await live.stop()

    async def remove(self, account_id: int) -> bool:
        """Disconnect an account (its device key and session are revoked) and
        forget it; the sessions imported with it keep their values."""
        service = self._services.pop(account_id, None)
        if service is None:
            return False
        await service.disconnect()
        await self._repo.delete_provider_account(account_id)
        return True
