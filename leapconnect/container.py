"""Composition root — owns all runtime state and service wiring.

Replaces the module-level globals that used to live in ``main.py``. A single
``AppContainer`` instance is created at import time (``container``) and
started/stopped by the FastAPI lifespan in ``leapconnect.api.app``.

This module is deliberately allowed to know about every layer: it constructs
the adapters, injects them into the application services, and exposes the
shared state the API routers operate on.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import HTTPException
from leapmotor_api import LeapmotorApiClient
from leapmotor_api.async_client import AsyncLeapmotorApiClient
from leapmotor_api.image import CarImagePackage
from leapmotor_api.models import Vehicle, VehicleStatus

from leapconnect import config
from leapconnect.application import settings_store
from leapconnect.application.commands import (
    command_allowed,
    execute_mqtt_command,
    execute_vehicle_command,
)
from leapconnect.application.notifications import NotificationDispatcher
from leapconnect.application.scheduler import VehicleDataScheduler
from leapconnect.application.vehicle_cache import VehicleStatusCache
from leapconnect.domain.identity.sessions import SessionStore
from leapconnect.domain.identity.throttle import LoginThrottle
from leapconnect.infrastructure.abrp.service import AbrpService
from leapconnect.infrastructure.logbuffer import RingBufferHandler
from leapconnect.infrastructure.mqtt.home_assistant import HomeAssistantMqttService
from leapconnect.infrastructure.persistence.sqlite_adapter import (
    SqlAlchemyRepository,
)

if TYPE_CHECKING:
    from fastapi import WebSocket

_LOGGER = logging.getLogger(__name__)


class AppContainer:
    """All mutable application state plus lifecycle management."""

    def __init__(self) -> None:
        # Leapmotor cloud connection
        self.sync_client: LeapmotorApiClient | None = None
        self.client: AsyncLeapmotorApiClient | None = None
        self.vehicles: list[Vehicle] = []
        self.connected: bool = False

        # Services (created in startup())
        self.repo: SqlAlchemyRepository | None = None
        self.scheduler: VehicleDataScheduler | None = None
        self.mqtt_service: HomeAssistantMqttService | None = None
        self.abrp_service: AbrpService | None = None
        self.vehicle_cache: VehicleStatusCache | None = None
        self.notification_dispatcher: NotificationDispatcher | None = None

        # Caches
        self.picture_cache: dict[str, dict[str, str]] = {}  # vin -> {name: data-URI}
        self.image_packages: dict[str, CarImagePackage] = {}  # vin -> package

        # WebSocket connection manager: vin -> set of WebSocket
        self.ws_connections: dict[str, set[WebSocket]] = {}

        # Live refresh — periodic cache refresh for VINs with active WS clients
        self.live_refresh_task: asyncio.Task | None = None
        self.live_refresh_interval: int = 30  # default 30s, 0 = disabled
        self._live_refresh_stop: asyncio.Event | None = None

        # Local dashboard sessions + login throttling
        self.sessions = SessionStore()
        self.login_throttle = LoginThrottle()

        # In-memory log buffer for the frontend log viewer
        self.log_handler = RingBufferHandler()
        self.log_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        self.log_handler.setLevel(logging.DEBUG)

        # Temporary-PIN save slot (Telegram commands must not clobber the
        # persisted PIN; see set_vehicle_pin()).
        self._saved_pin: str | None = None

    # -- accessors ------------------------------------------------------------

    def get_client(self) -> AsyncLeapmotorApiClient:
        if self.client is None:
            raise HTTPException(
                status_code=400, detail="Not connected. Please login first."
            )
        return self.client

    def find_vehicle(self, vin: str) -> Vehicle:
        for v in self.vehicles:
            if v.vin == vin:
                return v
        raise HTTPException(status_code=404, detail=f"Vehicle {vin} not found")

    # -- WebSocket broadcasting -------------------------------------------------

    async def ws_broadcast(self, vin: str, data: dict) -> None:
        """Send a JSON message to all WebSocket clients subscribed to a VIN."""
        clients = self.ws_connections.get(vin, set())
        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            clients.discard(ws)

    async def _on_cache_update(
        self, vin: str, status: VehicleStatus, cache_age: float
    ) -> None:
        """Called by VehicleStatusCache when fresh data is fetched from API."""
        from leapconnect.api.schemas.vehicle import VehicleStatusSchema

        payload = {
            "type": "status_update",
            "vin": vin,
            "status": VehicleStatusSchema.from_model(status).model_dump(mode="json"),
            "cache_age_seconds": round(cache_age, 1),
        }
        await self.ws_broadcast(vin, payload)

    # -- live refresh -----------------------------------------------------------

    async def _live_refresh_loop(self) -> None:
        """Periodically refresh vehicle cache for VINs with active WS clients."""
        _LOGGER.info(
            "Live refresh started (interval=%d sec)", self.live_refresh_interval
        )
        try:
            while self.live_refresh_interval > 0:
                await asyncio.sleep(self.live_refresh_interval)
                if self._live_refresh_stop and self._live_refresh_stop.is_set():
                    break
                if not self.vehicle_cache or not self.vehicles:
                    continue
                # Only refresh VINs with active WebSocket connections
                active_vins = {
                    vin for vin, conns in self.ws_connections.items() if conns
                }
                if not active_vins:
                    continue
                for vehicle in self.vehicles:
                    if vehicle.vin in active_vins:
                        try:
                            await self.vehicle_cache.get(vehicle)
                        except Exception as exc:
                            _LOGGER.debug(
                                "Live refresh failed for %s: %s", vehicle.vin, exc
                            )
        except asyncio.CancelledError:
            pass
        finally:
            _LOGGER.info("Live refresh loop stopped")

    def start_live_refresh(self) -> None:
        """Start (or restart) the live refresh background task."""
        self.stop_live_refresh()
        if self.live_refresh_interval <= 0:
            return
        self._live_refresh_stop = asyncio.Event()
        self.live_refresh_task = asyncio.create_task(
            self._live_refresh_loop(), name="live-refresh"
        )

    def stop_live_refresh(self) -> None:
        """Stop the live refresh background task if running."""
        if self._live_refresh_stop:
            self._live_refresh_stop.set()
        if self.live_refresh_task and not self.live_refresh_task.done():
            self.live_refresh_task.cancel()
        self.live_refresh_task = None
        self._live_refresh_stop = None

    @property
    def live_refresh_running(self) -> bool:
        return self.live_refresh_task is not None and not self.live_refresh_task.done()

    # -- cloud connection ---------------------------------------------------------

    def _close_sync_client(self) -> None:
        if self.sync_client:
            self.sync_client.close()

    async def connect(
        self,
        *,
        username: str,
        password: str,
        cert_path: str,
        key_path: str,
        p12_password: str | None = None,
    ) -> list[Vehicle]:
        """Connect to the Leapmotor cloud; wires scheduler/ABRP/live-refresh.

        On failure the connection state is reset and the exception re-raised.
        """
        self._close_sync_client()
        try:
            self.sync_client = LeapmotorApiClient(
                username=username,
                password=password,
                app_cert_path=cert_path,
                app_key_path=key_path,
                account_p12_password=p12_password,
            )
            self.client = AsyncLeapmotorApiClient(self.sync_client)
            await self.client.login()
            self.vehicles = await self.client.get_vehicle_list()
            self.connected = True

            if self.scheduler:
                self.scheduler.set_client(self.client, self.vehicles)
                self.scheduler.start()
            if self.abrp_service:
                self.abrp_service.set_vehicles(self.vehicles, self.vehicle_cache)
            if self.live_refresh_interval > 0:
                self.start_live_refresh()
            return self.vehicles
        except Exception:
            self.reset_connection()
            raise

    def reset_connection(self) -> None:
        """Clear connection state after a failure or explicit disconnect."""
        self.connected = False
        self.sync_client = None
        self.client = None
        self.vehicles = []
        if self.scheduler:
            self.scheduler.set_client(None, [])

    async def auto_connect(self) -> None:
        """Try to connect using saved credentials at startup."""
        if not self.repo:
            return

        account = await self.repo.get_account()
        if not account:
            _LOGGER.info("Auto-connect: no saved account, skipping")
            return

        cert_path = account["cert_path"]
        key_path = account["key_path"]
        if not Path(cert_path).is_file() or not Path(key_path).is_file():
            _LOGGER.warning("Auto-connect: certificate files missing, skipping")
            return

        try:
            await self.connect(
                username=account["username"],
                password=account["password"],
                cert_path=cert_path,
                key_path=key_path,
                p12_password=account.get("p12_password"),
            )
            _LOGGER.info("Auto-connect: success, %d vehicle(s)", len(self.vehicles))

            # Restore saved vehicle PIN for MQTT commands
            saved_pin = await self.repo.get_setting("mqtt_vehicle_pin")
            if saved_pin and self.sync_client:
                self.sync_client.operation_password = saved_pin
                _LOGGER.info("Auto-connect: vehicle PIN restored from DB")
        except Exception as exc:
            _LOGGER.warning("Auto-connect: failed (%s), app will run offline", exc)

    def disconnect(self) -> None:
        """Disconnect from the Leapmotor cloud without clearing session."""
        self.stop_live_refresh()
        if self.abrp_service:
            self.abrp_service.set_vehicles([], None)
        self._close_sync_client()
        self.reset_connection()

    def logout(self) -> None:
        """Disconnect from the Leapmotor API and clear cached vehicle data."""
        self._close_sync_client()
        self.reset_connection()
        self.picture_cache.clear()
        self.image_packages.clear()

    # -- vehicle PIN ---------------------------------------------------------------

    def set_vehicle_pin(self, pin: str) -> None:
        """Temporarily set/restore the vehicle operation PIN on the sync client.

        When called with a non-empty pin, saves the current PIN and sets the
        new one. When called with empty string, restores the previously saved
        PIN. This ensures Telegram commands don't interfere with the persisted
        PIN.
        """
        if not self.sync_client:
            return
        if pin.strip():
            self._saved_pin = self.sync_client.operation_password
            self.sync_client.operation_password = pin.strip()
        else:
            self.sync_client.operation_password = self._saved_pin

    # -- vehicle images --------------------------------------------------------------

    def cached_vehicle_image(self, vin: str) -> Path | None:
        """Return the locally-cached image file for a VIN, or None."""
        if config.VEHICLE_IMAGE_DIR.is_dir():
            for path in config.VEHICLE_IMAGE_DIR.glob(f"{vin}.*"):
                if path.is_file():
                    return path
        return None

    async def get_image_package(self, vin: str) -> CarImagePackage:
        """Get or create a cached CarImagePackage for the given VIN."""
        if vin in self.image_packages:
            return self.image_packages[vin]

        client = self.get_client()
        vehicle = self.find_vehicle(vin)
        picture_data = await client.get_car_picture(vehicle)
        key = (picture_data.get("data") or {}).get("key")
        if not key:
            raise HTTPException(status_code=404, detail="No picture key available")

        zip_bytes = await client.download_car_picture_package(picture_key=key)
        pkg = await asyncio.to_thread(CarImagePackage.from_zip, zip_bytes)
        self.image_packages[vin] = pkg
        return pkg

    async def compose_notification_image(self, vin: str) -> bytes | None:
        """Compose a dynamic vehicle image for notifications."""
        try:
            pkg = await self.get_image_package(vin)
            vehicle = self.find_vehicle(vin)
            if self.vehicle_cache:
                status = await self.vehicle_cache.get(vehicle)
            else:
                status = await self.get_client().get_vehicle_status(vehicle)
            return await asyncio.to_thread(
                pkg.compose, status, charge_frame=0, format="PNG"
            )
        except Exception as exc:
            _LOGGER.warning("Failed to compose notification image for %s: %s", vin, exc)
            return None

    # -- command execution (Telegram / MQTT callbacks) ---------------------------

    def check_command_right(self, vin: str, command: str) -> bool:
        """Sync helper for Telegram menu filtering."""
        try:
            vehicle = self.find_vehicle(vin)
        except Exception:
            return False
        return command_allowed(vehicle, command)

    async def execute_command(self, vin: str, command: str) -> dict | None:
        """Execute a vehicle command by name (Telegram bot callback)."""
        if not self.client:
            return None
        try:
            vehicle = self.find_vehicle(vin)
        except Exception:
            return None
        return await execute_vehicle_command(self.client, vehicle, command)

    async def handle_mqtt_command(self, vin: str, command: str) -> None:
        """Handle a command received from Home Assistant via MQTT."""
        if not self.client:
            _LOGGER.warning("MQTT command %s for %s ignored: no client", command, vin)
            return

        result = None
        try:
            result = await execute_mqtt_command(self.client, vin, command)
            if result is None:
                _LOGGER.warning("MQTT: unknown command '%s' for %s", command, vin)
                return
        except Exception as exc:
            _LOGGER.exception("MQTT command %s failed for %s", command, vin)
            result = {"error": str(exc)}

        if self.mqtt_service and result:
            await self.mqtt_service.publish_command_result(vin, command, result)

    async def mqtt_publish_status(self, vin: str, status) -> None:
        """Publish vehicle status to MQTT if enabled."""
        if not self.mqtt_service or not self.mqtt_service.is_connected:
            return
        vehicle = self.find_vehicle(vin)
        image_pkg = self.image_packages.get(vin)
        await self.mqtt_service.publish_vehicle_status(vehicle, status, image_pkg)
        # Also publish current scheduler intervals
        if self.scheduler:
            s = self.scheduler.settings
            await self.mqtt_service.publish_scheduler_settings(
                vin, s.interval_minutes, s.mqtt_interval_seconds
            )

    async def handle_mqtt_settings(self, key: str, value: int) -> None:
        """Handle a polling-interval/limit change received from HA via MQTT."""
        if not self.scheduler or not self.repo:
            _LOGGER.warning("MQTT settings change ignored: scheduler not available")
            return

        if key == "polling_interval":
            settings = self.scheduler.update_settings(mqtt_interval_seconds=value)
            await self.repo.save_scheduler_settings(settings)
            _LOGGER.info("MQTT settings applied: %s = %d", key, value)
            if self.mqtt_service and self.mqtt_service.is_connected:
                for v in self.vehicles:
                    await self.mqtt_service.publish_scheduler_settings(
                        v.vin,
                        settings.interval_minutes,
                        settings.mqtt_interval_seconds,
                    )
        elif key == "charge_limit":
            if not self.client:
                _LOGGER.warning("MQTT charge_limit change ignored: no API client")
                return
            for v in self.vehicles:
                try:
                    await self.client.set_charge_limit(v.vin, value)
                    _LOGGER.info("Charge limit set to %d%% for %s", value, v.vin)
                except Exception as exc:
                    _LOGGER.exception(
                        "Failed to set charge limit for %s: %s", v.vin, exc
                    )
        elif key == "ac_temperature":
            if not self.client:
                _LOGGER.warning("MQTT ac_temperature change ignored: no API client")
                return
            for v in self.vehicles:
                try:
                    await self.client.ac_on(v.vin, params={"temperature": str(value)})
                    _LOGGER.info("AC temperature set to %d°C for %s", value, v.vin)
                except Exception as exc:
                    _LOGGER.exception("Failed to set AC temp for %s: %s", v.vin, exc)
        else:
            _LOGGER.warning("MQTT: unknown setting key '%s'", key)

    async def _on_scheduler_status(self, vehicle, status) -> None:
        """Scheduler → MQTT publishing (status + cloud stats)."""
        if not (self.mqtt_service and self.mqtt_service.is_connected):
            return
        image_pkg = self.image_packages.get(vehicle.vin)
        if not image_pkg:
            with suppress(Exception):
                image_pkg = await self.get_image_package(vehicle.vin)
        await self.mqtt_service.publish_vehicle_status(vehicle, status, image_pkg)

        # Publish cloud stats (consumption rank + weekly breakdown)
        try:
            client = self.get_client()
            cloud_stats: dict = {}
            with suppress(Exception):
                rank_result = await client.get_consumption_weekly_rank(vehicle)
                if rank_result and rank_result.rank:
                    cloud_stats["consumption_rank"] = rank_result.rank.rank
                    cloud_stats["consumption_kwh_100km"] = (
                        rank_result.rank.hundred_km_ec
                    )
            with suppress(Exception):
                breakdown = await client.get_consumption_last_week_breakdown(vehicle)
                if breakdown:
                    cloud_stats["weekly_total_ec"] = breakdown.total_ec
                    cloud_stats["weekly_driver_ec"] = breakdown.driver_ec
                    cloud_stats["weekly_ac_ec"] = breakdown.ac_ec
                    cloud_stats["weekly_other_ec"] = breakdown.other_ec
            if cloud_stats:
                await self.mqtt_service.publish_cloud_stats(vehicle.vin, cloud_stats)
        except Exception as exc:
            _LOGGER.debug("Cloud stats MQTT publish skipped: %s", exc)

    # -- lifecycle --------------------------------------------------------------------

    async def startup(self) -> None:
        """Initialise persistence and services (the old lifespan body)."""
        root_logger = logging.getLogger()
        if self.log_handler not in root_logger.handlers:
            root_logger.addHandler(self.log_handler)
        # Capture the running event loop for thread-safe log broadcasting
        self.log_handler.set_loop(asyncio.get_running_loop())

        db_path = config.database_path()
        config.migrate_legacy_db(db_path)

        self.repo = SqlAlchemyRepository(config.database_url())
        await self.repo.init_db()
        _LOGGER.info("History DB initialised at %s", db_path)

        # Restore scheduler settings from DB
        saved = await self.repo.load_scheduler_settings()

        # Initialize shared vehicle status cache
        self.vehicle_cache = VehicleStatusCache(
            rate_limit_seconds=saved.rate_limit_seconds
        )
        self.vehicle_cache.set_on_update(self._on_cache_update)

        # Initialize notification dispatcher
        self.notification_dispatcher = NotificationDispatcher(
            repo=self.repo,
            image_composer=self.compose_notification_image,
            vehicle_cache=self.vehicle_cache,
            command_executor=self.execute_command,
            rights_checker=self.check_command_right,
            pin_checker=lambda: bool(
                self.sync_client and self.sync_client.operation_password
            ),
            pin_setter=self.set_vehicle_pin,
        )
        await self.notification_dispatcher.reload_config()

        self.scheduler = VehicleDataScheduler(
            self.repo,
            cache=self.vehicle_cache,
            notification_dispatcher=self.notification_dispatcher,
        )
        self.scheduler.update_settings(
            enabled=saved.enabled,
            interval_minutes=saved.interval_minutes,
            mqtt_interval_seconds=saved.mqtt_interval_seconds,
            rate_limit_seconds=saved.rate_limit_seconds,
            transition_detection_enabled=saved.transition_detection_enabled,
            transition_poll_interval_seconds=saved.transition_poll_interval_seconds,
            transition_min_event_interval_seconds=(
                saved.transition_min_event_interval_seconds
            ),
        )
        _LOGGER.info(
            "Scheduler settings loaded: enabled=%s, history=%d min,"
            " mqtt=%d sec, rate_limit=%d sec, transition=%s (poll=%ds, dedup=%ds)",
            saved.enabled,
            saved.interval_minutes,
            saved.mqtt_interval_seconds,
            saved.rate_limit_seconds,
            saved.transition_detection_enabled,
            saved.transition_poll_interval_seconds,
            saved.transition_min_event_interval_seconds,
        )

        # Initialize MQTT Home Assistant service
        self.mqtt_service = HomeAssistantMqttService()
        self.mqtt_service.set_command_callback(self.handle_mqtt_command)
        self.mqtt_service.set_settings_callback(self.handle_mqtt_settings)
        mqtt_settings = await settings_store.load_mqtt_settings(self.repo)
        self.mqtt_service.update_settings(
            enabled=mqtt_settings.enabled,
            broker=mqtt_settings.broker,
            port=mqtt_settings.port,
            username=mqtt_settings.username,
            password=mqtt_settings.password,
            use_tls=mqtt_settings.use_tls,
            discovery_prefix=mqtt_settings.discovery_prefix,
            topic_prefix=mqtt_settings.topic_prefix,
        )
        _LOGGER.info("MQTT HA service initialised: enabled=%s", mqtt_settings.enabled)

        # Sync the MQTT polling interval so discovery publishes the right value
        self.mqtt_service.mqtt_interval_seconds = saved.mqtt_interval_seconds

        # Wire scheduler → MQTT publishing
        self.scheduler.set_on_status_callback(self._on_scheduler_status)

        # Initialize ABRP telemetry service
        self.abrp_service = AbrpService()
        abrp_settings = await settings_store.load_abrp_settings(self.repo)
        self.abrp_service.update_settings(
            enabled=abrp_settings.enabled,
            user_token=abrp_settings.user_token,
        )
        _LOGGER.info("ABRP service initialised: enabled=%s", abrp_settings.enabled)

        # Initialize live refresh from saved setting
        live_raw = await self.repo.get_setting("live_refresh_interval")
        self.live_refresh_interval = int(live_raw) if live_raw else 30
        _LOGGER.info("Live refresh interval: %d sec", self.live_refresh_interval)

        # Auto-connect using saved credentials
        await self.auto_connect()

        # Start live refresh if configured (needs client from auto-connect)
        if self.live_refresh_interval > 0 and self.connected:
            self.start_live_refresh()

    async def shutdown(self) -> None:
        self.stop_live_refresh()
        if self.abrp_service:
            await self.abrp_service.stop()
        if self.mqtt_service:
            await self.mqtt_service.stop()
        if self.scheduler:
            await self.scheduler.stop()
        if self.repo:
            await self.repo.close()
        self._close_sync_client()


# The single application-wide container instance.
container = AppContainer()
