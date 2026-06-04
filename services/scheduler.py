"""Background scheduler for periodic vehicle data collection.

Runs as an asyncio task inside the FastAPI process. Polls all connected
vehicles at a configurable interval and persists snapshots via the
repository port.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from leapmotor_api.exceptions import LeapmotorApiError

from models import SchedulerSettings, VehicleSnapshot
from services.transition_detector import TransitionDetector

if TYPE_CHECKING:
    from leapmotor_api.async_client import AsyncLeapmotorApiClient
    from leapmotor_api.models import Vehicle

    from persistence.repository import VehicleHistoryRepository
    from services.notification_dispatcher import NotificationDispatcher
    from services.vehicle_cache import VehicleStatusCache

_LOGGER = logging.getLogger(__name__)

MIN_INTERVAL_MINUTES = 1
MAX_INTERVAL_MINUTES = 1440  # 24 h
MIN_MQTT_INTERVAL_SECONDS = 10
MAX_MQTT_INTERVAL_SECONDS = 86400  # 24 h
MIN_TRANSITION_POLL_SECONDS = 5
MAX_TRANSITION_POLL_SECONDS = 300


class VehicleDataScheduler:
    """Periodically polls vehicle status and saves snapshots."""

    def __init__(
        self,
        repo: VehicleHistoryRepository,
        cache: VehicleStatusCache | None = None,
        notification_dispatcher: NotificationDispatcher | None = None,
    ) -> None:
        self._repo = repo
        self._cache = cache
        self._notification_dispatcher = notification_dispatcher
        self._settings = SchedulerSettings()
        self._history_task: asyncio.Task | None = None
        self._mqtt_task: asyncio.Task | None = None
        self._transition_task: asyncio.Task | None = None
        self._history_stop = asyncio.Event()
        self._mqtt_stop = asyncio.Event()
        self._transition_stop = asyncio.Event()
        self._last_run: datetime | None = None
        self._last_error: str | None = None
        self._total_runs: int = 0
        self._total_errors: int = 0

        # Transition detector
        self._detector = TransitionDetector(
            min_event_interval_seconds=self._settings.transition_min_event_interval_seconds,
        )

        # Injected at runtime by main.py when the user logs in
        self._client: AsyncLeapmotorApiClient | None = None
        self._vehicles: list[Vehicle] = []

        # Optional callback for publishing status (e.g. MQTT)
        self._on_status_callback = None

    # -- public API ----------------------------------------------------------

    @property
    def settings(self) -> SchedulerSettings:
        return self._settings

    @property
    def is_running(self) -> bool:
        history_running = (
            self._history_task is not None and not self._history_task.done()
        )
        mqtt_running = self._mqtt_task is not None and not self._mqtt_task.done()
        transition_running = (
            self._transition_task is not None and not self._transition_task.done()
        )
        return history_running or mqtt_running or transition_running

    def status_dict(self) -> dict:
        return {
            "enabled": self._settings.enabled,
            "interval_minutes": self._settings.interval_minutes,
            "mqtt_interval_seconds": self._settings.mqtt_interval_seconds,
            "rate_limit_seconds": self._settings.rate_limit_seconds,
            "transition_detection_enabled": self._settings.transition_detection_enabled,
            "transition_poll_interval_seconds": (
                self._settings.transition_poll_interval_seconds
            ),
            "transition_min_event_interval_seconds": (
                self._settings.transition_min_event_interval_seconds
            ),
            "is_running": self.is_running,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "last_error": self._last_error,
            "total_runs": self._total_runs,
            "total_errors": self._total_errors,
        }

    def set_client(
        self, client: AsyncLeapmotorApiClient | None, vehicles: list[Vehicle]
    ) -> None:
        self._client = client
        self._vehicles = vehicles
        if self._cache:
            self._cache.set_client(client)

    def set_on_status_callback(self, callback) -> None:
        """Set a callback invoked with (vehicle, status) after each MQTT poll."""
        self._on_status_callback = callback

    def update_settings(
        self,
        *,
        enabled: bool | None = None,
        interval_minutes: int | None = None,
        mqtt_interval_seconds: int | None = None,
        rate_limit_seconds: int | None = None,
        transition_detection_enabled: bool | None = None,
        transition_poll_interval_seconds: int | None = None,
        transition_min_event_interval_seconds: int | None = None,
    ) -> SchedulerSettings:
        if interval_minutes is not None:
            interval_minutes = max(
                MIN_INTERVAL_MINUTES, min(MAX_INTERVAL_MINUTES, interval_minutes)
            )
            self._settings.interval_minutes = interval_minutes
        if mqtt_interval_seconds is not None:
            mqtt_interval_seconds = max(
                MIN_MQTT_INTERVAL_SECONDS,
                min(MAX_MQTT_INTERVAL_SECONDS, mqtt_interval_seconds),
            )
            self._settings.mqtt_interval_seconds = mqtt_interval_seconds
        if rate_limit_seconds is not None:
            rate_limit_seconds = max(
                1, min(MAX_MQTT_INTERVAL_SECONDS, rate_limit_seconds)
            )
            self._settings.rate_limit_seconds = rate_limit_seconds
            # Sync with cache
            if self._cache:
                self._cache.rate_limit_seconds = rate_limit_seconds
        if transition_detection_enabled is not None:
            self._settings.transition_detection_enabled = transition_detection_enabled
        if transition_poll_interval_seconds is not None:
            transition_poll_interval_seconds = max(
                MIN_TRANSITION_POLL_SECONDS,
                min(MAX_TRANSITION_POLL_SECONDS, transition_poll_interval_seconds),
            )
            self._settings.transition_poll_interval_seconds = (
                transition_poll_interval_seconds
            )
        if transition_min_event_interval_seconds is not None:
            transition_min_event_interval_seconds = max(
                1, min(300, transition_min_event_interval_seconds)
            )
            self._settings.transition_min_event_interval_seconds = (
                transition_min_event_interval_seconds
            )
            self._detector.min_event_interval_seconds = (
                transition_min_event_interval_seconds
            )
        if enabled is not None:
            self._settings.enabled = enabled

        # Apply change immediately
        if self._settings.enabled:
            self._ensure_running()
        else:
            self._request_stop()

        return self._settings

    def start(self) -> None:
        if self._settings.enabled:
            self._ensure_running()

    async def stop(self) -> None:
        self._request_stop()
        for task in (self._history_task, self._mqtt_task, self._transition_task):
            if task and not task.done():
                with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                    await asyncio.wait_for(task, timeout=5)
        self._history_task = None
        self._mqtt_task = None
        self._transition_task = None

    # -- internals -----------------------------------------------------------

    def _ensure_running(self) -> None:
        # History loop
        if self._history_task and not self._history_task.done():
            self._history_stop.set()
        else:
            self._history_stop.clear()
            self._history_task = asyncio.create_task(
                self._history_loop(), name="scheduler-history"
            )
        # MQTT loop
        if self._mqtt_task and not self._mqtt_task.done():
            self._mqtt_stop.set()
        else:
            self._mqtt_stop.clear()
            self._mqtt_task = asyncio.create_task(
                self._mqtt_loop(), name="scheduler-mqtt"
            )
        # Transition detection loop
        if self._settings.transition_detection_enabled:
            if self._transition_task and not self._transition_task.done():
                self._transition_stop.set()
            else:
                self._transition_stop.clear()
                self._transition_task = asyncio.create_task(
                    self._transition_loop(), name="scheduler-transition"
                )

    def _request_stop(self) -> None:
        self._history_stop.set()
        self._mqtt_stop.set()
        self._transition_stop.set()

    async def _history_loop(self) -> None:
        _LOGGER.info(
            "Scheduler started (history interval=%d min)",
            self._settings.interval_minutes,
        )
        try:
            while self._settings.enabled:
                await self._poll_history()
                try:
                    await asyncio.wait_for(
                        self._history_stop.wait(),
                        timeout=self._settings.interval_minutes * 60,
                    )
                    self._history_stop.clear()
                except TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass
        finally:
            _LOGGER.info("Scheduler history loop stopped")

    async def _mqtt_loop(self) -> None:
        _LOGGER.info(
            "Scheduler started (MQTT interval=%d sec)",
            self._settings.mqtt_interval_seconds,
        )
        try:
            while self._settings.enabled:
                await self._poll_mqtt()
                try:
                    await asyncio.wait_for(
                        self._mqtt_stop.wait(),
                        timeout=self._settings.mqtt_interval_seconds,
                    )
                    self._mqtt_stop.clear()
                except TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass
        finally:
            _LOGGER.info("Scheduler MQTT loop stopped")

    async def _poll_history(self) -> None:
        """Poll vehicles and save snapshots to the history DB."""
        if not self._client or not self._vehicles:
            _LOGGER.debug("Scheduler: no client or vehicles, skipping history poll")
            return

        _LOGGER.info(
            "Scheduler: polling %d vehicle(s) for history", len(self._vehicles)
        )
        self._total_runs += 1
        self._last_run = datetime.utcnow()
        self._last_error = None

        for vehicle in self._vehicles:
            try:
                if self._cache:
                    status = await self._cache.get(vehicle)
                else:
                    status = await self._client.get_vehicle_status(vehicle)

                def _enum_val(v):
                    if v is None:
                        return None
                    return v.value if hasattr(v, "value") else v

                snapshot = VehicleSnapshot(
                    vin=vehicle.vin,
                    timestamp=status.collect_time or datetime.utcnow(),
                    battery_soc=status.battery.soc if status.battery else None,
                    battery_current=status.battery.battery_current
                    if status.battery
                    else None,
                    battery_voltage=status.battery.battery_voltage
                    if status.battery
                    else None,
                    battery_charging_power_kw=status.battery.charging_power_kw
                    if status.battery
                    else None,
                    battery_discharge_power_kw=status.battery.discharging_power_kw
                    if status.battery
                    else None,
                    battery_is_charging=status.is_charging,
                    battery_dump_energy=status.battery.dump_energy
                    if status.battery
                    else None,
                    battery_expected_mileage=status.battery.expected_mileage
                    if status.battery
                    else None,
                    battery_charge_state=_enum_val(status.battery.charge_state)
                    if status.battery
                    else None,
                    drive_is_parked=status.driving.is_parked
                    if status.driving
                    else None,
                    drive_speed=status.driving.speed if status.driving else None,
                    drive_total_mileage=status.driving.total_mileage
                    if status.driving
                    else None,
                    vehicle_is_charging=status.is_charging,
                    vehicle_is_plugged=status.is_plugged,
                    vehicle_is_parked=status.is_parked,
                    vehicle_is_locked=status.is_locked,
                    vehicle_is_regening=status.is_regening,
                    vehicle_latitude=status.location.latitude
                    if status.location
                    else None,
                    vehicle_longitude=status.location.longitude
                    if status.location
                    else None,
                    climate_outdoor_temp=status.climate.outdoor_temp
                    if status.climate
                    else None,
                    tire_front_left_pressure=status.tires.front_left_kpa
                    if status.tires
                    else None,
                    tire_front_right_pressure=status.tires.front_right_kpa
                    if status.tires
                    else None,
                    tire_rear_left_pressure=status.tires.rear_left_kpa
                    if status.tires
                    else None,
                    tire_rear_right_pressure=status.tires.rear_right_kpa
                    if status.tires
                    else None,
                )
                await self._repo.save_snapshot(snapshot)
                _LOGGER.info(
                    "Scheduler: saved snapshot for %s (SOC=%s%%)",
                    vehicle.vin,
                    status.battery.soc,
                )
            except LeapmotorApiError as exc:
                self._total_errors += 1
                self._last_error = f"{vehicle.vin}: {exc}"
                _LOGGER.warning("Scheduler: API error polling %s: %s", vehicle.vin, exc)
            except Exception as exc:
                self._total_errors += 1
                self._last_error = f"{vehicle.vin}: {exc}"
                _LOGGER.exception("Scheduler: failed to poll %s", vehicle.vin)

    async def _poll_mqtt(self) -> None:
        """Poll vehicles and publish status to MQTT listeners."""
        if not self._client or not self._vehicles:
            _LOGGER.debug("Scheduler: no client or vehicles, skipping MQTT poll")
            return
        if not self._on_status_callback:
            return

        _LOGGER.info("Scheduler: polling %d vehicle(s) for MQTT", len(self._vehicles))

        for vehicle in self._vehicles:
            try:
                if self._cache:
                    status = await self._cache.get(vehicle)
                else:
                    status = await self._client.get_vehicle_status(vehicle)
                await self._on_status_callback(vehicle, status)
            except Exception as exc:
                _LOGGER.warning(
                    "Scheduler: MQTT poll failed for %s: %s", vehicle.vin, exc
                )

    # -- transition detection ------------------------------------------------

    async def _transition_loop(self) -> None:
        _LOGGER.info(
            "Scheduler started (transition poll interval=%d sec)",
            self._settings.transition_poll_interval_seconds,
        )
        try:
            while (
                self._settings.enabled and self._settings.transition_detection_enabled
            ):
                await self._poll_transitions()
                try:
                    await asyncio.wait_for(
                        self._transition_stop.wait(),
                        timeout=self._settings.transition_poll_interval_seconds,
                    )
                    self._transition_stop.clear()
                except TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass
        finally:
            _LOGGER.info("Scheduler transition loop stopped")

    async def _poll_transitions(self) -> None:
        """Poll vehicles, detect state transitions, save events + snapshots."""
        if not self._client or not self._vehicles:
            return

        for vehicle in self._vehicles:
            try:
                if self._cache:
                    status = await self._cache.get(vehicle)
                else:
                    status = await self._client.get_vehicle_status(vehicle)

                events = self._detector.detect(vehicle.vin, status)
                if not events:
                    continue

                # Save each event to the events table
                for event in events:
                    try:
                        await self._repo.save_event(event)
                    except Exception as exc:
                        _LOGGER.warning(
                            "Scheduler: failed to save event for %s: %s",
                            vehicle.vin,
                            exc,
                        )

                # Auto-create/finalize charging session costs
                for event in events:
                    try:
                        await self._handle_charging_cost_event(event, status)
                    except Exception as exc:
                        _LOGGER.debug(
                            "Scheduler: charging cost event error for %s: %s",
                            vehicle.vin,
                            exc,
                        )

                # Dispatch notifications
                if self._notification_dispatcher:
                    try:
                        await self._notification_dispatcher.dispatch(
                            events, status, vehicle
                        )
                    except Exception as exc:
                        _LOGGER.warning(
                            "Scheduler: notification dispatch error for %s: %s",
                            vehicle.vin,
                            exc,
                        )

                # Save a full snapshot on transition (one per poll, not per event)
                def _enum_val(v):
                    if v is None:
                        return None
                    return v.value if hasattr(v, "value") else v

                snapshot = VehicleSnapshot(
                    vin=vehicle.vin,
                    timestamp=status.collect_time or datetime.utcnow(),
                    battery_soc=status.battery.soc if status.battery else None,
                    battery_current=status.battery.battery_current
                    if status.battery
                    else None,
                    battery_voltage=status.battery.battery_voltage
                    if status.battery
                    else None,
                    battery_charging_power_kw=status.battery.charging_power_kw
                    if status.battery
                    else None,
                    battery_discharge_power_kw=status.battery.discharging_power_kw
                    if status.battery
                    else None,
                    battery_is_charging=status.is_charging,
                    battery_dump_energy=status.battery.dump_energy
                    if status.battery
                    else None,
                    battery_expected_mileage=status.battery.expected_mileage
                    if status.battery
                    else None,
                    battery_charge_state=_enum_val(status.battery.charge_state)
                    if status.battery
                    else None,
                    drive_is_parked=status.driving.is_parked
                    if status.driving
                    else None,
                    drive_speed=status.driving.speed if status.driving else None,
                    drive_total_mileage=status.driving.total_mileage
                    if status.driving
                    else None,
                    vehicle_is_charging=status.is_charging,
                    vehicle_is_plugged=status.is_plugged,
                    vehicle_is_parked=status.is_parked,
                    vehicle_is_locked=status.is_locked,
                    vehicle_is_regening=status.is_regening,
                    vehicle_latitude=status.location.latitude
                    if status.location
                    else None,
                    vehicle_longitude=status.location.longitude
                    if status.location
                    else None,
                    climate_outdoor_temp=status.climate.outdoor_temp
                    if status.climate
                    else None,
                    tire_front_left_pressure=status.tires.front_left_kpa
                    if status.tires
                    else None,
                    tire_front_right_pressure=status.tires.front_right_kpa
                    if status.tires
                    else None,
                    tire_rear_left_pressure=status.tires.rear_left_kpa
                    if status.tires
                    else None,
                    tire_rear_right_pressure=status.tires.rear_right_kpa
                    if status.tires
                    else None,
                )
                await self._repo.save_snapshot(snapshot)
                _LOGGER.info(
                    "Scheduler: transition snapshot saved for %s (%d event(s))",
                    vehicle.vin,
                    len(events),
                )
            except LeapmotorApiError as exc:
                _LOGGER.warning(
                    "Scheduler: transition poll API error for %s: %s",
                    vehicle.vin,
                    exc,
                )
            except Exception:
                _LOGGER.exception(
                    "Scheduler: transition poll failed for %s", vehicle.vin
                )

    async def _handle_charging_cost_event(self, event, status) -> None:
        """Auto-create/finalize session cost on charge_start/charge_stop."""

        from models import ChargingSessionCost

        if event.event_type == "charge_start":
            # Determine default tier
            tier_id = "home_grid"  # default
            # If DC/fast charge detected
            if hasattr(status, "battery") and status.battery:
                charge_state = getattr(status.battery, "charge_state", None)
                if hasattr(charge_state, "value"):
                    charge_state = charge_state.value
                # charge_state 2 = DC fast charge typically
                if charge_state == 2:
                    tier_id = "public_dc"
            sc = ChargingSessionCost(
                vin=event.vin,
                start_ts=event.timestamp,
                tier_id=tier_id,
            )
            await self._repo.upsert_session_cost(sc)
            _LOGGER.info(
                "Charging cost: session started for %s, tier=%s", event.vin, tier_id
            )

        elif event.event_type == "charge_stop":
            # Find the most recent open session for this VIN
            costs = await self._repo.get_session_costs(event.vin)
            open_session = next((c for c in costs if c.end_ts is None), None)
            if open_session:
                open_session.end_ts = event.timestamp
                # Try to compute energy from snapshots
                try:
                    history = await self._repo.get_history(event.vin, days=1)
                    # Find snapshots in session window
                    session_snaps = [
                        s
                        for s in history
                        if s.timestamp >= open_session.start_ts
                        and s.timestamp <= event.timestamp
                    ]
                    if len(session_snaps) >= 2:
                        start_energy = (
                            session_snaps[0].battery_dump_energy or 0
                        ) / 1000
                        end_energy = (session_snaps[-1].battery_dump_energy or 0) / 1000
                        energy = end_energy - start_energy
                        if energy > 0:
                            open_session.energy_kwh = round(energy, 2)
                            # Get tier price
                            tiers = await self._repo.get_price_tiers()
                            tier = next(
                                (t for t in tiers if t.id == open_session.tier_id),
                                None,
                            )
                            if tier:
                                open_session.cost = round(energy * tier.price_kwh, 4)
                except Exception as exc:
                    _LOGGER.debug("Charging cost: energy calc error: %s", exc)

                await self._repo.upsert_session_cost(open_session)
                _LOGGER.info(
                    "Charging cost: session ended for %s, energy=%.2f kWh, cost=€%.4f",
                    event.vin,
                    open_session.energy_kwh or 0,
                    open_session.cost or 0,
                )
