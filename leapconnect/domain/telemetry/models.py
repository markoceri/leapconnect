"""Telemetry value objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class VehicleSnapshot:
    """A single point-in-time snapshot of vehicle telemetry."""

    vin: str
    timestamp: datetime

    # Battery
    battery_soc: int | None = None
    battery_current: float | None = None
    battery_voltage: float | None = None
    battery_charging_power_kw: float | None = None
    battery_discharge_power_kw: float | None = None
    battery_is_charging: bool | None = None
    battery_is_discharging: bool | None = None
    battery_dump_energy: float | None = None
    battery_expected_mileage: int | None = None
    battery_charge_state: int | None = None

    # Drive
    drive_is_parked: bool | None = None
    drive_speed: int | None = None
    drive_total_mileage: int | None = None

    # Ignition
    ignition_is_on1: bool | None = None
    ignition_is_on2: bool | None = None

    # Vehicle
    vehicle_is_charging: bool | None = None
    vehicle_is_plugged: bool | None = None
    vehicle_is_regening: bool | None = None
    vehicle_is_parked: bool | None = None
    vehicle_is_locked: bool | None = None
    vehicle_latitude: float | None = None
    vehicle_longitude: float | None = None

    # Climate
    climate_outdoor_temp: int | None = None

    # Tire
    tire_front_left_pressure: float | None = None
    tire_front_right_pressure: float | None = None
    tire_rear_left_pressure: float | None = None
    tire_rear_right_pressure: float | None = None


@dataclass(frozen=True, slots=True)
class VehicleEvent:
    """A single state-transition event detected for a vehicle."""

    vin: str
    timestamp: datetime
    event_type: str  # e.g. "regen_start", "regen_stop", "charge_start"
    field_name: str  # e.g. "is_regening", "battery_soc"
    old_value: str | None = None
    new_value: str | None = None
