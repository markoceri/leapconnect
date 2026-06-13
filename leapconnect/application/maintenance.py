"""Maintenance use cases (application layer)."""

from __future__ import annotations

from leapconnect.application.ports.repositories import AppRepository
from leapconnect.domain.maintenance.models import MaintenancePlanItem


async def ensure_plan_generated(
    repo: AppRepository, vin: str, factory_items: list[dict]
) -> list:
    """Return the vehicle's plan, auto-generating it from ``factory_items`` if empty."""
    plan = await repo.get_maintenance_plan(vin)
    if plan:
        return plan
    for r in factory_items or []:
        item = MaintenancePlanItem(
            vin=vin,
            service_type=r["service_type"],
            label=r["label"],
            category=r.get("category", "other"),
            interval_km=r.get("interval_km"),
            interval_months=r.get("interval_months"),
            trigger_mode=r.get("trigger_mode", "or"),
            priority=r.get("priority", "routine"),
            source="catalog",
        )
        await repo.upsert_maintenance_plan_item(vin, item)
    if factory_items:
        plan = await repo.get_maintenance_plan(vin)
    return plan
