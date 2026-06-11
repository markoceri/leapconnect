"""Vehicle and vehicle-status DTOs (mapped from leapmotor_api models)."""

from __future__ import annotations

from leapmotor_api.models import (
    Vehicle,
    VehicleStatus,
)
from pydantic import BaseModel

from leapconnect.api.schemas._utils import _enum_val


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
