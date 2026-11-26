"""EVDC charging provider: one account's billed sessions and the network's
charging points, via ``evdc-network-api``.

Read-only: the client logs in, reads the charging history, the receipts and
the charging points. An account is connected once with e-mail and password
(plus a two-factor code when enabled); a device key is then enrolled so later
logins need neither the password, which is never stored, nor a new code.
Disconnecting revokes the device key and this client's session.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from evdc_network_api import (
    AsyncEvdcApiClient,
    EvdcApiClient,
    EvdcApiError,
    EvdcAuthError,
    EvdcTwoFactorRequiredError,
)

from leapconnect.application.ports.charging_provider import (
    ChargingProvider,
    ChargingProviderError,
)
from leapconnect.domain.charging.models import ChargingProviderAccount
from leapconnect.domain.charging.providers import ProviderFee, ProviderSession
from leapconnect.domain.charging.stations import ChargingStation

if TYPE_CHECKING:
    from evdc_network_api import ChargingSession, Evse

    from leapconnect.application.ports.repositories import AppRepository

_LOGGER = logging.getLogger(__name__)

PROVIDER = "evdc"
LABEL = "EVDC"
DEVICE_MODEL = "LeapConnect"
HISTORY_PAGE_SIZE = 20

# Charging points search: a bounded walk (the backend pages nearest first,
# with no radius of its own), and a short cache for map pans back and forth
MAX_STATIONS = 300
STATIONS_CACHE_TTL = 120.0  # seconds
STATIONS_CACHE_SIZE = 32

_FEES = (
    ("time_fee", "Time fee"),
    ("parking_fee", "Parking fee"),
    ("time_surcharge_fee", "Time surcharge"),
)


def _naive_utc(ts: datetime | None) -> datetime | None:
    if ts is None or ts.tzinfo is None:
        return ts
    return ts.astimezone(UTC).replace(tzinfo=None)


def _is_dc(evse: Evse | None) -> bool | None:
    """One EVSE is one connector: DC, or AC (1 or 3 phases); ``None`` when
    the power type is unknown."""
    types = {f.power_type for f in (evse.facilities if evse else []) if f.power_type}
    return ("DC" in types) if types else None


def _address(evse: Evse) -> str | None:
    a = evse.address
    if a is None:
        return None
    city = " ".join(p for p in (a.postal_code, a.city) if p)
    return ", ".join(p for p in (a.street, city) if p) or None


def to_station(evse: Evse, evse_id: str | None = None) -> ChargingStation | None:
    """A charging point; ``None`` without an EVSE id."""
    evse_id = evse.evse_id or evse_id
    if not evse_id:
        return None
    pricing = evse.pricing
    return ChargingStation(
        provider=PROVIDER,
        evse_id=evse_id,
        name=evse.name,
        operator=evse.operator_name,
        address=_address(evse),
        latitude=evse.latitude,
        longitude=evse.longitude,
        max_power_kw=evse.max_power_kw,
        is_dc=_is_dc(evse),
        plugs=tuple(evse.plugs),
        is_open_24h=evse.is_open_24h,
        status=evse.status,
        price=pricing.price if pricing else None,
        price_unit=pricing.unit if pricing else None,
        currency=pricing.currency if pricing else None,
        distance_m=evse.distance_m,
    )


def to_provider_session(
    s: ChargingSession, account_id: int | None = None
) -> ProviderSession | None:
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
    station = to_station(s.station, s.evse_id) if s.station else None
    if station is not None:
        # The station's live fields are not the session's
        station = replace(
            station,
            status=None,
            price=None,
            price_unit=None,
            currency=None,
            distance_m=None,
        )
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
        evse_id=s.evse_id or (station.evse_id if station else None),
        operator=s.operator,
        location=location,
        is_dc=_is_dc(s.station),
        latitude=s.station.latitude if s.station else None,
        longitude=s.station.longitude if s.station else None,
        account_id=account_id,
        station=station,
    )


def _error(exc: EvdcApiError) -> ChargingProviderError:
    return ChargingProviderError(f"{LABEL}: {exc}", auth=isinstance(exc, EvdcAuthError))


class EvdcService(ChargingProvider):
    """One EVDC account."""

    provider = PROVIDER
    label = LABEL

    def __init__(
        self, repo: AppRepository, account: ChargingProviderAccount | None = None
    ) -> None:
        self._repo = repo
        self.account = account or ChargingProviderAccount(provider=PROVIDER)
        self._client: AsyncEvdcApiClient | None = None
        self._pending: AsyncEvdcApiClient | None = None  # waiting for a 2FA code
        self._lock = asyncio.Lock()
        self._stations_cache: dict[tuple, tuple[float, list[ChargingStation]]] = {}
        c = self.account.credentials
        if self.account.username and c.get("device_key") and c.get("user_id"):
            self._client = AsyncEvdcApiClient(
                EvdcApiClient(
                    email=self.account.username,
                    access_token=c.get("access_token") or None,
                    refresh_token=c.get("refresh_token") or None,
                    device_key=c["device_key"],
                    user_id=c["user_id"],
                    device_id=c.get("device_id") or None,
                    device_model=DEVICE_MODEL,
                )
            )

    # -- state ---------------------------------------------------------------

    @property
    def account_id(self) -> int | None:
        return self.account.id

    @property
    def username(self) -> str | None:
        return self.account.username or None

    @property
    def connected(self) -> bool:
        return self._client is not None

    @property
    def auto_sync(self) -> bool:
        return self.account.auto_sync

    @property
    def two_factor_pending(self) -> str | None:
        return self._pending.two_factor_pending if self._pending else None

    # -- connect / disconnect ------------------------------------------------

    async def login(self, email: str, password: str) -> str | None:
        """Log in. Returns the two-factor method (``"email"``/``"totp"``)
        when a code is needed (then call :meth:`verify`), else ``None``: the
        account is connected and saved."""
        async with self._lock:
            client = AsyncEvdcApiClient(
                EvdcApiClient(
                    email=email,
                    password=password,
                    device_id=secrets.token_hex(32),
                    device_model=DEVICE_MODEL,
                )
            )
            try:
                await client.login()
            except EvdcTwoFactorRequiredError:
                self._pending = client
                return client.two_factor_pending or "email"
            except EvdcApiError as exc:
                raise _error(exc) from exc
            await self._finish_login(client)
            return None

    async def verify(self, code: str) -> None:
        """Complete a login waiting for a two-factor code."""
        async with self._lock:
            if self._pending is None:
                raise ChargingProviderError(
                    "No login waiting for a verification code", auth=True
                )
            try:
                await self._pending.verify_two_factor(code)
            except EvdcApiError as exc:
                raise _error(exc) from exc
            client, self._pending = self._pending, None
            await self._finish_login(client)

    async def _finish_login(self, client: AsyncEvdcApiClient) -> None:
        # The device key is added to the account's keys (the phone's stays):
        # later logins need neither the password nor a code.
        try:
            device_key = await client.enroll_device_key()
        except EvdcApiError as exc:
            raise _error(exc) from exc
        sync = client.client
        self.account.username = sync.email
        self.account.credentials = {
            "user_id": sync.user_id or "",
            "device_id": sync.device_id,
            "device_key": device_key,
            "access_token": sync.access_token or "",
            "refresh_token": sync.refresh_token or "",
        }
        self.account.last_error = None
        self._client = client
        await self._repo.save_provider_account(self.account)

    async def disconnect(self) -> None:
        """Revoke the device key and this client's session."""
        async with self._lock:
            client, self._client, self._pending = self._client, None, None
            if client is None:
                return
            try:
                sessions = await client.get_connected_sessions()
                await client.remove_device_key()
                current = next((s for s in sessions if s.is_current), None)
                if current is not None and current.id:
                    await client.revoke_session(current.id)
            except EvdcApiError as exc:
                _LOGGER.warning("EVDC: disconnecting the account failed: %s", exc)
            await client.close()

    async def set_auto_sync(self, enabled: bool) -> None:
        self.account.auto_sync = enabled
        await self._repo.save_provider_account(self.account)

    async def _save_tokens(self) -> None:
        """Persist the tokens when the client refreshed them."""
        if self._client is None or self.account.id is None:
            return
        sync = self._client.client
        access, refresh = sync.access_token or "", sync.refresh_token or ""
        c = self.account.credentials
        if (access, refresh) != (c.get("access_token"), c.get("refresh_token")):
            c["access_token"], c["refresh_token"] = access, refresh
            await self._repo.save_provider_account(self.account)

    def _require_client(self) -> AsyncEvdcApiClient:
        if self._client is None:
            raise ChargingProviderError(f"{LABEL} account not connected", auth=True)
        return self._client

    # -- data ----------------------------------------------------------------

    async def fetch_sessions(self, since: datetime) -> list[ProviderSession]:
        """Billed sessions started since ``since`` (naive UTC), oldest first."""
        async with self._lock:
            client = self._require_client()
            sessions: list[ProviderSession] = []
            page = 1
            try:
                while True:  # newest first: stop at the first page before `since`
                    result = await client.get_charge_history(page, HISTORY_PAGE_SIZE)
                    mapped = [
                        to_provider_session(s, self.account.id) for s in result.sessions
                    ]
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
                await self._record(error=str(exc))
                raise _error(exc) from exc
            finally:
                await self._save_tokens()
            await self._record(error=None)
            return sorted(sessions, key=lambda s: s.started_at)

    async def get_receipt(self, external_id: str) -> tuple[str | None, bytes]:
        async with self._lock:
            client = self._require_client()
            try:
                receipt = await client.get_receipt(external_id)
            except EvdcApiError as exc:
                raise _error(exc) from exc
            finally:
                await self._save_tokens()
            return receipt.filename, receipt.content

    async def get_station(self, evse_id: str) -> ChargingStation | None:
        async with self._lock:
            client = self._require_client()
            try:
                evse = await client.get_evse(evse_id)
            except EvdcApiError as exc:
                raise _error(exc) from exc
            finally:
                await self._save_tokens()
            return to_station(evse, evse_id)

    async def find_stations(
        self, latitude: float, longitude: float, radius_m: float
    ) -> list[ChargingStation]:
        key = (round(latitude, 3), round(longitude, 3), round(radius_m))
        now = time.monotonic()
        cached = self._stations_cache.get(key)
        if cached is not None and now - cached[0] < STATIONS_CACHE_TTL:
            return cached[1]
        async with self._lock:
            client = self._require_client()
            try:
                found = await client.find_stations_near(
                    latitude, longitude, radius_m=radius_m, max_results=MAX_STATIONS
                )
            except EvdcApiError as exc:
                raise _error(exc) from exc
            finally:
                await self._save_tokens()
        stations = [s for e in found if (s := to_station(e)) is not None]
        if len(self._stations_cache) >= STATIONS_CACHE_SIZE:
            oldest = min(self._stations_cache, key=lambda k: self._stations_cache[k][0])
            del self._stations_cache[oldest]
        self._stations_cache[key] = (now, stations)
        return stations

    async def _record(self, *, error: str | None) -> None:
        if error is None:
            self.account.last_sync = datetime.now(UTC).isoformat()
        self.account.last_error = error
        if self.account.id is not None:
            await self._repo.save_provider_account(self.account)
