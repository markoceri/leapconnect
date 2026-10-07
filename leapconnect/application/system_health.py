"""Host health monitoring: low disk space alerts.

Periodically reads free space on the filesystem(s) holding the database and
data directory and, when it falls under the global thresholds (Settings →
General → System), raises the ``disk_space_low`` event: on the first low
reading, then every 24 h while low, re-armed once space recovers. The event
then goes to every notification channel that has it enabled.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from leapconnect.domain.system import (
    DiskAlertSettings,
    DiskUsage,
    is_low_disk,
    low_disk_alert_due,
)

if TYPE_CHECKING:
    from leapconnect.application.notifications import NotificationDispatcher

_LOGGER = logging.getLogger(__name__)

DISK_EVENT = "disk_space_low"
DISK_CHECK_INTERVAL_SECONDS = 15 * 60
# Shown instead of a vehicle name in the notification title.
SENDER_NAME = "LeapConnect"


def lowest_disk(usages: list[DiskUsage], limits: DiskAlertSettings) -> DiskUsage | None:
    """The tightest filesystem that is under the thresholds, if any."""
    low = [u for u in usages if is_low_disk(u, limits)]
    return min(low, key=lambda u: u.free_percent) if low else None


class DiskSpaceMonitor:
    """Background task raising the ``disk_space_low`` event."""

    def __init__(
        self,
        dispatcher: NotificationDispatcher,
        read_usage: Callable[[], list[DiskUsage]],
        load_limits: Callable[[], Awaitable[DiskAlertSettings]],
        interval_seconds: float = DISK_CHECK_INTERVAL_SECONDS,
    ) -> None:
        self._dispatcher = dispatcher
        self._read_usage = read_usage
        self._load_limits = load_limits
        self._interval = interval_seconds
        self._last_alert: datetime | None = None
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="disk-space-monitor")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._task = None

    async def current_usage(self) -> list[DiskUsage]:
        """Read usage now (disk calls are blocking: run off the event loop)."""
        return await asyncio.to_thread(self._read_usage)

    async def _loop(self) -> None:
        while True:
            try:
                await self.check()
            except Exception:
                _LOGGER.exception("Disk space check failed")
            await asyncio.sleep(self._interval)

    async def check(self, now: datetime | None = None) -> bool:
        """Raise the event if it's due; True when it was raised."""
        limits = await self._load_limits()
        if not limits.enabled:
            self._last_alert = None
            return False
        low = lowest_disk(await self.current_usage(), limits)
        if low is None:
            self._last_alert = None  # recovered → re-arm
            return False
        now = now or datetime.now(UTC)
        if not low_disk_alert_due(True, self._last_alert, now):
            return False
        self._last_alert = now
        _LOGGER.warning(
            "Low disk space: %.1f GB free (%.1f%%) on %s",
            low.free_gb,
            low.free_percent,
            low.path,
        )
        await self._dispatcher.dispatch_system(
            DISK_EVENT,
            SENDER_NAME,
            {
                "free_gb": f"{low.free_gb:.1f}",
                "free_percent": f"{low.free_percent:.1f}",
                "total_gb": f"{low.total_gb:.1f}",
                "disk_path": low.path,
                "disk_limits": limits.describe(),
            },
        )
        return True
