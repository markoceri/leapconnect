"""Pydantic response schemas for the Leapmotor Dashboard API."""

from __future__ import annotations

from leapmotor_api.models import Message, Vehicle, VehicleStatus
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Vehicle
# ---------------------------------------------------------------------------


class VehicleSchema(BaseModel):
    vin: str
    car_type: str
    email: str | None = None
    plate_number: str | None = None
    car_id: str | None = None
    user_nickname: str | None = None
    vehicle_nickname: str | None = None
    mobile_number: str | None = None
    out_color: str | None = None
    is_shared: bool = False
    share_time: int | None = None
    expire_time: int | None = None
    duration_type: int | None = None
    seat_layout: str | None = None
    rudder: str | None = None
    year: int | None = None
    rights: str | None = None
    abilities: list[str] = []
    module_rights: str | None = None
    allocation_code: str | int | None = None
    raw: dict | None = None

    @classmethod
    def from_model(cls, v: Vehicle) -> VehicleSchema:
        return cls(
            vin=v.vin,
            car_type=v.car_type,
            email=v.email,
            plate_number=v.plate_number,
            car_id=v.car_id,
            user_nickname=v.user_nickname,
            vehicle_nickname=v.vehicle_nickname,
            mobile_number=v.mobile_number,
            out_color=v.out_color,
            is_shared=v.is_shared,
            share_time=v.share_time,
            expire_time=v.expire_time,
            duration_type=v.duration_type,
            seat_layout=v.seat_layout,
            rudder=v.rudder,
            year=v.year,
            rights=v.rights,
            abilities=v.abilities or [],
            module_rights=v.module_rights,
            allocation_code=v.allocation_code,
            raw=v.raw,
        )


# ---------------------------------------------------------------------------
# Vehicle Status (nested)
# ---------------------------------------------------------------------------


class BatterySchema(BaseModel):
    soc: int | None = None
    charge_state: int | None = None
    charge_state_label: str | None = None
    charge_remain_time: int | None = None
    charge_soc_setting: int | None = None
    charge_time_setting: str | None = None
    dc_input_fast_charge: int | None = None
    dump_energy: float | None = None
    battery_current: float | None = None
    battery_voltage: float | None = None
    expected_mileage: int | None = None
    # Computed properties
    dump_energy_kwh: float | None = None
    battery_power: float | None = None
    charging_power_kw: float | None = None
    discharging_power_kw: float | None = None
    is_charging: bool | None = None
    is_discharging: bool | None = None


class DrivingSchema(BaseModel):
    speed: int | None = None
    total_mileage: int | None = None
    gear_status: int | None = None
    is_parked: bool | None = None


class LocationSchema(BaseModel):
    latitude: float | None = None
    longitude: float | None = None


class ClimateSchema(BaseModel):
    ac_switch: bool | None = None
    ac_setting: float | None = None
    ac_air_volume: int | None = None
    ac_air_volume_setting: int | None = None
    ac_wind_direction: int | None = None
    ac_temp_mode: bool | None = None
    ac_circle_mode: bool | None = None
    ac_cooling_and_heating: int | None = None
    outdoor_temp: int | None = None
    min_single_temp: int | None = None
    ptc_state: int | None = None
    ptc_power_setting_value: int | None = None


class DoorSchema(BaseModel):
    driver_door_lock_status: bool | None = None
    lbcm_driver_door_status: bool | None = None
    rbcm_driver_door_status: bool | None = None
    lbcm_left_rear_door_status: bool | None = None
    rbcm_right_rear_door_status: bool | None = None
    bbcm_back_door_status: bool | None = None
    bcm_door_ctrl_allow: bool | None = None
    # Computed
    is_locked: bool | None = None


class WindowSchema(BaseModel):
    left_front_window_percent: int | None = None
    right_front_window_percent: int | None = None
    left_rear_window_percent: int | None = None
    right_rear_window_percent: int | None = None
    driver_window_status: bool | None = None
    right_front_window_status: bool | None = None
    left_rear_window_status: bool | None = None
    right_rear_window_status: bool | None = None
    sun_shade: int | None = None
    is_support_windows_remote_control: int | None = None


class TireSchema(BaseModel):
    front_left_kpa: int | None = None
    front_right_kpa: int | None = None
    rear_left_kpa: int | None = None
    rear_right_kpa: int | None = None
    front_left_state: int | None = None
    front_right_state: int | None = None
    rear_left_state: int | None = None
    rear_right_state: int | None = None
    # Computed (bar)
    front_left_bar: float | None = None
    front_right_bar: float | None = None
    rear_left_bar: float | None = None
    rear_right_bar: float | None = None
    all_ok: bool | None = None


class ConnectivitySchema(BaseModel):
    bluetooth_state: bool | None = None
    bluetooth_addr: str | None = None
    hotspot_state: bool | None = None


class IgnitionSchema(BaseModel):
    bcm_key_position_on1: bool | None = None
    bcm_key_position_on3: bool | None = None


class TimestampsSchema(BaseModel):
    collect_time: str | None = None
    create_time: str | None = None


class VehicleStatusSchema(BaseModel):
    battery: BatterySchema
    driving: DrivingSchema
    location: LocationSchema
    climate: ClimateSchema
    doors: DoorSchema
    windows: WindowSchema
    tires: TireSchema
    connectivity: ConnectivitySchema
    ignition: IgnitionSchema
    # Computed (top-level convenience)
    is_locked: bool | None = None
    is_charging: bool | None = None
    is_regening: bool | None = None
    is_parked: bool | None = None
    timestamps: TimestampsSchema
    raw: dict | None = None

    @classmethod
    def from_model(cls, status: VehicleStatus) -> VehicleStatusSchema:
        return cls(
            battery=BatterySchema(
                soc=status.battery.soc,
                charge_state=status.battery.charge_state.value
                if status.battery.charge_state
                else None,
                charge_state_label=status.battery.charge_state.name
                if status.battery.charge_state
                else None,
                charge_remain_time=status.battery.charge_remain_time,
                charge_soc_setting=status.battery.charge_soc_setting,
                charge_time_setting=status.battery.charge_time_setting,
                dc_input_fast_charge=status.battery.dc_input_fast_charge,
                dump_energy=status.battery.dump_energy,
                battery_current=status.battery.battery_current,
                battery_voltage=status.battery.battery_voltage,
                expected_mileage=status.battery.expected_mileage,
                dump_energy_kwh=status.battery.dump_energy_kwh,
                battery_power=status.battery.battery_power,
                charging_power_kw=status.battery.charging_power_kw,
                discharging_power_kw=status.battery.discharging_power_kw,
                is_charging=status.battery.is_charging,
                is_discharging=status.battery.is_discharging,
            ),
            driving=DrivingSchema(
                speed=status.driving.speed,
                total_mileage=status.driving.total_mileage,
                gear_status=status.driving.gear_status,
                is_parked=status.driving.is_parked,
            ),
            location=LocationSchema(
                latitude=status.location.latitude,
                longitude=status.location.longitude,
            ),
            climate=ClimateSchema(
                ac_switch=status.climate.ac_switch,
                ac_setting=status.climate.ac_setting,
                ac_air_volume=status.climate.ac_air_volume,
                ac_air_volume_setting=status.climate.ac_air_volume_setting,
                ac_wind_direction=status.climate.ac_wind_direction,
                ac_temp_mode=status.climate.ac_temp_mode,
                ac_circle_mode=status.climate.ac_circle_mode,
                ac_cooling_and_heating=status.climate.ac_cooling_and_heating,
                outdoor_temp=status.climate.outdoor_temp,
                min_single_temp=status.climate.min_single_temp,
                ptc_state=status.climate.ptc_state,
                ptc_power_setting_value=status.climate.ptc_power_setting_value,
            ),
            doors=DoorSchema(
                driver_door_lock_status=status.doors.driver_door_lock_status,
                lbcm_driver_door_status=status.doors.lbcm_driver_door_status,
                rbcm_driver_door_status=status.doors.rbcm_driver_door_status,
                lbcm_left_rear_door_status=status.doors.lbcm_left_rear_door_status,
                rbcm_right_rear_door_status=status.doors.rbcm_right_rear_door_status,
                bbcm_back_door_status=status.doors.bbcm_back_door_status,
                bcm_door_ctrl_allow=status.doors.bcm_door_ctrl_allow,
                is_locked=status.doors.is_locked,
            ),
            windows=WindowSchema(
                left_front_window_percent=status.windows.left_front_window_percent,
                right_front_window_percent=status.windows.right_front_window_percent,
                left_rear_window_percent=status.windows.left_rear_window_percent,
                right_rear_window_percent=status.windows.right_rear_window_percent,
                driver_window_status=status.windows.driver_window_status,
                right_front_window_status=status.windows.right_front_window_status,
                left_rear_window_status=status.windows.left_rear_window_status,
                right_rear_window_status=status.windows.right_rear_window_status,
                sun_shade=status.windows.sun_shade,
                is_support_windows_remote_control=status.windows.is_support_windows_remote_control,
            ),
            tires=TireSchema(
                front_left_kpa=status.tires.front_left_kpa,
                front_right_kpa=status.tires.front_right_kpa,
                rear_left_kpa=status.tires.rear_left_kpa,
                rear_right_kpa=status.tires.rear_right_kpa,
                front_left_state=status.tires.front_left_state,
                front_right_state=status.tires.front_right_state,
                rear_left_state=status.tires.rear_left_state,
                rear_right_state=status.tires.rear_right_state,
                front_left_bar=status.tires.front_left_bar,
                front_right_bar=status.tires.front_right_bar,
                rear_left_bar=status.tires.rear_left_bar,
                rear_right_bar=status.tires.rear_right_bar,
                all_ok=status.tires.all_ok,
            ),
            connectivity=ConnectivitySchema(
                bluetooth_state=status.connectivity.bluetooth_state,
                bluetooth_addr=status.connectivity.bluetooth_addr,
                hotspot_state=status.connectivity.hotspot_state,
            ),
            ignition=IgnitionSchema(
                bcm_key_position_on1=status.ignition.bcm_key_position_on1,
                bcm_key_position_on3=status.ignition.bcm_key_position_on3,
            ),
            is_locked=status.is_locked,
            is_charging=status.is_charging,
            is_regening=status.is_regening,
            is_parked=status.is_parked,
            timestamps=TimestampsSchema(
                collect_time=status.collect_time.isoformat()
                if status.collect_time
                else None,
                create_time=status.create_time.isoformat()
                if status.create_time
                else None,
            ),
            raw=status.raw,
        )


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


class MessageSchema(BaseModel):
    id: int
    vin: str | None = None
    title: str | None = None
    message: str | None = None
    send_time: str | None = None
    is_read: bool = False
    url: str | None = None
    msg_type: int | None = None

    @classmethod
    def from_model(cls, m: Message) -> MessageSchema:
        return cls(
            id=m.id,
            vin=m.vin,
            title=m.title,
            message=m.message,
            send_time=m.send_datetime.isoformat() if m.send_datetime else None,
            is_read=m.is_read,
            url=m.url,
            msg_type=m.msg_type,
        )


# ---------------------------------------------------------------------------
# API Response schemas
# ---------------------------------------------------------------------------


class StatusResponse(BaseModel):
    status: str = "ok"


class SetupStatusResponse(BaseModel):
    has_user: bool
    has_account: bool
    has_certificates: bool
    certificates_valid: bool
    authenticated: bool = False
    connected: bool
    vehicles: list[VehicleSchema]


class CertificateUploadResponse(BaseModel):
    status: str = "ok"
    cert_path: str
    key_path: str


class CertificateStatusResponse(BaseModel):
    cert_exists: bool
    key_exists: bool


class AccountSetupResponse(BaseModel):
    status: str = "ok"
    connected: bool
    vehicles: list[VehicleSchema] = []
    connection_error: str | None = None


class ReconnectResponse(BaseModel):
    status: str = "ok"
    connected: bool
    vehicles: list[VehicleSchema]


class LoginResponse(BaseModel):
    status: str = "ok"
    user_id: str | None = None
    vehicles: list[VehicleSchema]


class SetPinResponse(BaseModel):
    status: str = "ok"
    has_pin: bool


class ConnectionStatusResponse(BaseModel):
    connected: bool
    has_account: bool
    has_user: bool
    user_id: str | None = None
    leapmotor_email: str | None = None
    display_name: str | None = None
    vehicles: list[VehicleSchema]
    has_pin: bool


class UserCreateResponse(BaseModel):
    status: str = "ok"
    display_name: str


class AuthLoginResponse(BaseModel):
    status: str = "ok"
    display_name: str


class UserUpdateResponse(BaseModel):
    status: str = "ok"
    display_name: str


class UserInfoResponse(BaseModel):
    has_user: bool
    display_name: str | None = None


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


class SnapshotSchema(BaseModel):
    timestamp: str
    battery_soc: int | None = None
    expected_mileage: int | None = None
    total_mileage: int | None = None
    energy_kwh: float | None = None
    outdoor_temp: int | None = None
    is_charging: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    speed: int | None = None


class VehicleHistoryResponse(BaseModel):
    vin: str
    days: int
    count: int
    snapshots: list[SnapshotSchema]


class DailySummaryResponse(BaseModel):
    vin: str
    days: int
    count: int
    daily: list[dict]


class SchedulerStatusResponse(BaseModel):
    enabled: bool
    interval_minutes: int
    is_running: bool
    last_run: str | None = None
    last_error: str | None = None
    total_runs: int
    total_errors: int


class MessageListResponse(BaseModel):
    count: int
    page_no: int
    page_size: int
    messages: list[MessageSchema]


class UnreadCountResponse(BaseModel):
    unread: int
