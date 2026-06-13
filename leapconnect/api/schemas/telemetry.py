"""Vehicle status/history/live-refresh DTOs."""

from __future__ import annotations

from pydantic import BaseModel

from leapconnect.api.schemas.vehicle import VehicleSchema, VehicleStatusSchema


class VehicleListResponse(BaseModel):
    vehicles: list[VehicleSchema]


class VehicleStatusResponse(BaseModel):
    status: VehicleStatusSchema


class FullVehicleDataResponse(BaseModel):
    vehicle: VehicleSchema
    status: VehicleStatusSchema | None = None
    mileage: dict | None = None
    picture: dict | None = None
    errors: dict[str, str | None] = {}
    vehicle_raw: dict | None = None
    status_raw: dict | None = None
    cache_age_seconds: float | None = None


class VehicleSnapshotSchema(BaseModel):
    timestamp: str
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


class VehicleHistoryResponse(BaseModel):
    vin: str
    days: int
    count: int
    snapshots: list[VehicleSnapshotSchema]


class DailySummaryResponse(BaseModel):
    vin: str
    days: int
    count: int
    daily: list[dict]


class LiveRefreshStatusResponse(BaseModel):
    """Response for the live refresh status endpoint."""

    interval_seconds: int
    is_running: bool
