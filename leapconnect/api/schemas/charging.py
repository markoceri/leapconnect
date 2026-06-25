"""Charging history, price tiers, time bands, session costs, consumption DTOs."""

from __future__ import annotations

from leapmotor_api.models import (
    ChargeRecord,
    ConsumptionLastWeekBreakdown,
    ConsumptionRank,
    ConsumptionWeeklyRank,
    WeeklyConsumption,
)
from pydantic import BaseModel


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
    zone_name: str | None = None


class ChargingSessionCostCreate(BaseModel):
    start_ts: str
    end_ts: str | None = None
    tier_id: str
    energy_kwh: float | None = None
    peak_power_kw: float | None = None
    note: str | None = None
    zone_name: str | None = None


class ChargingSessionCostUpdate(BaseModel):
    tier_id: str | None = None
    end_ts: str | None = None
    energy_kwh: float | None = None
    peak_power_kw: float | None = None
    note: str | None = None
    zone_name: str | None = None


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
