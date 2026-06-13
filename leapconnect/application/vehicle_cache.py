"""Shared vehicle status cache with single-flight and rate limiting.

Ensures that only one request to the Leapmotor API is made at a time per
vehicle, regardless of how many consumers (MQTT scheduler, history scheduler,
frontend API) request the status concurrently.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from leapmotor_api.exceptions import LeapmotorApiError

if TYPE_CHECKING:
    from leapmotor_api.async_client import AsyncLeapmotorApiClient
    from leapmotor_api.models import Vehicle, VehicleStatus

_LOGGER = logging.getLogger(__name__)

DEFAULT_RATE_LIMIT_SECONDS = 10

# Type alias for the on-update callback: (vin, status, cache_age_seconds)
OnUpdateCallback = Callable[[str, "VehicleStatus", float], Awaitable[None]]


class VehicleStatusCache:
    """Rate-limited, single-flight cache for vehicle status requests."""

    def __init__(self, rate_limit_seconds: int = DEFAULT_RATE_LIMIT_SECONDS) -> None:
        self._rate_limit_seconds = rate_limit_seconds
        self._client: AsyncLeapmotorApiClient | None = None
        self._cache: dict[str, tuple[VehicleStatus, float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._on_update: OnUpdateCallback | None = None

    # -- Configuration -------------------------------------------------------

    @property
    def rate_limit_seconds(self) -> int:
        return self._rate_limit_seconds

    @rate_limit_seconds.setter
    def rate_limit_seconds(self, value: int) -> None:
        self._rate_limit_seconds = max(1, value)

    def set_client(self, client: AsyncLeapmotorApiClient | None) -> None:
        self._client = client

    def set_on_update(self, callback: OnUpdateCallback | None) -> None:
        """Register a callback invoked when fresh data is fetched from API."""
        self._on_update = callback

    async def _notify_update(self, vin: str, status: VehicleStatus) -> None:
        """Fire the on-update callback if registered."""
        if self._on_update:
            try:
                age = self.cache_age(vin) or 0.0
                await self._on_update(vin, status, age)
            except Exception:
                _LOGGER.debug("on_update callback error for %s", vin)

    # -- Public API ----------------------------------------------------------

    async def get(self, vehicle: Vehicle) -> VehicleStatus:
        """Get vehicle status, returning cached value if within rate limit.

        Uses single-flight: concurrent callers for the same VIN will wait for
        a single in-progress request rather than issuing duplicate requests.
        """
        if not self._client:
            raise RuntimeError("VehicleStatusCache: no API client configured")

        vin = vehicle.vin

        # Fast path: cache hit within rate limit
        cached = self._cache.get(vin)
        if cached and (time.time() - cached[1]) < self._rate_limit_seconds:
            _LOGGER.debug("Cache HIT for %s (age=%.1fs)", vin, time.time() - cached[1])
            return cached[0]

        # Slow path: single-flight fetch
        if vin not in self._locks:
            self._locks[vin] = asyncio.Lock()

        async with self._locks[vin]:
            # Double-check after acquiring lock (another coroutine may have fetched)
            cached = self._cache.get(vin)
            if cached and (time.time() - cached[1]) < self._rate_limit_seconds:
                _LOGGER.debug(
                    "Cache HIT (post-lock) for %s (age=%.1fs)",
                    vin,
                    time.time() - cached[1],
                )
                return cached[0]

            _LOGGER.debug("Cache MISS for %s — fetching from API", vin)
            status = await self._fetch_with_retry(vehicle)
            self._cache[vin] = (status, time.time())
            await self._notify_update(vin, status)
            return status

    async def force_refresh(self, vehicle: Vehicle) -> VehicleStatus:
        """Invalidate cache and fetch fresh data, ignoring rate limit."""
        if not self._client:
            raise RuntimeError("VehicleStatusCache: no API client configured")

        vin = vehicle.vin

        if vin not in self._locks:
            self._locks[vin] = asyncio.Lock()

        async with self._locks[vin]:
            _LOGGER.debug("Force refresh for %s", vin)
            status = await self._fetch_with_retry(vehicle)
            self._cache[vin] = (status, time.time())
            await self._notify_update(vin, status)
            return status

    async def _fetch_with_retry(self, vehicle: Vehicle) -> VehicleStatus:
        """Fetch vehicle status with one retry for transient server-side errors.

        Error code 39 ("Information verification failed") is returned by the
        Leapmotor API after a token refresh or re-login.
        clear auth, perform a full re-login, then retry.
        """
        assert self._client is not None  # caller must ensure client is set
        try:
            return await self._client.get_vehicle_status(vehicle)
        except LeapmotorApiError as exc:
            msg = str(exc).lower()
            if "try again" in msg or "verification failed" in msg:
                _LOGGER.warning(
                    "Transient API error for %s, performing full re-login: %s",
                    vehicle.vin,
                    exc,
                )
                try:
                    self._client.client._clear_auth()
                    await self._client.login()
                except Exception as login_exc:
                    _LOGGER.warning(
                        "Re-login failed for %s: %s", vehicle.vin, login_exc
                    )
                    raise exc from login_exc
                return await self._client.get_vehicle_status(vehicle)
            raise

    def get_cached(self, vin: str) -> VehicleStatus | None:
        """Return the cached status without fetching, or None if not cached."""
        cached = self._cache.get(vin)
        return cached[0] if cached else None

    def cache_age(self, vin: str) -> float | None:
        """Return the age in seconds of the cached value, or None."""
        cached = self._cache.get(vin)
        return (time.time() - cached[1]) if cached else None

    def invalidate(self, vin: str) -> None:
        """Remove a VIN from the cache."""
        self._cache.pop(vin, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
