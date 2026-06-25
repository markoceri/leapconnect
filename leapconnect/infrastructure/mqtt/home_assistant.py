"""Home Assistant MQTT integration service.

Publishes vehicle state, commands, messages, and dynamic car image
to an MQTT broker using Home Assistant's MQTT Discovery protocol.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import TYPE_CHECKING, Any

import aiomqtt

from leapconnect.asyncutils import spawn
from leapconnect.domain.settings.models import MqttSettings

if TYPE_CHECKING:
    from leapmotor_api.image import CarImagePackage
    from leapmotor_api.models import Vehicle, VehicleStatus

_LOGGER = logging.getLogger(__name__)


class HomeAssistantMqttService:
    """Manages MQTT connection and publishes vehicle data to Home Assistant."""

    def __init__(self) -> None:
        self._settings = MqttSettings()
        self._client: aiomqtt.Client | None = None
        self._connected: bool = False
        self._task: asyncio.Task | None = None
        self._last_error: str | None = None
        self._discovery_sent: set[str] = set()
        self._mqtt_interval_seconds: int = 60

    @property
    def settings(self) -> MqttSettings:
        return self._settings

    @property
    def mqtt_interval_seconds(self) -> int:
        """Polling interval published to the Home Assistant number entity."""
        return self._mqtt_interval_seconds

    @mqtt_interval_seconds.setter
    def mqtt_interval_seconds(self, value: int) -> None:
        self._mqtt_interval_seconds = value

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def _availability_topic(self) -> str:
        """Bridge availability topic (online/offline) used by HA entities."""
        return f"{self._settings.topic_prefix}/bridge/state"

    def update_settings(self, **kwargs: Any) -> MqttSettings:
        """Update MQTT settings and reconnect if needed."""
        changed = False
        for key, value in kwargs.items():
            if value is not None and hasattr(self._settings, key):
                if getattr(self._settings, key) != value:
                    setattr(self._settings, key, value)
                    changed = True

        if changed or kwargs.get("enabled") is not None:
            if self._settings.enabled and self._settings.broker:
                self._restart()
            else:
                self._request_stop()

        return self._settings

    def start(self) -> None:
        """Start the MQTT connection if enabled."""
        if self._settings.enabled and self._settings.broker:
            self._ensure_running()

    async def stop(self) -> None:
        """Stop the MQTT connection."""
        # Best-effort graceful "offline" so HA marks entities unavailable
        # immediately (the Last Will only fires on an ungraceful disconnect).
        if self._connected and self._client:
            with contextlib.suppress(Exception):
                await self._client.publish(
                    self._availability_topic, "offline", qos=1, retain=True
                )
        self._request_stop()
        if self._task and not self._task.done():
            with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(self._task, timeout=5)
        self._task = None
        self._connected = False
        self._client = None

    async def publish_vehicle_status(
        self,
        vehicle: Vehicle,
        status: VehicleStatus,
        image_package: CarImagePackage | None = None,
        current_zone: str | None = None,
    ) -> None:
        """Publish full vehicle state to MQTT with HA discovery."""
        if not self._connected or not self._settings.enabled:
            return

        vin = vehicle.vin
        device_name = vehicle.vehicle_nickname or f"Leapmotor {vehicle.car_type}"
        device_id = f"leapconnect_{vin.lower()}"

        # Ensure discovery configs are published
        if vin not in self._discovery_sent:
            try:
                await self._publish_discovery(vehicle, device_id, device_name)
                self._discovery_sent.add(vin)
            except Exception as exc:
                _LOGGER.error("MQTT discovery publish failed for %s: %s", vin, exc)
                return

        # Publish state values
        prefix = f"{self._settings.topic_prefix}/{vin}"

        try:
            state_data = self._build_state_payload(status)
            await self._publish(f"{prefix}/state", json.dumps(state_data), retain=True)
        except Exception as exc:
            _LOGGER.warning("MQTT state payload failed for %s: %s", vin, exc)

        # Publish individual sensor values for HA
        try:
            await self._publish_sensors(prefix, status, current_zone)
        except Exception as exc:
            _LOGGER.warning("MQTT sensor publish failed for %s: %s", vin, exc)

        # Publish location
        if status.location and status.location.latitude and status.location.longitude:
            location = json.dumps(
                {
                    "latitude": status.location.latitude,
                    "longitude": status.location.longitude,
                    "gps_accuracy": 10,
                }
            )
            await self._publish(f"{prefix}/location", location, retain=True)

        # Publish dynamic car image
        if image_package:
            try:
                img_bytes = image_package.compose(status, format="PNG")
                await self._publish(f"{prefix}/image", img_bytes, retain=True)
            except Exception as exc:
                _LOGGER.warning("Failed to compose car image for MQTT: %s", exc)
        else:
            _LOGGER.debug("No image package available for %s", vin)

    async def publish_messages(self, vin: str, messages: list[dict]) -> None:
        """Publish vehicle messages to MQTT."""
        if not self._connected or not self._settings.enabled:
            return
        prefix = f"{self._settings.topic_prefix}/{vin}"
        payload = json.dumps(messages[:20])  # Limit to last 20
        await self._publish(f"{prefix}/messages", payload, retain=True)

    async def publish_command_result(
        self, vin: str, command: str, result: dict
    ) -> None:
        """Publish a command result to MQTT."""
        if not self._connected or not self._settings.enabled:
            return
        prefix = f"{self._settings.topic_prefix}/{vin}"
        payload = json.dumps({"command": command, "result": result})
        await self._publish(f"{prefix}/command_result", payload, retain=False)

    # -- Private methods -----------------------------------------------------

    # Ability code → Right codes (mirrors frontend ABILITY_TO_RIGHTS)
    _ABILITY_TO_RIGHTS: dict[int, list[int]] = {
        1: [110],
        2: [120],
        3: [130],
        4: [150],
        6: [170],
        9: [171],
        10: [190],
        11: [161],
        12: [230],
        14: [301],
        15: [320],
        17: [170, 171],
        18: [460],
        24: [130],
        25: [160],
        30: [180],
        34: [510],
        35: [340],
        36: [230],
        38: [360, 361],
        40: [380],
        42: [370],
        43: [370],
        48: [192],
        50: [220],
        52: [180],
    }
    _RIGHTS_WITH_ABILITY: set[int] = set()
    for _rights_list in _ABILITY_TO_RIGHTS.values():
        _RIGHTS_WITH_ABILITY.update(_rights_list)

    @staticmethod
    def _has_right(vehicle: Vehicle, right: int | None) -> bool:
        """Check if a vehicle has the given right+ability permission."""
        if right is None:
            return True
        # Check user rights
        user_rights = {
            r.value if hasattr(r, "value") else int(r) for r in vehicle.rights
        }
        if right not in user_rights:
            return False
        # If this right requires a hardware ability, check abilities too
        if right in HomeAssistantMqttService._RIGHTS_WITH_ABILITY:
            hw_rights: set[int] = set()
            for a in vehicle.abilities:
                a_val = a.value if hasattr(a, "value") else int(a)
                mapped = HomeAssistantMqttService._ABILITY_TO_RIGHTS.get(a_val, [])
                hw_rights.update(mapped)
            if right not in hw_rights:
                return False
        return True

    def _build_state_payload(self, status: VehicleStatus) -> dict:
        """Build a comprehensive JSON payload from all VehicleStatus fields."""
        data: dict[str, Any] = {}

        def _enum_val(v):
            """Safely extract .value from an enum, or return the raw value."""
            if v is None:
                return None
            return v.value if hasattr(v, "value") else v

        # Battery
        if status.battery:
            b = status.battery
            data["battery_soc"] = b.soc
            data["battery_voltage"] = b.battery_voltage
            data["battery_current"] = b.battery_current
            data["battery_expected_mileage"] = b.expected_mileage
            data["battery_dump_energy"] = b.dump_energy
            data["battery_dump_energy_kwh"] = b.dump_energy_kwh
            data["battery_power_kw"] = b.battery_power
            data["battery_charging_power_kw"] = b.charging_power_kw
            data["battery_discharging_power_kw"] = b.discharging_power_kw
            data["battery_charge_state"] = _enum_val(b.charge_state)
            data["battery_charge_remain_time"] = b.charge_remain_time
            data["battery_charge_soc_setting"] = b.charge_plan.soc_setting
            data["battery_charge_time_setting"] = b.charge_plan.time_setting
            data["battery_dc_input_fast_charge"] = b.dc_input_fast_charge
            data["battery_ac_input_slow_charge"] = b.ac_input_slow_charge
            data["battery_is_charging"] = b.is_charging
            data["battery_is_discharging"] = b.is_discharging
            data["battery_precise_soc"] = b.precise_soc
            data["battery_min_temp"] = b.min_battery_temp
            data["battery_healthy_charge_enabled"] = b.healthy_charge_enabled
            data["battery_charge_completed"] = b.charge_completed
            # Charge plan
            cp = b.charge_plan
            data["charge_plan_enabled"] = cp.enabled
            data["charge_plan_start"] = cp.start
            data["charge_plan_end"] = cp.end
            data["charge_plan_cycles"] = cp.cycles
            data["charge_plan_circulation"] = cp.circulation
            data["charge_plan_recharge"] = cp.recharge

        # Driving
        if status.driving:
            d = status.driving
            data["speed"] = d.speed
            data["total_mileage"] = d.total_mileage
            data["gear_status"] = _enum_val(d.gear_status)
            data["vehicle_state"] = d.vehicle_state
            data["speed_limit"] = d.speed_limit
            data["speed_limit_active"] = d.speed_limit_active
            data["parking_brake_state"] = d.parking_brake_state
            data["live_remaining_range"] = d.live_remaining_range

        # Location
        if status.location:
            data["latitude"] = status.location.latitude
            data["longitude"] = status.location.longitude

        # Climate
        if status.climate:
            c = status.climate
            data["outdoor_temp"] = c.outdoor_temp
            data["ac_switch"] = c.ac_switch
            data["ac_setting"] = c.ac_setting
            data["ac_air_volume"] = c.ac_air_volume
            data["ac_air_volume_setting"] = c.ac_air_volume_setting
            data["ac_wind_direction"] = c.ac_wind_direction
            data["ac_temp_mode"] = c.ac_temp_mode
            data["ac_circle_mode"] = c.ac_circle_mode
            data["ac_cooling_and_heating"] = _enum_val(c.ac_cooling_and_heating)
            data["min_single_temp"] = c.min_single_temp
            data["ptc_state"] = c.ptc_state
            data["ptc_power_setting_value"] = c.ptc_power_setting_value
            data["interior_temp"] = c.interior_temp
            data["recirculation_mode"] = _enum_val(c.recirculation_mode)
            data["windshield_defrost"] = _enum_val(c.windshield_defrost)
            data["rear_window_heating"] = c.rear_window_heating
            data["climate_mode"] = _enum_val(c.climate_mode)
            data["ac_operate_mode"] = _enum_val(c.ac_operate_mode)

        # Doors
        if status.doors:
            dr = status.doors
            data["driver_door_lock_status"] = dr.driver_door_lock_status
            data["lbcm_driver_door_status"] = dr.lbcm_driver_door_status
            data["rbcm_driver_door_status"] = dr.rbcm_driver_door_status
            data["lbcm_left_rear_door_status"] = dr.lbcm_left_rear_door_status
            data["rbcm_right_rear_door_status"] = dr.rbcm_right_rear_door_status
            data["bbcm_back_door_status"] = dr.bbcm_back_door_status
            data["bcm_door_ctrl_allow"] = dr.bcm_door_ctrl_allow

        # Windows
        if status.windows:
            w = status.windows
            data["left_front_window_percent"] = w.left_front_window_percent
            data["right_front_window_percent"] = w.right_front_window_percent
            data["left_rear_window_percent"] = w.left_rear_window_percent
            data["right_rear_window_percent"] = w.right_rear_window_percent
            data["driver_window_status"] = w.driver_window_status
            data["right_front_window_status"] = w.right_front_window_status
            data["left_rear_window_status"] = w.left_rear_window_status
            data["right_rear_window_status"] = w.right_rear_window_status
            data["sun_shade"] = w.sun_shade

        # Tires (kPa + bar)
        if status.tires:
            t = status.tires
            data["tire_front_left_kpa"] = t.front_left_kpa
            data["tire_front_right_kpa"] = t.front_right_kpa
            data["tire_rear_left_kpa"] = t.rear_left_kpa
            data["tire_rear_right_kpa"] = t.rear_right_kpa
            data["tire_front_left_bar"] = t.front_left_bar
            data["tire_front_right_bar"] = t.front_right_bar
            data["tire_rear_left_bar"] = t.rear_left_bar
            data["tire_rear_right_bar"] = t.rear_right_bar
            data["tire_front_left_state"] = t.front_left_state
            data["tire_front_right_state"] = t.front_right_state
            data["tire_rear_left_state"] = t.rear_left_state
            data["tire_rear_right_state"] = t.rear_right_state
            data["tires_all_ok"] = t.all_ok

        # Connectivity
        if status.connectivity:
            cn = status.connectivity
            data["bluetooth_state"] = cn.bluetooth_state
            data["bluetooth_addr"] = cn.bluetooth_addr
            data["hotspot_state"] = cn.hotspot_state

        # Ignition
        if status.ignition:
            data["ignition_on1"] = status.ignition.bcm_key_position_on1
            data["ignition_on2"] = status.ignition.bcm_key_position_on2
            data["ignition_on3"] = status.ignition.bcm_key_position_on3

        # Seat comfort
        if status.seat_comfort:
            sc = status.seat_comfort
            data["driver_seat_heating"] = sc.driver_seat_heating
            data["driver_seat_ventilation"] = sc.driver_seat_ventilation
            data["passenger_seat_heating"] = sc.passenger_seat_heating
            data["passenger_seat_ventilation"] = sc.passenger_seat_ventilation
            data["steering_wheel_heating"] = sc.steering_wheel_heating
            data["steering_wheel_heater_minutes"] = sc.steering_wheel_heater_minutes

        # Security
        if status.security:
            sec = status.security
            data["vehicle_security_active"] = _enum_val(sec.vehicle_security_active)
            data["sentry_mode"] = sec.sentry_mode
            data["left_mirror_heating"] = sec.left_mirror_heating
            data["right_mirror_heating"] = sec.right_mirror_heating
            data["roof_opening"] = sec.roof_opening

        # Top-level convenience properties
        data["is_charging"] = status.is_charging
        data["is_regening"] = status.is_regening
        data["is_locked"] = status.is_locked
        data["is_parked"] = status.is_parked
        data["is_driving"] = status.is_driving
        data["is_plugged"] = status.is_plugged

        # Timestamps
        if status.collect_time:
            data["collect_time"] = status.collect_time.isoformat()
        if status.create_time:
            data["create_time"] = status.create_time.isoformat()

        return data

    async def _publish_sensors(
        self, prefix: str, status: VehicleStatus, current_zone: str | None = None
    ) -> None:
        """Publish individual sensor topics for HA entities."""
        _str = lambda v: str(v) if v is not None else ""  # noqa: E731
        _bool = lambda v: "ON" if v else "OFF"  # noqa: E731

        await self._publish(
            f"{prefix}/current_zone", current_zone or "Away", retain=True
        )

        # -- Numeric sensors --
        if status.battery:
            b = status.battery
            await self._publish(f"{prefix}/battery_soc", _str(b.soc), retain=True)
            await self._publish(
                f"{prefix}/range", _str(b.expected_mileage), retain=True
            )
            await self._publish(
                f"{prefix}/battery_voltage", _str(b.battery_voltage), retain=True
            )
            await self._publish(
                f"{prefix}/battery_current", _str(b.battery_current), retain=True
            )
            await self._publish(
                f"{prefix}/battery_power", _str(b.battery_power), retain=True
            )
            await self._publish(
                f"{prefix}/charging_power", _str(b.charging_power_kw), retain=True
            )
            await self._publish(
                f"{prefix}/discharging_power", _str(b.discharging_power_kw), retain=True
            )
            await self._publish(
                f"{prefix}/dump_energy_kwh", _str(b.dump_energy_kwh), retain=True
            )
            await self._publish(
                f"{prefix}/charge_remain_time", _str(b.charge_remain_time), retain=True
            )
            await self._publish(
                f"{prefix}/charge_soc_setting",
                _str(b.charge_plan.soc_setting),
                retain=True,
            )

        if status.driving:
            await self._publish(
                f"{prefix}/odometer", _str(status.driving.total_mileage), retain=True
            )
            await self._publish(
                f"{prefix}/speed", _str(status.driving.speed), retain=True
            )
            await self._publish(
                f"{prefix}/gear_status",
                _str(
                    status.driving.gear_status.value
                    if hasattr(status.driving.gear_status, "value")
                    else status.driving.gear_status
                )
                if status.driving.gear_status is not None
                else "",
                retain=True,
            )

        if status.climate:
            c = status.climate
            await self._publish(
                f"{prefix}/outdoor_temp", _str(c.outdoor_temp), retain=True
            )
            await self._publish(f"{prefix}/ac_setting", _str(c.ac_setting), retain=True)
            await self._publish(
                f"{prefix}/ac_air_volume", _str(c.ac_air_volume), retain=True
            )

        # Tires (bar)
        if status.tires:
            t = status.tires
            await self._publish(
                f"{prefix}/tire_fl_bar", _str(t.front_left_bar), retain=True
            )
            await self._publish(
                f"{prefix}/tire_fr_bar", _str(t.front_right_bar), retain=True
            )
            await self._publish(
                f"{prefix}/tire_rl_bar", _str(t.rear_left_bar), retain=True
            )
            await self._publish(
                f"{prefix}/tire_rr_bar", _str(t.rear_right_bar), retain=True
            )

        # Windows (percent)
        if status.windows:
            w = status.windows
            await self._publish(
                f"{prefix}/window_fl", _str(w.left_front_window_percent), retain=True
            )
            await self._publish(
                f"{prefix}/window_fr", _str(w.right_front_window_percent), retain=True
            )
            await self._publish(
                f"{prefix}/window_rl", _str(w.left_rear_window_percent), retain=True
            )
            await self._publish(
                f"{prefix}/window_rr", _str(w.right_rear_window_percent), retain=True
            )
            await self._publish(f"{prefix}/sun_shade", _str(w.sun_shade), retain=True)

        # -- Binary sensors --
        await self._publish(
            f"{prefix}/charging", _bool(status.is_charging), retain=True
        )
        await self._publish(
            f"{prefix}/regening", _bool(status.is_regening), retain=True
        )
        await self._publish(f"{prefix}/locked", _bool(status.is_locked), retain=True)
        await self._publish(f"{prefix}/parked", _bool(status.is_parked), retain=True)

        if status.battery:
            b = status.battery
            await self._publish(
                f"{prefix}/battery_charging",
                _bool(b.is_charging),
                retain=True,
            )
            await self._publish(
                f"{prefix}/battery_discharging",
                _bool(b.is_discharging),
                retain=True,
            )

        if status.climate:
            await self._publish(
                f"{prefix}/ac_switch", _bool(status.climate.ac_switch), retain=True
            )

        if status.doors:
            dr = status.doors
            await self._publish(
                f"{prefix}/door_driver_left",
                _bool(dr.lbcm_driver_door_status),
                retain=True,
            )
            await self._publish(
                f"{prefix}/door_driver_right",
                _bool(dr.rbcm_driver_door_status),
                retain=True,
            )
            await self._publish(
                f"{prefix}/door_rear_left",
                _bool(dr.lbcm_left_rear_door_status),
                retain=True,
            )
            await self._publish(
                f"{prefix}/door_rear_right",
                _bool(dr.rbcm_right_rear_door_status),
                retain=True,
            )
            await self._publish(
                f"{prefix}/door_trunk", _bool(dr.bbcm_back_door_status), retain=True
            )

        if status.ignition:
            await self._publish(
                f"{prefix}/ignition",
                _bool(status.ignition.bcm_key_position_on1),
                retain=True,
            )
            await self._publish(
                f"{prefix}/ignition_on3",
                _bool(status.ignition.bcm_key_position_on3),
                retain=True,
            )

        if status.connectivity:
            await self._publish(
                f"{prefix}/bluetooth",
                _bool(status.connectivity.bluetooth_state),
                retain=True,
            )
            await self._publish(
                f"{prefix}/hotspot",
                _bool(status.connectivity.hotspot_state),
                retain=True,
            )

        # -- Switch state topics --
        if status.security:
            await self._publish(
                f"{prefix}/sentry_mode",
                _bool(status.security.sentry_mode),
                retain=True,
            )
            await self._publish(
                f"{prefix}/rearview_mirror_heat",
                _bool(
                    status.security.left_mirror_heating
                    or status.security.right_mirror_heating
                ),
                retain=True,
            )

        if status.seat_comfort:
            await self._publish(
                f"{prefix}/steering_wheel_heat",
                _bool(status.seat_comfort.steering_wheel_heating),
                retain=True,
            )

        if status.battery:
            await self._publish(
                f"{prefix}/healthy_charging",
                _bool(status.battery.healthy_charge_enabled),
                retain=True,
            )

    async def _publish_discovery(
        self, vehicle: Vehicle, device_id: str, device_name: str
    ) -> None:
        """Publish Home Assistant MQTT discovery configs for all entities."""
        vin = vehicle.vin
        prefix = self._settings.topic_prefix
        disc_prefix = self._settings.discovery_prefix

        device_info = {
            "identifiers": [device_id],
            "name": device_name,
            "manufacturer": "Leapmotor",
            "model": vehicle.car_type or "Unknown",
            "sw_version": "LeapConnect",
        }
        if vehicle.year:
            device_info["hw_version"] = str(vehicle.year)

        # ── Sensors ────────────────────────────────────────────────────────
        sensors: list[dict[str, Any]] = [
            # Battery
            {
                "key": "battery_soc",
                "name": "Battery",
                "dc": "battery",
                "unit": "%",
                "icon": "mdi:battery",
            },
            {
                "key": "range",
                "name": "Range",
                "unit": "km",
                "icon": "mdi:map-marker-distance",
            },
            {
                "key": "battery_voltage",
                "name": "Battery Voltage",
                "dc": "voltage",
                "unit": "V",
                "icon": "mdi:flash",
            },
            {
                "key": "battery_current",
                "name": "Battery Current",
                "dc": "current",
                "unit": "A",
                "icon": "mdi:current-ac",
            },
            {
                "key": "battery_power",
                "name": "Battery Power",
                "dc": "power",
                "unit": "kW",
                "icon": "mdi:lightning-bolt",
            },
            {
                "key": "charging_power",
                "name": "Charging Power",
                "dc": "power",
                "unit": "kW",
                "icon": "mdi:ev-station",
            },
            {
                "key": "discharging_power",
                "name": "Discharging Power",
                "dc": "power",
                "unit": "kW",
                "icon": "mdi:battery-arrow-down",
            },
            {
                "key": "dump_energy_kwh",
                "name": "Available Energy",
                "dc": "energy",
                "unit": "kWh",
                "icon": "mdi:battery-heart",
            },
            {
                "key": "charge_remain_time",
                "name": "Charge Remaining Time",
                "dc": "duration",
                "unit": "min",
                "icon": "mdi:timer-outline",
            },
            # Driving
            {
                "key": "odometer",
                "name": "Odometer",
                "dc": "distance",
                "unit": "km",
                "icon": "mdi:counter",
            },
            {
                "key": "speed",
                "name": "Speed",
                "dc": "speed",
                "unit": "km/h",
                "icon": "mdi:speedometer",
            },
            {"key": "gear_status", "name": "Gear", "icon": "mdi:car-shift-pattern"},
            # Climate
            {
                "key": "outdoor_temp",
                "name": "Outdoor Temperature",
                "dc": "temperature",
                "unit": "°C",
                "icon": "mdi:thermometer",
            },
            {
                "key": "ac_setting",
                "name": "AC Set Temperature",
                "dc": "temperature",
                "unit": "°C",
                "icon": "mdi:air-conditioner",
            },
            {"key": "ac_air_volume", "name": "AC Fan Speed", "icon": "mdi:fan"},
            # Tires (bar)
            {
                "key": "tire_fl_bar",
                "name": "Tire FL Pressure",
                "dc": "pressure",
                "unit": "bar",
                "icon": "mdi:tire",
            },
            {
                "key": "tire_fr_bar",
                "name": "Tire FR Pressure",
                "dc": "pressure",
                "unit": "bar",
                "icon": "mdi:tire",
            },
            {
                "key": "tire_rl_bar",
                "name": "Tire RL Pressure",
                "dc": "pressure",
                "unit": "bar",
                "icon": "mdi:tire",
            },
            {
                "key": "tire_rr_bar",
                "name": "Tire RR Pressure",
                "dc": "pressure",
                "unit": "bar",
                "icon": "mdi:tire",
            },
            # Windows
            {
                "key": "window_fl",
                "name": "Window Front Left",
                "unit": "%",
                "icon": "mdi:car-door",
            },
            {
                "key": "window_fr",
                "name": "Window Front Right",
                "unit": "%",
                "icon": "mdi:car-door",
            },
            {
                "key": "window_rl",
                "name": "Window Rear Left",
                "unit": "%",
                "icon": "mdi:car-door",
            },
            {
                "key": "window_rr",
                "name": "Window Rear Right",
                "unit": "%",
                "icon": "mdi:car-door",
            },
            {
                "key": "sun_shade",
                "name": "Sunshade Position",
                "unit": "%",
                "icon": "mdi:blinds",
            },
            # Cloud statistics
            {
                "key": "cloud_consumption_rank",
                "name": "Consumption Rank",
                "unit": "%",
                "icon": "mdi:podium",
            },
            {
                "key": "cloud_consumption_kwh_100km",
                "name": "Consumption (cloud)",
                "dc": "energy",
                "unit": "kWh/100km",
                "icon": "mdi:leaf",
            },
            {
                "key": "cloud_weekly_total_ec",
                "name": "Weekly Energy Total",
                "dc": "energy",
                "unit": "kWh",
                "icon": "mdi:chart-bar",
            },
            {
                "key": "cloud_weekly_driver_ec",
                "name": "Weekly Energy Driving",
                "dc": "energy",
                "unit": "kWh",
                "icon": "mdi:car-electric",
            },
            {
                "key": "cloud_weekly_ac_ec",
                "name": "Weekly Energy A/C",
                "dc": "energy",
                "unit": "kWh",
                "icon": "mdi:air-conditioner",
            },
            {
                "key": "cloud_weekly_other_ec",
                "name": "Weekly Energy Other",
                "dc": "energy",
                "unit": "kWh",
                "icon": "mdi:flash",
            },
            {
                "key": "current_zone",
                "name": "Current Zone",
                "icon": "mdi:map-marker-radius",
            },
        ]

        for s in sensors:
            config: dict[str, Any] = {
                "name": s["name"],
                "unique_id": f"{device_id}_{s['key']}",
                "state_topic": f"{prefix}/{vin}/{s['key']}",
                "device": device_info,
                "icon": s.get("icon"),
            }
            if s.get("unit"):
                config["unit_of_measurement"] = s["unit"]
            if s.get("dc"):
                config["device_class"] = s["dc"]

            topic = f"{disc_prefix}/sensor/{device_id}/{s['key']}/config"
            await self._publish_config(topic, config)

        # ── Binary sensors ─────────────────────────────────────────────────
        binary_sensors: list[dict[str, Any]] = [
            # Vehicle state
            {
                "key": "charging",
                "name": "Charging",
                "dc": "battery_charging",
                "icon": "mdi:ev-station",
            },
            {"key": "regening", "name": "Regenerating", "icon": "mdi:battery-sync"},
            {"key": "locked", "name": "Locked", "dc": "lock", "icon": "mdi:lock"},
            {"key": "parked", "name": "Parked", "icon": "mdi:parking"},
            # Battery state
            {
                "key": "battery_charging",
                "name": "Battery Charging",
                "dc": "battery_charging",
                "icon": "mdi:battery-charging",
            },
            {
                "key": "battery_discharging",
                "name": "Battery Discharging",
                "icon": "mdi:battery-arrow-down",
            },
            # Climate
            {
                "key": "ac_switch",
                "name": "Air Conditioning",
                "icon": "mdi:air-conditioner",
            },
            # Doors
            {
                "key": "door_driver_left",
                "name": "Door Driver Left",
                "dc": "door",
                "icon": "mdi:car-door",
            },
            {
                "key": "door_driver_right",
                "name": "Door Driver Right",
                "dc": "door",
                "icon": "mdi:car-door",
            },
            {
                "key": "door_rear_left",
                "name": "Door Rear Left",
                "dc": "door",
                "icon": "mdi:car-door",
            },
            {
                "key": "door_rear_right",
                "name": "Door Rear Right",
                "dc": "door",
                "icon": "mdi:car-door",
            },
            {
                "key": "door_trunk",
                "name": "Trunk",
                "dc": "door",
                "icon": "mdi:car-back",
            },
            # Ignition
            {
                "key": "ignition",
                "name": "Ignition",
                "dc": "power",
                "icon": "mdi:key-variant",
            },
            {
                "key": "ignition_on3",
                "name": "Ignition Ready",
                "dc": "power",
                "icon": "mdi:car-key",
            },
            # Connectivity
            {
                "key": "bluetooth",
                "name": "Bluetooth",
                "dc": "connectivity",
                "icon": "mdi:bluetooth",
            },
            {
                "key": "hotspot",
                "name": "WiFi Hotspot",
                "dc": "connectivity",
                "icon": "mdi:wifi",
            },
        ]

        for bs in binary_sensors:
            config = {
                "name": bs["name"],
                "unique_id": f"{device_id}_{bs['key']}",
                "state_topic": f"{prefix}/{vin}/{bs['key']}",
                "payload_on": "ON",
                "payload_off": "OFF",
                "device": device_info,
                "icon": bs.get("icon"),
            }
            if bs.get("dc"):
                config["device_class"] = bs["dc"]

            topic = f"{disc_prefix}/binary_sensor/{device_id}/{bs['key']}/config"
            await self._publish_config(topic, config)

        # ── Device tracker (GPS) ───────────────────────────────────────────
        # No state_topic / value_template: a state_topic would override the
        # zone resolution Home Assistant derives from the GPS attributes, which
        # is what pinned the tracker to "home" regardless of the real position.
        # With only json_attributes_topic + source_type=gps, HA computes the
        # home/not_home/<zone> state from the published latitude/longitude.
        tracker_config = {
            "name": f"{device_name} Location",
            "unique_id": f"{device_id}_location",
            "json_attributes_topic": f"{prefix}/{vin}/location",
            "device": device_info,
            "icon": "mdi:car-connected",
            "source_type": "gps",
        }
        topic = f"{disc_prefix}/device_tracker/{device_id}/config"
        await self._publish_config(topic, tracker_config)

        # ── Image (dynamic car image) ──────────────────────────────────────
        image_config = {
            "name": f"{device_name} Image",
            "unique_id": f"{device_id}_image",
            "image_topic": f"{prefix}/{vin}/image",
            "device": device_info,
            "icon": "mdi:car",
            "content_type": "image/png",
        }
        topic = f"{disc_prefix}/image/{device_id}/image/config"
        await self._publish_config(topic, image_config)

        # Buttons (commands) — gated by vehicle rights/abilities
        commands = [
            # Remote controls
            {"key": "lock", "name": "Lock", "icon": "mdi:lock", "right": 110},
            {"key": "unlock", "name": "Unlock", "icon": "mdi:lock-open", "right": 110},
            {
                "key": "trunk_open",
                "name": "Open Trunk",
                "icon": "mdi:car-back",
                "right": 130,
            },
            {
                "key": "trunk_close",
                "name": "Close Trunk",
                "icon": "mdi:car-back",
                "right": 130,
            },
            {
                "key": "find",
                "name": "Find Vehicle",
                "icon": "mdi:car-search",
                "right": 120,
            },
            {
                "key": "windows_open",
                "name": "Open Windows",
                "icon": "mdi:car-door",
                "right": 230,
            },
            {
                "key": "windows_close",
                "name": "Close Windows",
                "icon": "mdi:car-door",
                "right": 230,
            },
            # Charging
            {
                "key": "charging_start",
                "name": "Start Charging",
                "icon": "mdi:ev-station",
                "right": 193,
            },
            {
                "key": "charging_stop",
                "name": "Stop Charging",
                "icon": "mdi:ev-station",
                "right": 193,
            },
            {
                "key": "battery_preheat",
                "name": "Battery Preheat",
                "icon": "mdi:heat-wave",
                "right": 190,
            },
            {
                "key": "battery_preheat_off",
                "name": "Battery Preheat Off",
                "icon": "mdi:heat-wave",
                "right": 190,
            },
            {
                "key": "unlock_charger",
                "name": "Unlock Charger",
                "icon": "mdi:ev-plug-type2",
                "right": 192,
            },
            # Comfort
            {
                "key": "sunroof_open",
                "name": "Open Sunroof",
                "icon": "mdi:car-select",
                "right": 160,
            },
            {
                "key": "sunroof_close",
                "name": "Close Sunroof",
                "icon": "mdi:car-select",
                "right": 160,
            },
            # Vehicle
            {"key": "on3_on", "name": "ON3 On", "icon": "mdi:power", "right": 410},
            {
                "key": "on3_off",
                "name": "ON3 Off",
                "icon": "mdi:power-off",
                "right": 410,
            },
            {
                "key": "ble_key_restart",
                "name": "BLE Key Restart",
                "icon": "mdi:key-variant",
                "right": 430,
            },
            {
                "key": "hotspot",
                "name": "Toggle Hotspot",
                "icon": "mdi:wifi",
                "right": 140,
            },
            {
                "key": "autopark",
                "name": "Autopark",
                "icon": "mdi:parking",
                "right": 150,
            },
            {
                "key": "defrost",
                "name": "Windshield Defrost",
                "icon": "mdi:car-defrost-front",
                "right": 170,
            },
        ]

        for cmd in commands:
            if not self._has_right(vehicle, cmd.get("right")):
                continue
            cmd_config = {
                "name": cmd["name"],
                "unique_id": f"{device_id}_cmd_{cmd['key']}",
                "command_topic": f"{prefix}/{vin}/command",
                "payload_press": cmd["key"],
                "device": device_info,
                "icon": cmd["icon"],
            }
            topic = f"{disc_prefix}/button/{device_id}/{cmd['key']}/config"
            await self._publish_config(topic, cmd_config)

        # ── Switch entities (on/off pairs) ─────────────────────────────
        switches = [
            {
                "key": "ac",
                "name": "Air Conditioning",
                "icon": "mdi:air-conditioner",
                "right": 170,
                "state_topic_key": "ac_switch",
            },
            {
                "key": "sentry_mode",
                "name": "Sentry Mode",
                "icon": "mdi:cctv",
                "right": 220,
                "state_topic_key": None,
            },
            {
                "key": "steering_wheel_heat",
                "name": "Steering Wheel Heat",
                "icon": "mdi:steering",
                "right": 320,
                "state_topic_key": None,
            },
            {
                "key": "fuel_heating",
                "name": "Fuel Heating",
                "icon": "mdi:fire",
                "right": 380,
                "state_topic_key": None,
            },
            {
                "key": "rearview_mirror_heat",
                "name": "Rearview Mirror Heat",
                "icon": "mdi:mirror",
                "right": 440,
                "state_topic_key": None,
            },
            {
                "key": "healthy_charging",
                "name": "Healthy Charging",
                "icon": "mdi:battery-heart-variant",
                "right": 480,
                "state_topic_key": None,
            },
        ]

        for sw in switches:
            if not self._has_right(vehicle, sw.get("right")):
                continue
            state_key = sw.get("state_topic_key") or sw["key"]
            sw_config = {
                "name": sw["name"],
                "unique_id": f"{device_id}_sw_{sw['key']}",
                "command_topic": f"{prefix}/{vin}/{sw['key']}/set",
                "state_topic": f"{prefix}/{vin}/{state_key}",
                "payload_on": "ON",
                "payload_off": "OFF",
                "device": device_info,
                "icon": sw["icon"],
            }
            topic = f"{disc_prefix}/switch/{device_id}/{sw['key']}/config"
            await self._publish_config(topic, sw_config)

        # ── Climate number entities ────────────────────────────────────
        if self._has_right(vehicle, 170):
            ac_temp_config = {
                "name": "AC Temperature",
                "unique_id": f"{device_id}_ac_temperature",
                "state_topic": f"{prefix}/{vin}/ac_setting",
                "command_topic": f"{prefix}/{vin}/ac_temperature/set",
                "unit_of_measurement": "°C",
                "min": 16,
                "max": 32,
                "step": 0.5,
                "mode": "slider",
                "device": device_info,
                "icon": "mdi:thermometer",
            }
            topic = f"{disc_prefix}/number/{device_id}/ac_temperature/config"
            await self._publish_config(topic, ac_temp_config)

        # ── Number entities ────────────────────────────────────────────
        if self._has_right(vehicle, 340):
            charge_limit_config = {
                "name": "Charge Limit",
                "unique_id": f"{device_id}_charge_limit",
                "state_topic": f"{prefix}/{vin}/charge_soc_setting",
                "command_topic": f"{prefix}/{vin}/charge_limit/set",
                "unit_of_measurement": "%",
                "min": 50,
                "max": 100,
                "step": 5,
                "mode": "slider",
                "device": device_info,
                "icon": "mdi:battery-lock",
            }
            topic = f"{disc_prefix}/number/{device_id}/charge_limit/config"
            await self._publish_config(topic, charge_limit_config)
        ha_poll_config = {
            "name": "Polling Interval",
            "unique_id": f"{device_id}_polling_interval",
            "state_topic": f"{prefix}/{vin}/polling_interval",
            "command_topic": f"{prefix}/{vin}/polling_interval/set",
            "unit_of_measurement": "s",
            "min": 10,
            "max": 3600,
            "step": 10,
            "mode": "slider",
            "device": device_info,
            "icon": "mdi:home-clock",
            "entity_category": "config",
        }
        topic = f"{disc_prefix}/number/{device_id}/polling_interval/config"
        await self._publish_config(topic, ha_poll_config)

        # Publish initial value for number entity
        await self._publish(
            f"{prefix}/{vin}/polling_interval",
            str(self._mqtt_interval_seconds),
            retain=True,
        )

        _LOGGER.info("MQTT discovery published for %s (%s)", device_name, vin)

    async def publish_scheduler_settings(
        self, vin: str, interval_minutes: int, mqtt_interval_seconds: int
    ) -> None:
        """Publish current scheduler intervals to MQTT state topics."""
        if not self._connected or not self._settings.enabled:
            return
        self._mqtt_interval_seconds = mqtt_interval_seconds
        prefix = f"{self._settings.topic_prefix}/{vin}"
        await self._publish(
            f"{prefix}/polling_interval", str(mqtt_interval_seconds), retain=True
        )

    async def publish_cloud_stats(self, vin: str, cloud_stats: dict[str, Any]) -> None:
        """Publish Leapmotor cloud statistics to MQTT sensor topics.

        Expected cloud_stats keys:
        - consumption_rank: str (e.g. "15%")
        - consumption_kwh_100km: float
        - weekly_total_ec: float (kWh total last week)
        - weekly_driver_ec: float (kWh driving)
        - weekly_ac_ec: float (kWh A/C)
        - weekly_other_ec: float (kWh other)
        """
        if not self._connected or not self._settings.enabled:
            return

        prefix = f"{self._settings.topic_prefix}/{vin}"
        _str = lambda v: str(v) if v is not None else ""  # noqa: E731

        for key, value in cloud_stats.items():
            if value is not None:
                await self._publish(f"{prefix}/cloud_{key}", _str(value), retain=True)

    async def _publish(
        self, topic: str, payload: str | bytes, *, retain: bool = False
    ) -> None:
        """Publish a message to the broker if connected."""
        if not (self._connected and self._client):
            return
        try:
            await self._client.publish(topic, payload, retain=retain)
        except aiomqtt.MqttError as exc:
            # Connection is dead. Flag it so we stop spamming failed publishes;
            # the message-iteration loop will raise too and trigger a reconnect.
            self._connected = False
            self._last_error = str(exc)
            _LOGGER.warning("MQTT publish failed (%s), will reconnect: %s", topic, exc)
        except Exception as exc:
            _LOGGER.warning("MQTT publish error for %s: %s", topic, exc)

    async def _publish_config(self, topic: str, config: dict[str, Any]) -> None:
        """Publish a retained HA discovery config wired to bridge availability.

        Adds the availability topic so HA shows the entity as unavailable when
        the bridge goes offline (Last Will) and live again once it reconnects.
        """
        config["availability_topic"] = self._availability_topic
        config["payload_available"] = "online"
        config["payload_not_available"] = "offline"
        await self._publish_config(topic, config)

    def _ensure_running(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._connection_loop(), name="mqtt-ha")

    def _request_stop(self) -> None:
        self._connected = False
        if self._task and not self._task.done():
            self._task.cancel()

    def _restart(self) -> None:
        """Stop and restart the connection."""
        self._discovery_sent.clear()
        # Cancel the current connection task (if any) and start a fresh one.
        # Cancellation unwinds the old aiomqtt client cleanly; the new task
        # connects independently. We do NOT reuse a shared stop flag, which
        # previously could stay set and silently kill all later reconnects.
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = asyncio.create_task(self._connection_loop(), name="mqtt-ha")

    async def _connection_loop(self) -> None:
        """Main connection loop with reconnection logic."""
        _LOGGER.info(
            "MQTT connecting to %s:%d", self._settings.broker, self._settings.port
        )
        try:
            await self._run_connection_loop()
        finally:
            self._connected = False
            self._client = None
            _LOGGER.info("MQTT disconnected")

    async def _run_connection_loop(self) -> None:
        while self._settings.enabled:
            try:
                tls_params = aiomqtt.TLSParameters() if self._settings.use_tls else None
                # Last Will: broker publishes "offline" on the availability
                # topic if we disconnect ungracefully, so HA marks the entities
                # unavailable instead of showing stale values forever.
                will = aiomqtt.Will(
                    topic=self._availability_topic,
                    payload="offline",
                    qos=1,
                    retain=True,
                )
                async with aiomqtt.Client(
                    hostname=self._settings.broker,
                    port=self._settings.port,
                    username=self._settings.username or None,
                    password=self._settings.password or None,
                    tls_params=tls_params,
                    keepalive=60,
                    will=will,
                ) as client:
                    self._client = client
                    self._connected = True
                    self._last_error = None
                    # Re-publish discovery on every (re)connect: retained
                    # configs may have been lost (broker/HA restart), so clear
                    # the cache and let the next poll recreate the entities.
                    self._discovery_sent.clear()
                    _LOGGER.info(
                        "MQTT connected to %s:%d",
                        self._settings.broker,
                        self._settings.port,
                    )

                    # Announce availability (clears the retained "offline" LWT)
                    await client.publish(
                        self._availability_topic, "online", qos=1, retain=True
                    )

                    # Subscribe to command topics and number set topics
                    await client.subscribe(f"{self._settings.topic_prefix}/+/command")
                    await client.subscribe(f"{self._settings.topic_prefix}/+/+/set")

                    # Process incoming messages until disconnect or cancellation
                    async for message in client.messages:
                        topic_str = str(message.topic)

                        # Handle command messages
                        if topic_str.endswith("/command"):
                            parts = topic_str.split("/")
                            if len(parts) >= 3:
                                vin = parts[-2]
                                cmd = (
                                    message.payload.decode() if message.payload else ""
                                )
                                _LOGGER.info(
                                    "MQTT command received: %s for %s", cmd, vin
                                )
                                if self._command_callback:
                                    spawn(self._handle_command_safe(vin, cmd))

                        # Handle number set messages (e.g. .../vin/polling_interval/set)
                        # and switch set messages (e.g. .../vin/ac/set)
                        elif topic_str.endswith("/set"):
                            parts = topic_str.split("/")
                            if len(parts) >= 4:
                                vin = parts[-3]
                                key = parts[-2]
                                payload_str = (
                                    message.payload.decode() if message.payload else ""
                                )

                                # Switch entities send ON/OFF
                                if payload_str in ("ON", "OFF"):
                                    cmd = (
                                        f"{key}_on"
                                        if payload_str == "ON"
                                        else f"{key}_off"
                                    )
                                    _LOGGER.info(
                                        "MQTT switch command: %s for %s", cmd, vin
                                    )
                                    if self._command_callback:
                                        spawn(self._handle_command_safe(vin, cmd))
                                # Number entities send numeric values
                                elif key in (
                                    "polling_interval",
                                    "charge_limit",
                                    "ac_temperature",
                                ):
                                    try:
                                        value = int(float(payload_str))
                                        _LOGGER.info(
                                            "MQTT setting change: %s = %d", key, value
                                        )
                                        if self._settings_callback:
                                            spawn(
                                                self._handle_settings_safe(key, value)
                                            )
                                    except (ValueError, TypeError):
                                        _LOGGER.warning(
                                            "MQTT invalid number value for %s: %s",
                                            key,
                                            message.payload,
                                        )

            except aiomqtt.MqttError as exc:
                self._connected = False
                self._client = None
                self._last_error = str(exc)
                _LOGGER.warning("MQTT connection error: %s", exc)
                if not self._settings.enabled:
                    break
                # Back off before reconnecting. A stop/restart cancels the task,
                # interrupting this sleep with CancelledError so we exit cleanly.
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._connected = False
                self._client = None
                self._last_error = str(exc)
                _LOGGER.exception("MQTT unexpected error")
                if not self._settings.enabled:
                    break
                await asyncio.sleep(30)

    # Command handling
    _command_callback = None
    _settings_callback = None

    def set_command_callback(self, callback) -> None:
        """Set callback for handling incoming commands from HA."""
        self._command_callback = callback

    def set_settings_callback(self, callback) -> None:
        """Set callback for handling interval changes from HA.

        Callback signature: async def cb(key: str, value: int) -> None
        key is 'polling_interval'.
        """
        self._settings_callback = callback

    async def _handle_command_safe(self, vin: str, command: str) -> None:
        """Execute command callback safely."""
        try:
            if self._command_callback:
                await self._command_callback(vin, command)
        except Exception as exc:
            _LOGGER.exception("MQTT command handler error: %s", exc)

    async def _handle_settings_safe(self, key: str, value: int) -> None:
        """Execute settings callback safely."""
        try:
            if self._settings_callback:
                await self._settings_callback(key, value)
        except Exception as exc:
            _LOGGER.exception("MQTT settings handler error: %s", exc)
