"""Local telemetry history routes: snapshots, daily summaries, events."""

from __future__ import annotations

from fastapi import APIRouter

from leapconnect.api.deps import get_repo_or_503
from leapconnect.api.schemas import (
    DailySummaryResponse,
    VehicleHistoryResponse,
    VehicleSnapshotSchema,
)

router = APIRouter()


@router.get("/api/vehicles/{vin}/history", response_model=VehicleHistoryResponse)
async def get_vehicle_history(
    vin: str,
    days: int = 30,
    from_date: str | None = None,
    to_date: str | None = None,
    max_points: int | None = None,
) -> VehicleHistoryResponse:
    """Get historical vehicle snapshots for a given time period."""
    repo = get_repo_or_503("History not available")
    snapshots = await repo.get_history(
        vin, days=days, from_date=from_date, to_date=to_date, max_points=max_points
    )
    return VehicleHistoryResponse(
        vin=vin,
        days=days,
        count=len(snapshots),
        snapshots=[
            VehicleSnapshotSchema(
                timestamp=s.timestamp.isoformat(),
                battery_soc=s.battery_soc,
                battery_current=s.battery_current,
                battery_voltage=s.battery_voltage,
                battery_charging_power_kw=s.battery_charging_power_kw,
                battery_discharge_power_kw=s.battery_discharge_power_kw,
                battery_is_charging=s.battery_is_charging,
                battery_is_discharging=s.battery_is_discharging,
                battery_dump_energy=s.battery_dump_energy,
                battery_expected_mileage=s.battery_expected_mileage,
                battery_charge_state=s.battery_charge_state,
                drive_is_parked=s.drive_is_parked,
                drive_speed=s.drive_speed,
                drive_total_mileage=s.drive_total_mileage,
                ignition_is_on1=s.ignition_is_on1,
                ignition_is_on2=s.ignition_is_on2,
                vehicle_is_charging=s.vehicle_is_charging,
                vehicle_is_plugged=s.vehicle_is_plugged,
                vehicle_is_regening=s.vehicle_is_regening,
                vehicle_is_parked=s.vehicle_is_parked,
                vehicle_is_locked=s.vehicle_is_locked,
                vehicle_latitude=s.vehicle_latitude,
                vehicle_longitude=s.vehicle_longitude,
                climate_outdoor_temp=s.climate_outdoor_temp,
                tire_front_left_pressure=s.tire_front_left_pressure,
                tire_front_right_pressure=s.tire_front_right_pressure,
                tire_rear_left_pressure=s.tire_rear_left_pressure,
                tire_rear_right_pressure=s.tire_rear_right_pressure,
            )
            for s in snapshots
        ],
    )


@router.get("/api/vehicles/{vin}/history/daily", response_model=DailySummaryResponse)
async def get_vehicle_daily_summary(vin: str, days: int = 30) -> DailySummaryResponse:
    """Get aggregated daily summaries for charts and statistics."""
    repo = get_repo_or_503("History not available")
    summaries = await repo.get_daily_summary(vin, days=days)
    return DailySummaryResponse(
        vin=vin,
        days=days,
        count=len(summaries),
        daily=summaries,
    )


@router.get("/api/vehicles/{vin}/events")
async def get_vehicle_events(vin: str, days: int = 30, event_type: str | None = None):
    """Get state-transition events for analytics and duration tracking."""
    repo = get_repo_or_503("History not available")
    events = await repo.get_events(vin, days=days, event_type=event_type)
    return {
        "vin": vin,
        "days": days,
        "count": len(events),
        "events": [
            {
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type,
                "field_name": e.field_name,
                "old_value": e.old_value,
                "new_value": e.new_value,
            }
            for e in events
        ],
    }
