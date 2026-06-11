"""ABRP (A Better Route Planner) telemetry service.

Periodically sends vehicle telemetry to the Iternio Telemetry API so that
ABRP can use live data for route planning and car-model calibration.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import TYPE_CHECKING

import httpx

from leapconnect.domain.settings.models import AbrpSettings

if TYPE_CHECKING:
    from leapmotor_api.models import Vehicle

    from leapconnect.application.vehicle_cache import VehicleStatusCache

_LOGGER = logging.getLogger(__name__)

ABRP_API_URL = "https://api.iternio.com/1/tlm/send"
ABRP_API_KEY = "6f6a554f-d8c8-4c72-8914-d5895f58b1eb"

# Adaptive intervals (seconds)
_INTERVAL_DRIVING = 10
_INTERVAL_CHARGING = 30
_INTERVAL_PARKED = 300


class AbrpService:
    """Sends live telemetry data to ABRP."""

    def __init__(self) -> None:
        self._settings = AbrpSettings()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._cache: VehicleStatusCache | None = None
        self._vehicles: list[Vehicle] = []
        self._last_error: str | None = None
        self._total_sends: int = 0
        self._total_errors: int = 0

    # -- public API ----------------------------------------------------------

    @property
    def settings(self) -> AbrpSettings:
        return self._settings

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def set_vehicles(
        self, vehicles: list[Vehicle], cache: VehicleStatusCache | None = None
    ) -> None:
        self._vehicles = vehicles
        self._cache = cache

    def update_settings(
        self,
        *,
        enabled: bool | None = None,
        user_token: str | None = None,
    ) -> AbrpSettings:
        if user_token is not None:
            self._settings.user_token = user_token.strip()
        if enabled is not None:
            self._settings.enabled = enabled

        if self._settings.enabled and self._settings.user_token:
            self._ensure_running()
        else:
            if enabled is False or not self._settings.enabled:
                self._request_stop()

        return self._settings

    def status_dict(self) -> dict:
        return {
            "enabled": self._settings.enabled,
            "user_token": self._settings.user_token,
            "is_running": self.is_running,
            "last_error": self._last_error,
            "total_sends": self._total_sends,
            "total_errors": self._total_errors,
        }

    async def stop(self) -> None:
        self._request_stop()
        if self._task and not self._task.done():
            with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(self._task, timeout=5)
        self._task = None

    # -- internals -----------------------------------------------------------

    def _ensure_running(self) -> None:
        if self._task and not self._task.done():
            self._stop.set()
        else:
            self._stop.clear()
            self._task = asyncio.create_task(self._loop(), name="abrp-telemetry")

    def _request_stop(self) -> None:
        self._stop.set()

    async def _loop(self) -> None:
        _LOGGER.info("ABRP telemetry service started")
        try:
            while self._settings.enabled:
                interval = await self._send_all()
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=interval)
                    self._stop.clear()
                    if not self._settings.enabled:
                        break
                except TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass
        finally:
            _LOGGER.info("ABRP telemetry service stopped")

    async def _send_all(self) -> float:
        """Send telemetry for all vehicles. Returns the next sleep interval."""
        if not self._vehicles or not self._cache:
            return _INTERVAL_PARKED

        min_interval = _INTERVAL_PARKED
        for vehicle in self._vehicles:
            try:
                status = self._cache.get_cached(vehicle.vin)
                if status is None:
                    continue
                interval = await self._send_telemetry(vehicle, status)
                min_interval = min(min_interval, interval)
            except Exception as exc:
                self._total_errors += 1
                self._last_error = f"{vehicle.vin}: {exc}"
                _LOGGER.exception("ABRP: failed to send for %s", vehicle.vin)

        return min_interval

    async def _send_telemetry(self, vehicle: Vehicle, status) -> float:
        """Build and send a single telemetry payload. Returns recommended interval."""
        tlm = self._build_tlm(status)

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                ABRP_API_URL,
                params={
                    "api_key": ABRP_API_KEY,
                    "token": self._settings.user_token,
                    "tlm": _json_compact(tlm),
                },
            )
            if resp.status_code != 200:
                self._total_errors += 1
                self._last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                _LOGGER.warning("ABRP HTTP %d: %s", resp.status_code, resp.text[:200])
            else:
                body = resp.json()
                if body.get("status") != "ok":
                    self._total_errors += 1
                    self._last_error = str(body)
                    _LOGGER.warning("ABRP error: %s", body)
                else:
                    self._total_sends += 1
                    self._last_error = None
                    _LOGGER.debug("ABRP: telemetry sent for %s", vehicle.vin)

        # Adaptive interval
        if status.is_charging:
            return _INTERVAL_CHARGING
        if status.driving and status.driving.speed and status.driving.speed > 0:
            return _INTERVAL_DRIVING
        return _INTERVAL_PARKED

    @staticmethod
    def _build_tlm(status) -> dict:
        """Map VehicleStatus fields to ABRP telemetry JSON."""
        tlm: dict = {}

        tlm["utc"] = int(time.time())

        b = status.battery
        if b:
            if b.precise_soc is not None:
                tlm["soc"] = round(b.precise_soc, 1)
            elif b.soc is not None:
                tlm["soc"] = b.soc

            if b.battery_power is not None:
                tlm["power"] = round(b.battery_power, 2)
            elif b.battery_current is not None and b.battery_voltage is not None:
                tlm["power"] = round(b.battery_current * b.battery_voltage / 1000, 2)

            if b.battery_voltage is not None:
                tlm["voltage"] = round(b.battery_voltage, 1)
            if b.battery_current is not None:
                tlm["current"] = round(b.battery_current, 2)

            if b.is_charging is not None:
                tlm["is_charging"] = b.is_charging

            if b.dc_input_fast_charge is not None:
                tlm["is_dcfc"] = b.dc_input_fast_charge == 1

            if b.min_battery_temp is not None:
                tlm["batt_temp"] = b.min_battery_temp

        d = status.driving
        if d:
            if d.speed is not None:
                tlm["speed"] = d.speed
            if d.total_mileage is not None:
                tlm["odometer"] = d.total_mileage
            if d.is_parked is not None:
                tlm["is_parked"] = d.is_parked
            if d.live_remaining_range is not None:
                tlm["est_battery_range"] = d.live_remaining_range

        loc = status.location
        if loc:
            if loc.latitude is not None:
                tlm["lat"] = loc.latitude
            if loc.longitude is not None:
                tlm["lon"] = loc.longitude

        c = status.climate
        if c:
            if c.outdoor_temp is not None:
                tlm["ext_temp"] = c.outdoor_temp
            if c.interior_temp is not None:
                tlm["cabin_temp"] = c.interior_temp
            if c.ac_setting is not None:
                tlm["hvac_setpoint"] = c.ac_setting

        t = status.tires
        if t:
            if t.front_left_kpa is not None:
                tlm["tire_pressure_fl"] = t.front_left_kpa
            if t.front_right_kpa is not None:
                tlm["tire_pressure_fr"] = t.front_right_kpa
            if t.rear_left_kpa is not None:
                tlm["tire_pressure_rl"] = t.rear_left_kpa
            if t.rear_right_kpa is not None:
                tlm["tire_pressure_rr"] = t.rear_right_kpa

        return tlm


def _json_compact(obj: dict) -> str:
    """Produce compact JSON without spaces."""
    import json

    return json.dumps(obj, separators=(",", ":"))
