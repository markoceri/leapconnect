"""EVDC charging provider: the account's billed sessions via ``evdc-network-api``.

Read-only: the client only logs in and reads the charging history and the
receipts. The account is connected once with e-mail and password (plus a
two-factor code when enabled); a device key is then enrolled so later logins
need neither the password, which is never stored, nor a new code. Disconnecting
revokes the device key and this client's session.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from evdc_network_api import (
    AsyncEvdcApiClient,
    EvdcApiClient,
    EvdcApiError,
    EvdcAuthError,
    EvdcTwoFactorRequiredError,
)

from leapconnect.application.ports.charging_provider import ChargingProvider
from leapconnect.domain.charging.providers import ProviderFee, ProviderSession

if TYPE_CHECKING:
    from evdc_network_api import ChargingSession

    from leapconnect.application.ports.repositories import AppRepository

_LOGGER = logging.getLogger(__name__)

PROVIDER = "evdc"
DEVICE_MODEL = "LeapConnect"
HISTORY_PAGE_SIZE = 20

# Settings keys (the secret ones are encrypted at rest, see
# persistence.settings.SECRET_SETTING_KEYS)
KEY_EMAIL = "evdc_email"
KEY_USER_ID = "evdc_user_id"
KEY_DEVICE_ID = "evdc_device_id"
KEY_DEVICE_KEY = "evdc_device_key"
KEY_ACCESS_TOKEN = "evdc_access_token"
KEY_REFRESH_TOKEN = "evdc_refresh_token"
KEY_AUTO_SYNC = "evdc_auto_sync"
KEY_LAST_SYNC = "evdc_last_sync"
KEY_LAST_ERROR = "evdc_last_error"
SECRET_KEYS = (KEY_DEVICE_KEY, KEY_ACCESS_TOKEN, KEY_REFRESH_TOKEN)

_FEES = (
    ("time_fee", "Time fee"),
    ("parking_fee", "Parking fee"),
    ("time_surcharge_fee", "Time surcharge"),
)


def _naive_utc(ts: datetime | None) -> datetime | None:
    if ts is None or ts.tzinfo is None:
        return ts
    return ts.astimezone(UTC).replace(tzinfo=None)


def to_provider_session(s: ChargingSession) -> ProviderSession | None:
    """A billed EVDC session; ``None`` for failed, test or unbilled ones."""
    external_id = s.session_id or s.id
    if not external_id or s.is_failed or s.is_test_session or s.cost is None:
        return None
    fees = tuple(
        ProviderFee(label, amount)
        for attr, label in _FEES
        if (amount := getattr(s, attr)) not in (None, 0)
    )
    location = None
    if s.address is not None:
        location = ", ".join(p for p in (s.address.street, s.address.city) if p) or None
    price = (
        s.pricing.price
        if s.pricing and (s.pricing.unit or "").lower() == "kwh"
        else None
    )
    # One EVSE is one connector: DC, or AC (1 or 3 phases)
    power_types = {
        f.power_type
        for f in (s.station.facilities if s.station else [])
        if f.power_type
    }
    is_dc = ("DC" in power_types) if power_types else None
    return ProviderSession(
        provider=PROVIDER,
        external_id=external_id,
        started_at=_naive_utc(s.started_at or s.created_at),
        ended_at=_naive_utc(s.ended_at),
        energy_kwh=s.energy_kwh,
        cost=s.cost,  # real money, also for a session paid with EVDC tokens
        currency=s.cost_currency,
        price_kwh=price,
        fees=fees,
        evse_id=s.evse_id,
        operator=s.operator,
        location=location,
        is_dc=is_dc,
        latitude=s.station.latitude if s.station else None,
        longitude=s.station.longitude if s.station else None,
    )


@dataclass
class _Credentials:
    email: str = ""
    user_id: str = ""
    device_id: str = ""
    device_key: str = ""
    access_token: str = ""
    refresh_token: str = ""


class EvdcService(ChargingProvider):
    """The connected EVDC account (one per installation)."""

    name = PROVIDER
    label = "EVDC"

    def __init__(self, repo: AppRepository) -> None:
        self._repo = repo
        self._creds = _Credentials()
        self._client: AsyncEvdcApiClient | None = None
        self._pending: AsyncEvdcApiClient | None = None  # waiting for a 2FA code
        self._lock = asyncio.Lock()
        self.auto_sync = True
        self.last_sync: str | None = None
        self.last_error: str | None = None

    # -- state ---------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._client is not None

    @property
    def email(self) -> str | None:
        return self._creds.email or None

    @property
    def two_factor_pending(self) -> str | None:
        return self._pending.two_factor_pending if self._pending else None

    def status_dict(self) -> dict:
        return {
            "connected": self.connected,
            "email": self.email,
            "two_factor_pending": self.two_factor_pending,
            "auto_sync": self.auto_sync,
            "last_sync": self.last_sync,
            "last_error": self.last_error,
        }

    async def load(self) -> None:
        """Restore the connected account from the settings."""
        get = self._repo.get_setting
        self._creds = _Credentials(
            email=await get(KEY_EMAIL) or "",
            user_id=await get(KEY_USER_ID) or "",
            device_id=await get(KEY_DEVICE_ID) or "",
            device_key=await get(KEY_DEVICE_KEY) or "",
            access_token=await get(KEY_ACCESS_TOKEN) or "",
            refresh_token=await get(KEY_REFRESH_TOKEN) or "",
        )
        self.auto_sync = (await get(KEY_AUTO_SYNC) or "true") == "true"
        self.last_sync = await get(KEY_LAST_SYNC) or None
        self.last_error = await get(KEY_LAST_ERROR) or None
        c = self._creds
        if c.email and c.device_key and c.user_id:
            self._client = AsyncEvdcApiClient(
                EvdcApiClient(
                    email=c.email,
                    access_token=c.access_token or None,
                    refresh_token=c.refresh_token or None,
                    device_key=c.device_key,
                    user_id=c.user_id,
                    device_id=c.device_id or None,
                    device_model=DEVICE_MODEL,
                )
            )

    async def set_auto_sync(self, enabled: bool) -> None:
        self.auto_sync = enabled
        await self._repo.save_setting(KEY_AUTO_SYNC, "true" if enabled else "false")

    # -- connect / disconnect ------------------------------------------------

    async def login(self, email: str, password: str) -> dict:
        """Log in; ``status_dict()["two_factor_pending"]`` tells when a code
        is needed (then call :meth:`verify`)."""
        async with self._lock:
            device_id = self._creds.device_id or secrets.token_hex(32)
            client = AsyncEvdcApiClient(
                EvdcApiClient(
                    email=email,
                    password=password,
                    device_id=device_id,
                    device_model=DEVICE_MODEL,
                )
            )
            try:
                await client.login()
            except EvdcTwoFactorRequiredError:
                self._pending = client
                return self.status_dict()
            await self._finish_login(client)
            return self.status_dict()

    async def verify(self, code: str) -> dict:
        """Complete a login waiting for a two-factor code."""
        async with self._lock:
            if self._pending is None:
                raise EvdcAuthError("No login waiting for a verification code")
            await self._pending.verify_two_factor(code)
            client, self._pending = self._pending, None
            await self._finish_login(client)
            return self.status_dict()

    async def _finish_login(self, client: AsyncEvdcApiClient) -> None:
        # The device key is added to the account's keys (the phone's stays):
        # later logins need neither the password nor a code.
        device_key = await client.enroll_device_key()
        sync = client.client
        self._creds = _Credentials(
            email=sync.email,
            user_id=sync.user_id or "",
            device_id=sync.device_id,
            device_key=device_key,
        )
        self._client = client
        self.last_error = None
        await self._save_credentials()
        await self._repo.save_setting(KEY_LAST_ERROR, "")

    async def disconnect(self) -> None:
        """Revoke the device key and this client's session, forget the account."""
        async with self._lock:
            client, self._client, self._pending = self._client, None, None
            if client is not None:
                try:
                    sessions = await client.get_connected_sessions()
                    await client.remove_device_key()
                    current = next((s for s in sessions if s.is_current), None)
                    if current is not None and current.id:
                        await client.revoke_session(current.id)
                except EvdcApiError as exc:
                    _LOGGER.warning("EVDC: disconnecting the account failed: %s", exc)
                await client.close()
            self._creds = _Credentials(device_id=self._creds.device_id)
            await self._save_credentials()

    async def _save_credentials(self) -> None:
        c = self._creds
        for key, value in (
            (KEY_EMAIL, c.email),
            (KEY_USER_ID, c.user_id),
            (KEY_DEVICE_ID, c.device_id),
            (KEY_DEVICE_KEY, c.device_key),
            (KEY_ACCESS_TOKEN, c.access_token),
            (KEY_REFRESH_TOKEN, c.refresh_token),
        ):
            await self._repo.save_setting(key, value)

    async def _save_tokens(self) -> None:
        """Persist the tokens when the client refreshed them."""
        if self._client is None:
            return
        sync = self._client.client
        access, refresh = sync.access_token or "", sync.refresh_token or ""
        if (access, refresh) != (self._creds.access_token, self._creds.refresh_token):
            self._creds.access_token, self._creds.refresh_token = access, refresh
            await self._repo.save_setting(KEY_ACCESS_TOKEN, access)
            await self._repo.save_setting(KEY_REFRESH_TOKEN, refresh)

    # -- data ----------------------------------------------------------------

    async def fetch_sessions(self, since: datetime) -> list[ProviderSession]:
        """Billed sessions started since ``since`` (naive UTC), oldest first."""
        async with self._lock:
            if self._client is None:
                raise EvdcAuthError("No EVDC account connected")
            sessions: list[ProviderSession] = []
            page = 1
            try:
                while True:  # newest first: stop at the first page before `since`
                    result = await self._client.get_charge_history(
                        page, HISTORY_PAGE_SIZE
                    )
                    mapped = [to_provider_session(s) for s in result.sessions]
                    sessions += [
                        s
                        for s in mapped
                        if s and s.started_at and s.started_at >= since
                    ]
                    oldest = min(
                        (s.started_at for s in mapped if s and s.started_at),
                        default=None,
                    )
                    if not result.has_next or (oldest is not None and oldest < since):
                        break
                    page += 1
            except EvdcApiError as exc:
                await self._record_error(str(exc))
                raise
            finally:
                await self._save_tokens()
            await self._record_sync()
            return sorted(sessions, key=lambda s: s.started_at)

    async def get_receipt(self, external_id: str) -> tuple[str | None, bytes]:
        """The PDF receipt of a billed session: ``(filename, content)``."""
        async with self._lock:
            if self._client is None:
                raise EvdcAuthError("No EVDC account connected")
            try:
                receipt = await self._client.get_receipt(external_id)
            finally:
                await self._save_tokens()
            return receipt.filename, receipt.content

    async def _record_sync(self) -> None:
        self.last_sync = datetime.now(UTC).isoformat()
        self.last_error = None
        await self._repo.save_setting(KEY_LAST_SYNC, self.last_sync)
        await self._repo.save_setting(KEY_LAST_ERROR, "")

    async def _record_error(self, message: str) -> None:
        self.last_error = message
        await self._repo.save_setting(KEY_LAST_ERROR, message)
