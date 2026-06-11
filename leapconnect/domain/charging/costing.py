"""Charging cost calculation (pure domain service).

Supports a flat per-tier price and time-of-use (TOU) pricing where the session
energy is split proportionally across configured time bands.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from leapconnect.domain.charging.models import ChargingTimeBand

# Sessions are walked in fixed slots to attribute time to TOU bands.
TOU_SLOT = timedelta(minutes=15)


def flat_cost(energy_kwh: float, price_kwh: float) -> float:
    return round(energy_kwh * price_kwh, 4)


def match_time_band(
    timestamp: datetime, bands: list[ChargingTimeBand]
) -> ChargingTimeBand | None:
    """Find which time band a timestamp falls into."""
    weekday = timestamp.weekday()  # 0=Mon, 6=Sun
    time_minutes = timestamp.hour * 60 + timestamp.minute

    for band in bands:
        for slot in band.schedule:
            if weekday not in slot.get("days", []):
                continue
            start_min = slot.get("start_hour", 0) * 60 + slot.get("start_min", 0)
            end_min = slot.get("end_hour", 0) * 60 + slot.get("end_min", 0)
            # Handle overnight bands (e.g. 23:00 - 07:00)
            if end_min <= start_min:
                if time_minutes >= start_min or time_minutes < end_min:
                    return band
            else:
                if start_min <= time_minutes < end_min:
                    return band
    return None


def calculate_tou_cost(
    energy_kwh: float,
    start_ts: datetime,
    end_ts: datetime,
    bands: list[ChargingTimeBand],
    flat_price: float,
) -> float:
    """Split energy proportionally across time bands based on session duration.

    Hours not covered by any band fall back to *flat_price*.
    """
    total_seconds = (end_ts - start_ts).total_seconds()
    if total_seconds <= 0:
        return 0.0

    # Walk through the session in fixed increments, determine band for each slot
    band_seconds: dict[int, float] = {}  # band_id -> seconds in that band
    fallback_seconds = 0.0
    current = start_ts
    while current < end_ts:
        slot_end = min(current + TOU_SLOT, end_ts)
        slot_duration = (slot_end - current).total_seconds()
        matched_band = match_time_band(current, bands)
        if matched_band:
            band_seconds[matched_band.id] = (
                band_seconds.get(matched_band.id, 0) + slot_duration
            )
        else:
            fallback_seconds += slot_duration
        current = slot_end

    # Calculate cost proportionally
    total_cost = 0.0
    for band_id, secs in band_seconds.items():
        band = next((b for b in bands if b.id == band_id), None)
        if band:
            proportion = secs / total_seconds
            total_cost += proportion * energy_kwh * band.price_kwh

    # Fallback: uncovered hours use the tier's flat price
    if fallback_seconds > 0:
        proportion = fallback_seconds / total_seconds
        total_cost += proportion * energy_kwh * flat_price

    return round(total_cost, 4)
