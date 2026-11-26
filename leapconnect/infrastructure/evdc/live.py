"""Live progress of an EVDC account's sessions in progress, over socket.io.

The socket is opened only while it's wanted — someone is following a session
in progress — and closed when no session is in progress any more, or nobody
asked for one for ``IDLE_TIMEOUT``. The socket runs in its own threads (the
``python-socketio`` client); progress events are kept by session id.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from evdc_network_api.live import EvdcLiveClient

from leapconnect.domain.charging.providers import ProviderLiveProgress

if TYPE_CHECKING:
    from collections.abc import Callable

    from evdc_network_api import EvdcApiClient, SessionProgress

_LOGGER = logging.getLogger(__name__)

# Closed when nobody followed a session in progress for this long
IDLE_TIMEOUT = 600.0  # seconds
WATCHDOG_EVERY = 60.0  # seconds
# After a failed connection, wait this long before trying again
RETRY_AFTER = 300.0  # seconds


def _naive_utc(ts: datetime | None) -> datetime | None:
    if ts is None or ts.tzinfo is None:
        return ts
    return ts.astimezone(UTC).replace(tzinfo=None)


def to_live_progress(p: SessionProgress) -> ProviderLiveProgress:
    return ProviderLiveProgress(
        energy_kwh=p.consumed_energy_kwh,
        power_kw=p.power_kw,
        max_power_kw=p.max_power_kw,
        current_a=p.current_a,
        updated_at=_naive_utc(p.time) or datetime.now(UTC).replace(tzinfo=None),
    )


class EvdcLiveFeed:
    """The live socket of one account, opened on demand."""

    def __init__(
        self,
        client: Callable[[], EvdcApiClient | None],
        factory: Callable[..., EvdcLiveClient] = EvdcLiveClient,
    ) -> None:
        self._client = client  # the account's (sync) API client, when connected
        self._factory = factory
        self._live: EvdcLiveClient | None = None
        self._progress: dict[str, ProviderLiveProgress] = {}
        self._lock = threading.Lock()  # progress comes from the socket threads
        self._wanted_at = 0.0
        self._failed_at: float | None = None
        self._watchdog: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        return self._live is not None

    def progress(self, session_id: str) -> ProviderLiveProgress | None:
        with self._lock:
            return self._progress.get(session_id)

    async def want(self, session_ids: set[str]) -> None:
        """Sessions in progress are being followed: open the socket (if not
        open), and forget the progress of the sessions that ended."""
        now = time.monotonic()
        self._wanted_at = now
        with self._lock:
            for sid in [k for k in self._progress if k not in session_ids]:
                del self._progress[sid]
        if self._live is not None:
            return
        if self._failed_at is not None and now - self._failed_at < RETRY_AFTER:
            return
        client = self._client()
        if client is None:
            return
        try:
            live = self._factory(client, self._on_progress)
            await asyncio.to_thread(live.connect)
        except Exception as exc:  # noqa: BLE001 - optional, never fatal
            # EvdcApiError (no token, extra missing) or a socket.io
            # connection error
            self._failed_at = now
            _LOGGER.warning("EVDC live progress unavailable: %s", exc)
            return
        self._failed_at = None
        self._live = live
        self._watchdog = asyncio.create_task(self._watch())
        _LOGGER.info("EVDC live progress: socket open")

    async def stop(self) -> None:
        """Close the socket and forget the progress."""
        live, self._live = self._live, None
        task, self._watchdog = self._watchdog, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
        with self._lock:
            self._progress.clear()
        if live is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(live.disconnect)
            _LOGGER.info("EVDC live progress: socket closed")

    async def _watch(self) -> None:
        while self._live is not None:
            await asyncio.sleep(WATCHDOG_EVERY)
            if time.monotonic() - self._wanted_at > IDLE_TIMEOUT:
                await self.stop()
                return

    def _on_progress(self, p: SessionProgress) -> None:
        if not p.session_id:
            return
        with self._lock:
            self._progress[p.session_id] = to_live_progress(p)
