"""Battery State of Health estimate.

No cloud API exposes the pack SOH, but the remaining energy the BMS reports
(``dump_energy``) is scaled to the pack's real capacity, so the energy it
reports at a full charge (SOC 100%) is a proxy for the usable capacity. The
displayed SOC isn't linear in energy (the energy/SOC ratio drifts by ~3%
between 30% and 100%), hence only full-charge readings are comparable.

A cold pack reads lower, so each day contributes its highest full-charge
reading and the series is smoothed with a rolling median over the last
``WINDOW`` full-charge days.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import median

#: Full-charge days in the rolling median.
WINDOW = 7
#: Fewer full-charge days than this give no estimate at all.
MIN_SAMPLES = 3
#: Plausible usable capacity range (kWh) for a user-entered reference.
MIN_REFERENCE_KWH = 10.0
MAX_REFERENCE_KWH = 200.0


@dataclass(frozen=True, slots=True)
class FullChargeSample:
    """The highest energy (kWh) reported at SOC 100% on a given day."""

    day: date
    energy_kwh: float


@dataclass(frozen=True, slots=True)
class CapacityPoint:
    """One full-charge day: raw reading, smoothed capacity and its SOH."""

    day: date
    energy_kwh: float
    capacity_kwh: float
    soh_pct: float


@dataclass(frozen=True, slots=True)
class BatteryHealth:
    """Current SOH estimate and the series it was derived from."""

    soh_pct: float
    capacity_kwh: float
    reference_kwh: float
    #: ``"user"`` (entered by the user) or ``"observed"`` (peak capacity seen).
    reference_source: str
    last_full_charge: date
    samples: int
    series: list[CapacityPoint]


def is_valid_reference(kwh: float) -> bool:
    return MIN_REFERENCE_KWH <= kwh <= MAX_REFERENCE_KWH


def smooth_capacity(samples: list[FullChargeSample]) -> list[float]:
    """Rolling median of the last ``WINDOW`` readings, per sample."""
    values = [s.energy_kwh for s in samples]
    return [median(values[max(0, i - WINDOW + 1) : i + 1]) for i in range(len(values))]


def estimate_battery_health(
    samples: list[FullChargeSample], reference_kwh: float | None = None
) -> BatteryHealth | None:
    """SOH estimate from per-day full-charge readings, or None if too few.

    Without a user ``reference_kwh`` the reference is the peak smoothed
    capacity observed (on a young pack, the first weeks), i.e. the SOH is
    relative to when LeapConnect started recording, not to the factory
    capacity.
    """
    samples = sorted((s for s in samples if s.energy_kwh > 0), key=lambda s: s.day)
    if len(samples) < MIN_SAMPLES:
        return None

    smoothed = smooth_capacity(samples)
    if reference_kwh is not None and is_valid_reference(reference_kwh):
        reference, source = reference_kwh, "user"
    else:
        # Points before the window fills are medians of 1-6 days: skip them
        # so a single odd early reading can't become the reference.
        reference, source = max(smoothed[WINDOW - 1 :] or smoothed), "observed"

    def _soh(kwh: float) -> float:
        return round(kwh / reference * 100, 1)

    series = [
        CapacityPoint(
            day=s.day,
            energy_kwh=round(s.energy_kwh, 2),
            capacity_kwh=round(cap, 2),
            soh_pct=_soh(cap),
        )
        for s, cap in zip(samples, smoothed, strict=True)
    ]
    current = series[-1]
    return BatteryHealth(
        soh_pct=current.soh_pct,
        capacity_kwh=current.capacity_kwh,
        reference_kwh=round(reference, 2),
        reference_source=source,
        last_full_charge=current.day,
        samples=len(samples),
        series=series,
    )
