"""Extra costs of a charging session (pure domain service).

On top of the energy, a charge can cost a session fee, an idle fee for staying
plugged in after the charge, parking, a per-minute fee, a roaming surcharge,
a payment fee, or get a discount. Each extra is one of four kinds:

- ``fixed``: an amount (negative for a discount);
- ``time``: a rate per minute or hour over a span of the session, from the
  charge start or end (plus an offset, e.g. a grace period) to the charge end,
  the unplug, the departure, or for a duration entered by hand; billed exactly
  or per started unit, up to an optional cap;
- ``per_kwh``: a rate per kWh charged;
- ``percent``: a percentage of the energy cost.

Unplug and departure times come from the snapshots after the charge.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime, timedelta

from leapconnect.domain.charging.models import ChargingSessionExtra
from leapconnect.domain.telemetry.models import VehicleSnapshot

EXTRA_FIXED = "fixed"
EXTRA_TIME = "time"
EXTRA_PER_KWH = "per_kwh"
EXTRA_PERCENT = "percent"
EXTRA_KINDS = (EXTRA_FIXED, EXTRA_TIME, EXTRA_PER_KWH, EXTRA_PERCENT)

FROM_CHARGE_START = "charge_start"
FROM_CHARGE_END = "charge_end"
START_REFS = (FROM_CHARGE_START, FROM_CHARGE_END)

UNTIL_CHARGE_END = "charge_end"
UNTIL_UNPLUG = "unplug"
UNTIL_DEPARTURE = "departure"
UNTIL_MANUAL = "manual"
END_REFS = (UNTIL_CHARGE_END, UNTIL_UNPLUG, UNTIL_DEPARTURE, UNTIL_MANUAL)

UNIT_MINUTES = {"minute": 1, "hour": 60}
BILLING_EXACT = "exact"
BILLING_STARTED = "started"  # every started unit is billed whole

# How long after the charge the unplug and the departure are looked for
AFTER_CHARGE_WINDOW = timedelta(hours=48)


def find_unplug(
    snapshots: Sequence[VehicleSnapshot], after: datetime | None
) -> datetime | None:
    """First snapshot after ``after`` with the cable unplugged.

    The unplug happened between the previous snapshot and this one: its time
    is an upper bound, as precise as the polling interval.
    """
    if after is None:
        return None
    limit = after + AFTER_CHARGE_WINDOW
    for s in snapshots:
        if after <= s.timestamp <= limit and s.vehicle_is_plugged is False:
            return s.timestamp
    return None


def find_departure(
    snapshots: Sequence[VehicleSnapshot], after: datetime | None
) -> datetime | None:
    """First snapshot after ``after`` with the car moving or a higher odometer."""
    if after is None:
        return None
    limit = after + AFTER_CHARGE_WINDOW
    odometer = None
    for s in snapshots:
        if s.timestamp > limit:
            break
        reading = s.drive_total_mileage if (s.drive_total_mileage or 0) > 0 else None
        if s.timestamp < after:
            odometer = reading or odometer
            continue
        if (s.drive_speed or 0) > 0 or (
            odometer is not None and reading is not None and reading > odometer
        ):
            return s.timestamp
        odometer = odometer or reading
    return None


def billable_minutes(
    extra: ChargingSessionExtra,
    *,
    start_ts: datetime | None,
    end_ts: datetime | None,
    unplug_ts: datetime | None = None,
    departure_ts: datetime | None = None,
) -> int | None:
    """Minutes a time-based extra applies for; ``None`` when not known yet."""
    if extra.end_ref == UNTIL_MANUAL:
        return extra.duration_min
    begin = start_ts if extra.start_ref == FROM_CHARGE_START else end_ts
    finish = {
        UNTIL_CHARGE_END: end_ts,
        UNTIL_UNPLUG: unplug_ts,
        UNTIL_DEPARTURE: departure_ts,
    }.get(extra.end_ref)
    if begin is None or finish is None:
        return None
    begin += timedelta(minutes=extra.start_offset_min or 0)
    return max(0, int((finish - begin).total_seconds() // 60))


def extra_cost(
    extra: ChargingSessionExtra,
    *,
    energy_kwh: float | None,
    energy_cost: float | None,
    minutes: int | None = None,
) -> float | None:
    """Amount of one extra; ``None`` when it can't be computed."""
    if extra.kind == EXTRA_FIXED:
        return extra.amount
    if extra.rate is None:
        return None
    if extra.kind == EXTRA_PER_KWH:
        return None if energy_kwh is None else round(extra.rate * energy_kwh, 4)
    if extra.kind == EXTRA_PERCENT:
        return None if energy_cost is None else round(extra.rate * energy_cost / 100, 4)
    if extra.kind != EXTRA_TIME or minutes is None:
        return None
    units = minutes / UNIT_MINUTES.get(extra.time_unit, 60)
    if extra.billing == BILLING_STARTED:
        units = math.ceil(units)
    cost = extra.rate * units
    if extra.cap is not None:
        cost = min(cost, extra.cap)
    return round(cost, 4)


def price_extras(
    extras: Sequence[ChargingSessionExtra],
    *,
    energy_kwh: float | None,
    energy_cost: float | None,
    start_ts: datetime | None,
    end_ts: datetime | None,
    unplug_ts: datetime | None = None,
    departure_ts: datetime | None = None,
) -> None:
    """Compute ``minutes`` and ``cost`` of each extra in place."""
    for extra in extras:
        extra.minutes = (
            billable_minutes(
                extra,
                start_ts=start_ts,
                end_ts=end_ts,
                unplug_ts=unplug_ts,
                departure_ts=departure_ts,
            )
            if extra.kind == EXTRA_TIME
            else None
        )
        extra.cost = extra_cost(
            extra,
            energy_kwh=energy_kwh,
            energy_cost=energy_cost,
            minutes=extra.minutes,
        )


def needs_after_charge(extras: Sequence[ChargingSessionExtra]) -> bool:
    """Whether the unplug or departure time is needed to price ``extras``."""
    return any(
        e.kind == EXTRA_TIME and e.end_ref in (UNTIL_UNPLUG, UNTIL_DEPARTURE)
        for e in extras
    )
