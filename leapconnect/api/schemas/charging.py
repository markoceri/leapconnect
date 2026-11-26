"""Charging history, price tiers, time bands, session costs, consumption DTOs."""

from __future__ import annotations

from datetime import date
from typing import Literal

from leapmotor_api.models import (
    ChargeRecord,
    ConsumptionBreakdown,
    ConsumptionRank,
    ConsumptionWeeklyRank,
    MileageEnergyHistory,
    WeeklyConsumption,
)
from pydantic import BaseModel, Field, model_validator


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


class _ChargingSessionExtraFields(BaseModel):
    """An extra cost of a session; see ``domain.charging.extras``."""

    kind: Literal["fixed", "time", "per_kwh", "percent"]
    label: str = Field(default="", max_length=64)
    included: bool = True  # counted in the session cost
    amount: float | None = None  # fixed: € (negative for a discount)
    # time: €/time_unit; per_kwh: €/kWh; percent: % of the energy cost
    rate: float | None = Field(default=None, ge=0)
    time_unit: Literal["minute", "hour"] = "hour"
    billing: Literal["exact", "started"] = "exact"
    start_ref: Literal["charge_start", "charge_end"] = "charge_end"
    start_offset_min: int = Field(default=0, ge=0)
    end_ref: Literal["charge_end", "unplug", "departure", "manual"] = "unplug"
    duration_min: int | None = Field(default=None, ge=0)  # end_ref "manual"
    cap: float | None = Field(default=None, ge=0)


class ChargingSessionExtraIn(_ChargingSessionExtraFields):
    @model_validator(mode="after")
    def _check_kind(self):
        if self.kind == "fixed" and self.amount is None:
            raise ValueError("a fixed extra needs an amount")
        if self.kind != "fixed" and self.rate is None:
            raise ValueError(f"a {self.kind} extra needs a rate")
        if (
            self.kind == "time"
            and self.end_ref == "manual"
            and self.duration_min is None
        ):
            raise ValueError("a time extra with a manual end needs a duration")
        return self


class ChargingSessionExtraResponse(_ChargingSessionExtraFields):
    id: int | None = None
    source: str | None = None  # provider it comes from; None = the user's
    minutes: int | None = None  # billable minutes (time-based)
    cost: float | None = None  # None = can't be computed yet


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
    cost: float | None = None  # energy cost
    cost_manual: bool = False  # entered by hand, kept by recalculations
    energy_manual: bool = False
    manual_price_kwh: float | None = None  # cost = energy × this price
    # Imported from a charging provider: energy and cost are the billed ones
    external_source: str | None = None
    external_id: str | None = None
    provider_account_id: int | None = None
    evse_id: str | None = None  # the charging point (see /api/charging/stations)
    latitude: float | None = None  # where the car charged
    longitude: float | None = None
    auto_link_disabled: bool = False
    extras: list[ChargingSessionExtraResponse] = []
    extras_total: float | None = None  # extras counted in the session cost
    total_cost: float | None = None  # energy cost + extras_total
    note: str | None = None
    zone_name: str | None = None


class ChargingSessionRowSchema(BaseModel):
    """One row of a period's session list (detected and/or stored)."""

    id: int | None = None  # stored cost record; None = detected only
    start_ts: str
    end_ts: str | None = None
    tier_id: str | None = None
    tier_label: str | None = None
    time_band_id: int | None = None
    time_band_name: str | None = None
    energy_kwh: float | None = None
    peak_power_kw: float | None = None
    cost: float | None = None
    cost_manual: bool = False
    energy_manual: bool = False
    manual_price_kwh: float | None = None
    external_source: str | None = None
    external_id: str | None = None
    provider_account_id: int | None = None
    evse_id: str | None = None
    auto_link_disabled: bool = False
    extras: list[ChargingSessionExtraResponse] = []
    extras_total: float | None = None
    total_cost: float | None = None
    note: str | None = None
    zone_name: str | None = None
    # Cable unplugged / car moved after the charge (time-based extras)
    unplug_ts: str | None = None
    departure_ts: str | None = None
    # End seen in the history, for an open record whose charge stop was missed
    detected_end_ts: str | None = None
    start_soc: int | None = None
    end_soc: int | None = None
    # Where the car charged (last GPS fix of the session, else the stored
    # position, e.g. the charger's), and whether any of its runs was a DC
    # charge
    latitude: float | None = None
    longitude: float | None = None
    is_dc: bool = False
    # Charging runs in the session: more than one for a merged session
    parts: int = 0
    # Set on a record without charging runs lying inside another session's
    # window: most likely a duplicate of that session
    duplicate_of_id: int | None = None
    duplicate_of_start_ts: str | None = None
    duplicate_of_end_ts: str | None = None


class ChargingSessionsResponse(BaseModel):
    timezone: str  # IANA zone the period is computed in
    start: str  # period bounds, naive UTC ``[start, end)``
    end: str
    sessions: list[ChargingSessionRowSchema]  # newest first


class ChargingSessionCostCreate(BaseModel):
    start_ts: str
    end_ts: str | None = None
    tier_id: str
    # Entered by hand when given; else measured / priced with the tier
    energy_kwh: float | None = Field(default=None, ge=0)
    peak_power_kw: float | None = None
    cost: float | None = Field(default=None, ge=0)
    # Price per kWh entered by hand instead of the cost (cost = energy × price)
    manual_price_kwh: float | None = Field(default=None, ge=0)
    # Replaces the session's extra costs; omitted = unchanged
    extras: list[ChargingSessionExtraIn] | None = Field(default=None, max_length=20)
    note: str | None = None
    zone_name: str | None = None


class ChargingSessionCostUpdate(BaseModel):
    tier_id: str | None = None
    end_ts: str | None = None
    # energy_kwh/cost: a value is entered by hand, null goes back to the
    # automatic one (measured / priced), omitted leaves it as it is
    energy_kwh: float | None = Field(default=None, ge=0)
    peak_power_kw: float | None = None
    cost: float | None = Field(default=None, ge=0)
    # Price per kWh entered by hand instead of the cost (cost = energy × price)
    manual_price_kwh: float | None = Field(default=None, ge=0)
    # Replaces the session's extra costs; omitted = unchanged
    extras: list[ChargingSessionExtraIn] | None = Field(default=None, max_length=20)
    note: str | None = None
    zone_name: str | None = None


class MergeChargingSessionsRequest(BaseModel):
    # Start of each selected session (those in between are included too)
    start_ts: list[str]
    # Tier of the merged session; required when the sessions' tiers differ
    tier_id: str | None = None
    # Longest pause allowed between two charging runs
    max_gap_minutes: int = 120


class MergePreviewSession(BaseModel):
    id: int | None = None
    start_ts: str
    end_ts: str | None = None
    energy_kwh: float | None = None
    parts: int = 0
    selected: bool  # False = included because it lies between the selected ones
    tier_id: str | None = None
    # Why this session can't be merged (ongoing | not_in_history | duplicate)
    problem: str | None = None
    problem_message: str | None = None


class MergePreviewRun(BaseModel):
    start_ts: str
    end_ts: str | None = None
    energy_kwh: float | None = None
    zone_name: str | None = None  # "" = outside every zone, None = unknown


class MergePreviewGap(BaseModel):
    start_ts: str
    end_ts: str
    minutes: int
    within_max_gap: bool
    same_odometer: bool | None = None  # None = can't be checked
    same_place: bool | None = None


class MergePreviewResponse(BaseModel):
    sessions: list[MergePreviewSession]  # oldest first
    runs: list[MergePreviewRun]
    gaps: list[MergePreviewGap]
    tiers: list[str]
    tier_id: str | None = None
    zone_name: str | None = None
    energy_kwh: float | None = None
    cost: float | None = None
    max_gap_minutes: int
    reason: str | None = None
    message: str | None = None  # human-readable reason


class MissingCostSessionItem(BaseModel):
    start_ts: str
    end_ts: str | None = None
    cost_id: int | None = None  # set when a stored record already exists


class CalculateMissingCostsRequest(BaseModel):
    sessions: list[MissingCostSessionItem]
    # Tier for sessions whose tier can't be inferred; None skips them.
    fallback_tier_id: str | None = None
    # Close open records whose charge stop was missed, using end_ts.
    close_orphans: bool = False


class SkippedSessionSchema(BaseModel):
    start_ts: str
    reason: str  # ongoing | no_tier | no_energy | not_found


class CalculateMissingCostsResponse(BaseModel):
    calculated: int
    skipped: list[SkippedSessionSchema]


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
    def from_model(cls, r: ConsumptionBreakdown) -> ConsumptionLastWeekResponse:
        return cls(
            driver_ec=r.driver_ec,
            ac_ec=r.ac_ec,
            other_ec=r.other_ec,
            total_ec=r.total_ec,
        )


class ConsumptionBreakdownResponse(ConsumptionLastWeekResponse):
    """Driving / A/C / other split over a chosen range of days."""

    start: date
    end: date

    @classmethod
    def for_window(
        cls, r: ConsumptionBreakdown, start: date, end: date
    ) -> ConsumptionBreakdownResponse:
        return cls(
            driver_ec=r.driver_ec,
            ac_ec=r.ac_ec,
            other_ec=r.other_ec,
            total_ec=r.total_ec,
            start=start,
            end=end,
        )


class DailyMileageEnergySchema(BaseModel):
    day: str
    day_ms: int | None = None
    odometer_km: float | None = None
    mileage_km: float | None = None
    energy_kwh: float | None = None


class MileageEnergyHistoryResponse(BaseModel):
    """Per-day mileage/energy over a range of days, plus lifetime totals.

    The cloud's daily energy is coarse (often rounded to whole kWh);
    ``total_energy_kwh`` (lifetime, standby included) is the precise figure.
    """

    start: date
    end: date
    total_mileage_km: float | None = None
    total_energy_kwh: float | None = None
    delivery_days: int | None = None
    window_mileage_km: float | None = None
    window_energy_kwh: float | None = None
    days: list[DailyMileageEnergySchema]

    @classmethod
    def for_window(
        cls, h: MileageEnergyHistory, start: date, end: date
    ) -> MileageEnergyHistoryResponse:
        energies = [d.energy_kwh for d in h.days if d.energy_kwh is not None]
        return cls(
            start=start,
            end=end,
            total_mileage_km=h.total_mileage_km,
            total_energy_kwh=h.total_energy_kwh,
            delivery_days=h.delivery_days,
            window_mileage_km=h.window_mileage_km,
            window_energy_kwh=round(sum(energies), 2) if energies else None,
            days=[
                DailyMileageEnergySchema(
                    day=d.day,
                    day_ms=d.day_ms,
                    odometer_km=d.odometer_km,
                    mileage_km=d.mileage_km,
                    energy_kwh=d.energy_kwh,
                )
                for d in h.days
            ],
        )
