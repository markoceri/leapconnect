"""Location tracking mode: periodic position updates via the notifiers."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from leapconnect.application.ports.notifier import Notification
from leapconnect.domain.telemetry.models import VehicleEvent
from leapconnect.infrastructure.telegram.notifier import TelegramNotifier

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from leapconnect.application.ports.notifier import BaseNotifier
    from leapconnect.application.ports.repositories import AppRepository

_LOGGER = logging.getLogger(__name__)


class LocationTracker:
    """Per-VIN periodic location notifications (Telegram sendLocation)."""

    def __init__(
        self,
        repo: AppRepository,
        vehicle_cache: object | None,
        notifiers: Callable[[], Iterable[BaseNotifier]],
        on_start: Callable[[], None] | None = None,
    ) -> None:
        self._repo = repo
        self._vehicle_cache = vehicle_cache
        self._notifiers = notifiers  # () -> active notifier instances
        self._on_start = on_start  # e.g. ensure Telegram callback polling
        # vin -> {interval_seconds, task}
        self._tracking: dict[str, dict] = {}

    async def start(
        self, vin: str, interval_seconds: int = 60, base_url: str = ""
    ) -> bool:
        """Start sending periodic location updates for a VIN."""
        if vin in self._tracking:
            # Already tracking — update interval
            self._tracking[vin]["interval_seconds"] = interval_seconds
            return True
        self._tracking[vin] = {
            "interval_seconds": interval_seconds,
            "task": asyncio.create_task(self._tracking_loop(vin)),
        }
        # Ensure Telegram callback polling is active for stop buttons
        if self._on_start:
            self._on_start()
        _LOGGER.info("Tracking started for %s (every %ds)", vin, interval_seconds)
        # Persist tracking_start event
        with contextlib.suppress(Exception):
            await self._repo.save_event(
                VehicleEvent(
                    vin=vin,
                    timestamp=datetime.now(UTC),
                    event_type="tracking_start",
                    field_name="tracking",
                    old_value=None,
                    new_value=f"{interval_seconds}s",
                )
            )
        return True

    async def stop(self, vin: str) -> bool:
        """Stop location tracking for a VIN."""
        info = self._tracking.pop(vin, None)
        if info and info.get("task"):
            info["task"].cancel()
            _LOGGER.info("Tracking stopped for %s", vin)
            # Persist tracking_stop event
            with contextlib.suppress(Exception):
                await self._repo.save_event(
                    VehicleEvent(
                        vin=vin,
                        timestamp=datetime.now(UTC),
                        event_type="tracking_stop",
                        field_name="tracking",
                        old_value=None,
                        new_value=None,
                    )
                )
            return True
        return False

    def is_tracking(self, vin: str) -> bool:
        return vin in self._tracking

    def info(self, vin: str) -> dict | None:
        info = self._tracking.get(vin)
        if info:
            return {"interval_seconds": info["interval_seconds"]}
        return None

    async def _tracking_loop(self, vin: str) -> None:
        """Periodic loop that sends location notifications via Telegram sendLocation."""
        try:
            while vin in self._tracking:
                info = self._tracking.get(vin)
                if not info:
                    break
                interval = info["interval_seconds"]

                # Get latest cached position from the vehicle cache
                lat = lon = None
                if self._vehicle_cache:
                    cached = self._vehicle_cache.get_cached(vin)
                    if cached:
                        lat = getattr(cached, "latitude", None) or (
                            cached.vehicle.latitude
                            if hasattr(cached, "vehicle") and cached.vehicle
                            else None
                        )
                        lon = getattr(cached, "longitude", None) or (
                            cached.vehicle.longitude
                            if hasattr(cached, "vehicle") and cached.vehicle
                            else None
                        )
                        if not lat and hasattr(cached, "location") and cached.location:
                            lat = cached.location.latitude
                            lon = cached.location.longitude

                if lat and lon:
                    # Build inline keyboard with Stop button (callback_data, not URL)
                    reply_markup = {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "⏹ Stop tracking",
                                    "callback_data": f"stop_tracking:{vin}",
                                },
                            ]
                        ]
                    }

                    # Use native sendLocation for map preview
                    for notifier in self._notifiers():
                        if isinstance(notifier, TelegramNotifier):
                            try:
                                await notifier.send_location(
                                    lat,
                                    lon,
                                    reply_markup=reply_markup,
                                )
                            except Exception as exc:
                                _LOGGER.warning("Tracking send error: %s", exc)
                        else:
                            # Fallback for non-Telegram notifiers
                            maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                            body = (
                                f'📍 <a href="{maps_url}">View on map</a>'
                                f"\nLat: {lat:.5f} · Lon: {lon:.5f}"
                            )
                            notification = Notification(
                                event_type="tracking",
                                title="📡 Location update",
                                body=body,
                                vin=vin,
                                timestamp=datetime.now(UTC),
                            )
                            try:
                                await notifier.send(notification)
                            except Exception as exc:
                                _LOGGER.warning("Tracking send error: %s", exc)

                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            _LOGGER.error("Tracking loop error for %s: %s", vin, exc)
        finally:
            self._tracking.pop(vin, None)
