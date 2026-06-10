"""Pydantic response schemas for the Leapmotor Dashboard API."""

from __future__ import annotations

from datetime import datetime

from leapmotor_api.models import (
    ChargeRecord,
    ConsumptionLastWeekBreakdown,
    ConsumptionRank,
    ConsumptionWeeklyRank,
    Message,
    Vehicle,
    VehicleStatus,
    WeeklyConsumption,
)
from pydantic import BaseModel


def _enum_val(v):
    """Extract .value from an IntEnum/StrEnum, pass through None."""
    if v is None:
        return None
    return v.value if hasattr(v, "value") else v


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
            rights=",".join(str(r.value) for r in v.rights) if v.rights else None,
            abilities=[str(a.value) for a in v.abilities] if v.abilities else [],
            module_rights=",".join(str(m.value) for m in v.module_rights)
            if v.module_rights
            else None,
            allocation_code=v.allocation_code,
            raw=v.raw,
        )


# ---------------------------------------------------------------------------
# Vehicle Status (nested)
# ---------------------------------------------------------------------------


class ChargePlanSchema(BaseModel):
    soc_setting: int | None = None
    time_setting: str | None = None
    enabled: int | None = None
    start: str | None = None
    end: str | None = None
    cycles: str | None = None
    circulation: int | None = None
    recharge: int | None = None
    cancelled_once: int | None = None


class BatterySchema(BaseModel):
    soc: int | None = None
    precise_soc: float | None = None
    charge_state: int | None = None
    charge_state_label: str | None = None
    charge_remain_time: int | None = None
    charge_soc_setting: int | None = None
    charge_time_setting: str | None = None
    charge_completed: int | None = None
    dc_input_fast_charge: int | None = None
    ac_input_slow_charge: int | None = None
    dump_energy: float | None = None
    battery_current: float | None = None
    battery_voltage: float | None = None
    expected_mileage: int | None = None
    min_battery_temp: int | None = None
    battery_thermal_request: int | None = None
    healthy_charge_enabled: int | None = None
    charge_plan: ChargePlanSchema | None = None
    # Computed properties
    dump_energy_kwh: float | None = None
    battery_power: float | None = None
    charging_power_kw: float | None = None
    discharging_power_kw: float | None = None
    is_charging: bool | None = None
    is_discharging: bool | None = None
    is_charge_fast_gun_insert: bool | None = None
    is_charge_slow_gun_insert: bool | None = None


class DrivingSchema(BaseModel):
    speed: int | None = None
    total_mileage: int | None = None
    gear_status: int | None = None
    is_parked: bool | None = None
    vehicle_state: int | None = None
    speed_limit: int | None = None
    speed_limit_unit: int | None = None
    speed_limit_active: int | None = None
    live_remaining_range: int | None = None
    max_range: int | None = None
    range_mode: int | None = None
    parking_brake_state: int | None = None


class LocationSchema(BaseModel):
    latitude: float | None = None
    longitude: float | None = None


class ClimateSchema(BaseModel):
    ac_switch: bool | None = None
    ac_setting: float | None = None
    ac_setting_right: float | None = None
    interior_temp: float | None = None
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
    recirculation_mode: int | None = None
    windshield_defrost: int | None = None
    rear_window_heating: int | None = None
    climate_mode: int | None = None
    rapid_cooling: int | None = None
    rapid_heating: int | None = None
    ac_operate_mode: int | None = None
    is_windshield_defrost_active: bool | None = None


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


class SeatComfortSchema(BaseModel):
    driver_seat_heating: int | None = None
    driver_seat_ventilation: int | None = None
    passenger_seat_heating: int | None = None
    passenger_seat_ventilation: int | None = None
    steering_wheel_heating: int | None = None
    steering_wheel_heater_minutes: int | None = None


class SecuritySchema(BaseModel):
    vehicle_security_active: int | None = None
    sentry_mode: int | None = None
    left_mirror_heating: int | None = None
    right_mirror_heating: int | None = None
    roof_opening: int | None = None
    is_security_active: bool | None = None


class IgnitionSchema(BaseModel):
    bcm_key_position_on1: bool | None = None
    bcm_key_position_on2: bool | None = None
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
    seat_comfort: SeatComfortSchema
    security: SecuritySchema
    ignition: IgnitionSchema
    # Computed (top-level convenience)
    is_locked: bool | None = None
    is_charging: bool | None = None
    is_plugged: bool | None = None
    is_regening: bool | None = None
    is_parked: bool | None = None
    is_driving: bool | None = None
    timestamps: TimestampsSchema
    raw: dict | None = None

    @classmethod
    def from_model(cls, status: VehicleStatus) -> VehicleStatusSchema:
        b = status.battery
        cp = b.charge_plan
        d = status.driving
        c = status.climate
        sc = status.seat_comfort
        sec = status.security
        ign = status.ignition

        return cls(
            battery=BatterySchema(
                soc=b.soc,
                precise_soc=b.precise_soc,
                charge_state=_enum_val(b.charge_state),
                charge_state_label=b.charge_state.name
                if b.charge_state is not None
                else None,
                charge_remain_time=b.charge_remain_time,
                charge_soc_setting=cp.soc_setting,
                charge_time_setting=cp.time_setting,
                charge_completed=b.charge_completed,
                dc_input_fast_charge=b.dc_input_fast_charge,
                ac_input_slow_charge=b.ac_input_slow_charge,
                dump_energy=b.dump_energy,
                battery_current=b.battery_current,
                battery_voltage=b.battery_voltage,
                expected_mileage=b.expected_mileage,
                min_battery_temp=b.min_battery_temp,
                battery_thermal_request=b.battery_thermal_request,
                healthy_charge_enabled=b.healthy_charge_enabled,
                charge_plan=ChargePlanSchema(
                    soc_setting=cp.soc_setting,
                    time_setting=cp.time_setting,
                    enabled=cp.enabled,
                    start=cp.start,
                    end=cp.end,
                    cycles=cp.cycles,
                    circulation=cp.circulation,
                    recharge=cp.recharge,
                    cancelled_once=cp.cancelled_once,
                ),
                dump_energy_kwh=b.dump_energy_kwh,
                battery_power=b.battery_power,
                charging_power_kw=b.charging_power_kw,
                discharging_power_kw=b.discharging_power_kw,
                is_charging=b.is_charging,
                is_discharging=b.is_discharging,
                is_charge_fast_gun_insert=b.is_charge_fast_gun_insert,
                is_charge_slow_gun_insert=b.is_charge_slow_gun_insert,
            ),
            driving=DrivingSchema(
                speed=d.speed,
                total_mileage=d.total_mileage,
                gear_status=_enum_val(d.gear_status),
                is_parked=d.is_parked,
                vehicle_state=d.vehicle_state,
                speed_limit=d.speed_limit,
                speed_limit_unit=d.speed_limit_unit,
                speed_limit_active=d.speed_limit_active,
                live_remaining_range=d.live_remaining_range,
                max_range=d.max_range,
                range_mode=d.range_mode,
                parking_brake_state=d.parking_brake_state,
            ),
            location=LocationSchema(
                latitude=status.location.latitude,
                longitude=status.location.longitude,
            ),
            climate=ClimateSchema(
                ac_switch=c.ac_switch,
                ac_setting=c.ac_setting,
                ac_setting_right=c.ac_setting_right,
                interior_temp=c.interior_temp,
                ac_air_volume=c.ac_air_volume,
                ac_air_volume_setting=c.ac_air_volume_setting,
                ac_wind_direction=c.ac_wind_direction,
                ac_temp_mode=c.ac_temp_mode,
                ac_circle_mode=c.ac_circle_mode,
                ac_cooling_and_heating=_enum_val(c.ac_cooling_and_heating),
                outdoor_temp=c.outdoor_temp,
                min_single_temp=c.min_single_temp,
                ptc_state=c.ptc_state,
                ptc_power_setting_value=c.ptc_power_setting_value,
                recirculation_mode=_enum_val(c.recirculation_mode),
                windshield_defrost=_enum_val(c.windshield_defrost),
                rear_window_heating=c.rear_window_heating,
                climate_mode=_enum_val(c.climate_mode),
                rapid_cooling=c.rapid_cooling,
                rapid_heating=c.rapid_heating,
                ac_operate_mode=_enum_val(c.ac_operate_mode),
                is_windshield_defrost_active=c.is_windshield_defrost_active,
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
            seat_comfort=SeatComfortSchema(
                driver_seat_heating=sc.driver_seat_heating,
                driver_seat_ventilation=sc.driver_seat_ventilation,
                passenger_seat_heating=sc.passenger_seat_heating,
                passenger_seat_ventilation=sc.passenger_seat_ventilation,
                steering_wheel_heating=sc.steering_wheel_heating,
                steering_wheel_heater_minutes=sc.steering_wheel_heater_minutes,
            ),
            security=SecuritySchema(
                vehicle_security_active=_enum_val(sec.vehicle_security_active),
                sentry_mode=sec.sentry_mode,
                left_mirror_heating=sec.left_mirror_heating,
                right_mirror_heating=sec.right_mirror_heating,
                roof_opening=sec.roof_opening,
                is_security_active=sec.is_security_active,
            ),
            ignition=IgnitionSchema(
                bcm_key_position_on1=ign.bcm_key_position_on1,
                bcm_key_position_on2=ign.bcm_key_position_on2,
                bcm_key_position_on3=ign.bcm_key_position_on3,
            ),
            is_locked=status.is_locked,
            is_charging=status.is_charging,
            is_plugged=status.is_plugged,
            is_regening=status.is_regening,
            is_parked=status.is_parked,
            is_driving=status.is_driving,
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
    certs_found_on_disk: bool = False
    authenticated: bool = False
    connected: bool
    vehicles: list[VehicleSchema]
    display_name: str | None = None


class CertificateUploadResponse(BaseModel):
    status: str = "ok"
    cert_path: str
    key_path: str


class CertificateStatusResponse(BaseModel):
    cert_exists: bool
    key_exists: bool


class CertificateFetchResponse(BaseModel):
    status: str = "ok"
    cert_path: str | None = None
    key_path: str | None = None
    source: str | None = None


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
    display_name: str | None = None


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
    app_version: str | None = None


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


class SchedulerStatusResponse(BaseModel):
    enabled: bool
    interval_minutes: int
    mqtt_interval_seconds: int
    rate_limit_seconds: int = 10
    transition_detection_enabled: bool = True
    transition_poll_interval_seconds: int = 10
    transition_min_event_interval_seconds: int = 10
    is_running: bool
    last_run: str | None = None
    last_error: str | None = None
    total_runs: int
    total_errors: int


class LiveRefreshStatusResponse(BaseModel):
    """Response for the live refresh status endpoint."""

    interval_seconds: int
    is_running: bool


class MessageListResponse(BaseModel):
    count: int
    page_no: int
    page_size: int
    messages: list[MessageSchema]


class UnreadCountResponse(BaseModel):
    unread: int


class PreferencesResponse(BaseModel):
    electricity_price_kwh: float = 0.25
    theme: str = "dark"
    downsampling_enabled: bool = True
    downsampling_max_points: int = 2000
    has_solar_panels: bool = False
    home_pricing_mode: str = "flat"


class MqttStatusResponse(BaseModel):
    enabled: bool = False
    connected: bool = False
    broker: str = ""
    port: int = 1883
    username: str = ""
    use_tls: bool = False
    discovery_prefix: str = "homeassistant"
    topic_prefix: str = "leapconnect"
    last_error: str | None = None


class MqttTestResponse(BaseModel):
    status: str
    message: str


class AbrpStatusResponse(BaseModel):
    enabled: bool = False
    user_token: str = ""
    is_running: bool = False
    last_error: str | None = None
    total_sends: int = 0
    total_errors: int = 0


# ---------------------------------------------------------------------------
# Charging History
# ---------------------------------------------------------------------------


class ChargeRecordSchema(BaseModel):
    start_ts: int
    end_ts: int
    charge_type: str
    energy_kwh: float
    latitude: str | None = None
    longitude: str | None = None
    timezone: str | None = None
    start_datetime: str | None = None
    end_datetime: str | None = None
    duration_seconds: int | None = None
    is_fast_charge: bool

    @classmethod
    def from_model(cls, r: ChargeRecord) -> ChargeRecordSchema:
        return cls(
            start_ts=r.start_ts,
            end_ts=r.end_ts,
            charge_type=str(r.charge_type.value) if r.charge_type else "1",
            energy_kwh=r.energy_kwh,
            latitude=r.latitude,
            longitude=r.longitude,
            timezone=r.timezone,
            start_datetime=r.start_datetime.isoformat() if r.start_datetime else None,
            end_datetime=r.end_datetime.isoformat() if r.end_datetime else None,
            duration_seconds=r.duration_seconds,
            is_fast_charge=r.is_fast_charge,
        )


class ChargingHistoryResponse(BaseModel):
    records: list[ChargeRecordSchema]
    total: int
    page_num: int
    page_size: int

    @classmethod
    def from_result(
        cls,
        records: list[ChargeRecord],
        page: int,
        size: int,
    ) -> ChargingHistoryResponse:
        items = [ChargeRecordSchema.from_model(r) for r in records]
        return cls(
            records=items,
            total=len(items),
            page_num=page,
            page_size=size,
        )


# ---------------------------------------------------------------------------
# Charging Price Tiers & Session Costs
# ---------------------------------------------------------------------------


class TimeBandScheduleEntry(BaseModel):
    days: list[int]  # 0=Mon, 6=Sun
    start_hour: int
    start_min: int = 0
    end_hour: int
    end_min: int = 0


class ChargingTimeBandResponse(BaseModel):
    id: int
    tier_id: str = "home_grid"
    name: str
    price_kwh: float
    schedule: list[TimeBandScheduleEntry]
    color: str | None = None
    position: int = 0


class ChargingTimeBandCreate(BaseModel):
    name: str
    price_kwh: float
    schedule: list[TimeBandScheduleEntry]
    color: str | None = None
    position: int | None = None


class ChargingTimeBandUpdate(BaseModel):
    name: str | None = None
    price_kwh: float | None = None
    schedule: list[TimeBandScheduleEntry] | None = None
    color: str | None = None
    position: int | None = None


class ChargingPriceTierResponse(BaseModel):
    id: str
    label: str
    price_kwh: float
    enabled: bool


class ChargingPriceTierUpdate(BaseModel):
    label: str | None = None
    price_kwh: float | None = None
    enabled: bool | None = None


class ChargingTiersFullResponse(BaseModel):
    tiers: list[ChargingPriceTierResponse]
    time_bands: list[ChargingTimeBandResponse]
    home_pricing_mode: str = "flat"


class ChargingSessionCostResponse(BaseModel):
    id: int
    vin: str
    start_ts: str
    end_ts: str | None = None
    tier_id: str
    tier_label: str | None = None
    time_band_id: int | None = None
    time_band_name: str | None = None
    energy_kwh: float | None = None
    peak_power_kw: float | None = None
    cost: float | None = None
    note: str | None = None


class ChargingSessionCostCreate(BaseModel):
    start_ts: str
    end_ts: str | None = None
    tier_id: str
    energy_kwh: float | None = None
    peak_power_kw: float | None = None
    note: str | None = None


class ChargingSessionCostUpdate(BaseModel):
    tier_id: str | None = None
    end_ts: str | None = None
    energy_kwh: float | None = None
    peak_power_kw: float | None = None
    note: str | None = None


# ---------------------------------------------------------------------------
# Consumption Statistics
# ---------------------------------------------------------------------------


class ConsumptionRankSchema(BaseModel):
    result: int
    rank: str
    hundred_km_ec: float
    hundred_mi_kwh_ec: float

    @classmethod
    def from_model(cls, r: ConsumptionRank) -> ConsumptionRankSchema:
        return cls(
            result=r.result,
            rank=r.rank,
            hundred_km_ec=r.hundred_km_ec,
            hundred_mi_kwh_ec=r.hundred_mi_kwh_ec,
        )


class WeeklyConsumptionSchema(BaseModel):
    week_start: str
    week_end: str
    hundred_km_ec: float
    hundred_mi_kwh_ec: float

    @classmethod
    def from_model(cls, w: WeeklyConsumption) -> WeeklyConsumptionSchema:
        return cls(
            week_start=w.week_start,
            week_end=w.week_end,
            hundred_km_ec=w.hundred_km_ec,
            hundred_mi_kwh_ec=w.hundred_mi_kwh_ec,
        )


class ConsumptionWeeklyRankResponse(BaseModel):
    rank: ConsumptionRankSchema | None = None
    weekly: list[WeeklyConsumptionSchema]

    @classmethod
    def from_model(cls, r: ConsumptionWeeklyRank) -> ConsumptionWeeklyRankResponse:
        return cls(
            rank=ConsumptionRankSchema.from_model(r.rank) if r.rank else None,
            weekly=[WeeklyConsumptionSchema.from_model(w) for w in r.weekly],
        )


class ConsumptionLastWeekResponse(BaseModel):
    driver_ec: float
    ac_ec: float
    other_ec: float
    total_ec: float

    @classmethod
    def from_model(cls, r: ConsumptionLastWeekBreakdown) -> ConsumptionLastWeekResponse:
        return cls(
            driver_ec=r.driver_ec,
            ac_ec=r.ac_ec,
            other_ec=r.other_ec,
            total_ec=r.total_ec,
        )


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class NotificationChannelConfig(BaseModel):
    """Channel-specific configuration (e.g. Telegram bot_token + chat_id)."""

    bot_token: str = ""
    chat_id: str = ""


class NotificationChannelCreate(BaseModel):
    channel_type: str = "telegram"
    config: dict = {}
    enabled: bool = True


class NotificationChannelUpdate(BaseModel):
    config: dict | None = None
    enabled: bool | None = None


class NotificationChannelResponse(BaseModel):
    id: int
    channel_type: str
    config: dict
    enabled: bool
    created_at: str | None = None


class NotificationPreferenceItem(BaseModel):
    event_type: str
    enabled: bool = True
    config: dict | None = None


class NotificationPreferencesUpdate(BaseModel):
    channel_id: int
    preferences: list[NotificationPreferenceItem]


class NotificationEventInfo(BaseModel):
    """Describes an available notification event type."""

    event_type: str
    label: str
    description: str
    category: str
    has_image: bool = False
    configurable: bool = False
    config_schema: dict | None = None


class NotificationEventStatus(BaseModel):
    """Current status of a notification event (enabled + config)."""

    event_type: str
    label: str
    description: str
    category: str
    has_image: bool = False
    configurable: bool = False
    config_schema: dict | None = None
    enabled: bool = False
    config: dict | None = None


class GeofenceCreate(BaseModel):
    vin: str | None = None
    name: str
    latitude: float
    longitude: float
    radius_m: float = 200.0
    notify_on_enter: bool = True
    notify_on_exit: bool = True
    enabled: bool = True


class GeofenceUpdate(BaseModel):
    name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_m: float | None = None
    notify_on_enter: bool | None = None
    notify_on_exit: bool | None = None
    enabled: bool | None = None


class GeofenceResponse(BaseModel):
    id: int
    vin: str | None = None
    name: str
    latitude: float
    longitude: float
    radius_m: float
    notify_on_enter: bool
    notify_on_exit: bool
    enabled: bool


# ---------------------------------------------------------------------------
# Telegram Users
# ---------------------------------------------------------------------------


class TelegramUserResponse(BaseModel):
    id: int | None = None
    chat_id: str
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    status: str
    created_at: str | None = None
    approved_at: str | None = None


class TelegramLinkTokenResponse(BaseModel):
    token: str
    link: str
    expires_at: str


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------


class MaintenancePlanItemResponse(BaseModel):
    id: int
    vin: str = ""
    service_type: str
    label: str
    category: str
    interval_km: int | None = None
    interval_months: int | None = None
    trigger_mode: str = "or"
    priority: str = "routine"
    last_done_km: int | None = None
    last_done_date: datetime | None = None
    enabled: bool = True
    notes: str | None = None
    source: str = "catalog"
    source_ref: str | None = None


class MaintenancePlanItemUpdate(BaseModel):
    enabled: bool | None = None
    interval_km: int | None = None
    interval_months: int | None = None
    trigger_mode: str | None = None
    priority: str | None = None
    last_done_km: int | None = None
    last_done_date: datetime | None = None
    notes: str | None = None


class MaintenanceRecordResponse(BaseModel):
    id: int
    vin: str = ""
    service_type: str
    label: str
    timestamp: datetime | None = None
    mileage_km: int | None = None
    cost: float | None = None
    provider: str | None = None
    notes: str | None = None


class MaintenanceRecordCreate(BaseModel):
    service_type: str
    label: str = ""
    timestamp: datetime | None = None
    mileage_km: int | None = None
    cost: float | None = None
    provider: str | None = None
    notes: str | None = None
    # If True, update the corresponding plan item's last_done fields
    update_plan_item: bool = True


class MaintenanceRecordUpdate(BaseModel):
    timestamp: datetime | None = None
    mileage_km: int | None = None
    cost: float | None = None
    provider: str | None = None
    notes: str | None = None


class MaintenanceAlertResponse(BaseModel):
    plan_item_id: int
    service_type: str
    label: str
    category: str
    priority: str
    status: str  # "ok" | "due_soon" | "overdue"
    due_km: int | None = None
    due_date: datetime | None = None
    current_km: int | None = None
    remaining_km: int | None = None
    remaining_days: int | None = None


class MaintenanceCostByCategory(BaseModel):
    category: str
    total: float = 0.0


class MaintenanceCostSummary(BaseModel):
    total: float = 0.0  # all-time sum of logged service costs
    this_year: float = 0.0
    services_count: int = 0  # number of records with a recorded cost
    avg: float = 0.0  # average cost per costed service
    by_category: list[MaintenanceCostByCategory] = []


class MaintenanceOverviewResponse(BaseModel):
    model_key: str
    display_name: str
    variant: str | None = None
    current_km: int | None = None
    total_items: int = 0
    upcoming_count: int = 0
    overdue_count: int = 0
    critical_count: int = 0
    next_item: MaintenancePlanItemResponse | None = None
    # Overdue + due-soon items, urgency-sorted (Overview shortlist).
    due_soon: list[MaintenanceAlertResponse] = []
    costs: MaintenanceCostSummary = MaintenanceCostSummary()
    plan: list[MaintenancePlanItemResponse] = []
    recent_records: list[MaintenanceRecordResponse] = []


# ---------------------------------------------------------------------------
# Maintenance — Library, repos & packs
# ---------------------------------------------------------------------------


class MaintenanceServiceItem(BaseModel):
    """A maintenance service item definition (catalog/pack/local)."""

    service_type: str
    label: str
    category: str = "other"
    interval_km: int | None = None
    interval_months: int | None = None
    trigger_mode: str = "or"
    priority: str = "routine"
    notes: str | None = None


class MaintenanceLibraryItem(MaintenanceServiceItem):
    """A library item with its origin and whether it's already in the plan."""

    origin: str  # "catalog" | "repo" | "local"
    origin_ref: str | None = None  # repo/pack slug for repo items
    in_plan: bool = False


class MaintenancePackResponse(BaseModel):
    id: int | None = None
    repo_id: int | None = None
    slug: str
    name: str
    author: str | None = None
    version: int | None = None
    description: str | None = None
    model_compat: list[str] | None = None
    items: list[MaintenanceLibraryItem] = []
    applies: bool = True  # matches this vehicle's model


class MaintenanceRepoResponse(BaseModel):
    id: int
    type: str
    url: str
    name: str | None = None
    author: str | None = None
    description: str | None = None
    branch: str | None = None
    added_at: datetime | None = None
    last_fetched_at: datetime | None = None
    status: str = "ok"
    pack_count: int = 0
    is_official: bool = False


class MaintenanceRepoCreate(BaseModel):
    url: str


class MaintenanceLibraryResponse(BaseModel):
    model_key: str
    display_name: str
    variant: str | None = None
    catalog: list[MaintenanceLibraryItem] = []
    local: list[MaintenanceLibraryItem] = []
    repos: list[MaintenanceRepoResponse] = []
    packs: list[MaintenancePackResponse] = []


class MaintenancePlanImportItem(MaintenanceServiceItem):
    # Optional per-item conflict resolution; falls back to request default.
    conflict: str | None = None  # "update" | "variant" | "skip"


class MaintenancePlanImportRequest(BaseModel):
    items: list[MaintenancePlanImportItem]
    source: str = "repo"  # "repo" | "local"
    source_ref: str | None = None
    on_conflict: str = "update"  # "update" | "variant" | "skip"


class MaintenancePlanImportResult(BaseModel):
    imported: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []
    variants: list[str] = []


class MaintenanceCustomItemCreate(MaintenanceServiceItem):
    last_done_km: int | None = None
    last_done_date: datetime | None = None


class MaintenancePackImportRequest(BaseModel):
    # One of: (repo_id + slug) | url | inline
    repo_id: int | None = None
    slug: str | None = None
    url: str | None = None
    inline: dict | None = None
