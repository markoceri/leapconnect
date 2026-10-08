"""Battery health use case: SOH estimate + the per-vehicle reference capacity."""

from __future__ import annotations

from typing import TYPE_CHECKING

from leapconnect.domain.telemetry.battery_health import (
    BatteryHealth,
    estimate_battery_health,
    is_valid_reference,
)

if TYPE_CHECKING:
    from leapconnect.application.ports.repositories import AppRepository


def _reference_key(vin: str) -> str:
    return f"battery_reference_kwh_{vin}"


async def load_reference_kwh(repo: AppRepository, vin: str) -> float | None:
    """User-entered reference capacity for *vin*, if any (and still valid)."""
    raw = await repo.get_setting(_reference_key(vin))
    try:
        value = float(raw) if raw else None
    except ValueError:
        return None
    return value if value is not None and is_valid_reference(value) else None


async def save_reference_kwh(repo: AppRepository, vin: str, kwh: float | None) -> None:
    """Store the reference capacity; ``None`` reverts to the observed one."""
    if kwh is not None and not is_valid_reference(kwh):
        raise ValueError(f"Reference capacity out of range: {kwh} kWh")
    await repo.save_setting(_reference_key(vin), "" if kwh is None else str(kwh))


async def get_battery_health(repo: AppRepository, vin: str) -> BatteryHealth | None:
    """Current SOH estimate for *vin*, or None without enough full charges."""
    samples = await repo.get_full_charge_samples(vin)
    return estimate_battery_health(samples, await load_reference_kwh(repo, vin))
