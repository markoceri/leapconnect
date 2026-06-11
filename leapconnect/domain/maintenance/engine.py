"""Maintenance alert engine (pure domain service).

Computes due/overdue alerts for a vehicle's maintenance plan and aggregates
service-cost statistics. No I/O.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from leapconnect.domain.maintenance.models import MaintenanceAlert, MaintenancePlanItem

# Due-soon thresholds for the Overview shortlist (configurable later).
DUE_SOON_KM = 2000
DUE_SOON_DAYS = 60

_PRIORITY_ORDER = {"urgent": 0, "important": 1, "routine": 2}


def _due_km(item: MaintenancePlanItem) -> int | None:
    if item.last_done_km is not None and item.interval_km:
        return item.last_done_km + item.interval_km
    return None


def _due_date(item: MaintenancePlanItem) -> datetime | None:
    if item.last_done_date and item.interval_months:
        return item.last_done_date + timedelta(days=item.interval_months * 30)
    return None


def compute_alert(
    item: MaintenancePlanItem,
    current_km: int | None,
    now: datetime,
) -> MaintenanceAlert | None:
    """Compute a due/overdue alert for a single plan item.

    Returns ``None`` when there is not enough data to compute a due point
    (e.g. the item has never been logged), or the item is disabled.
    The ``status`` is one of ``"ok" | "due_soon" | "overdue"`` and honours the
    item's ``trigger_mode`` (``or`` / ``and`` / ``km`` / ``time``).
    """
    if not item.enabled:
        return None

    due_km = _due_km(item)
    due_date = _due_date(item)
    if due_km is None and due_date is None:
        return None

    remaining_km = None
    if due_km is not None and current_km is not None:
        remaining_km = due_km - current_km
    remaining_days = None
    if due_date is not None:
        remaining_days = (due_date - now).days

    km_overdue = remaining_km is not None and remaining_km <= 0
    time_overdue = remaining_days is not None and remaining_days <= 0
    km_soon = remaining_km is not None and 0 < remaining_km <= DUE_SOON_KM
    time_soon = remaining_days is not None and 0 < remaining_days <= DUE_SOON_DAYS

    mode = item.trigger_mode or "or"
    if mode == "km":
        overdue, soon = km_overdue, km_soon
    elif mode == "time":
        overdue, soon = time_overdue, time_soon
    elif mode == "and":
        # Both conditions must be met to be overdue.
        overdue = km_overdue and time_overdue
        soon = (km_overdue or km_soon) and (time_overdue or time_soon) and not overdue
    else:  # "or" (default)
        overdue = km_overdue or time_overdue
        soon = (km_soon or time_soon) and not overdue

    status = "overdue" if overdue else ("due_soon" if soon else "ok")

    return MaintenanceAlert(
        plan_item_id=item.id or 0,
        service_type=item.service_type,
        label=item.label,
        category=item.category,
        priority=item.priority,
        status=status,
        due_km=due_km,
        due_date=due_date,
        current_km=current_km,
        remaining_km=remaining_km,
        remaining_days=remaining_days,
    )


def compute_alerts(
    plan: list[MaintenancePlanItem],
    current_km: int | None,
    now: datetime,
) -> list[MaintenanceAlert]:
    """Compute alerts for a plan, sorted by urgency (most urgent first)."""
    alerts = []
    for item in plan:
        alert = compute_alert(item, current_km, now)
        if alert is not None:
            alerts.append(alert)

    def _sort_key(a: MaintenanceAlert):
        status_rank = {"overdue": 0, "due_soon": 1, "ok": 2}.get(a.status, 3)
        # Within a status, sort by how soon (smaller remaining first).
        remaining = []
        if a.remaining_km is not None:
            remaining.append(a.remaining_km / max(DUE_SOON_KM, 1))
        if a.remaining_days is not None:
            remaining.append(a.remaining_days / max(DUE_SOON_DAYS, 1))
        nearest = min(remaining) if remaining else 999
        return (status_rank, nearest, _PRIORITY_ORDER.get(a.priority, 9))

    alerts.sort(key=_sort_key)
    return alerts


def due_soon_alerts(alerts: list[MaintenanceAlert]) -> list[MaintenanceAlert]:
    """Filter to the Overview shortlist: overdue + due-soon, urgency-sorted."""
    return [a for a in alerts if a.status in ("overdue", "due_soon")]


def compute_cost_summary(records: list, plan: list, now: datetime) -> dict:
    """Aggregate logged service costs: total, this year, count, avg, by category.

    ``records`` are MaintenanceRecord rows; ``plan`` provides the
    service_type→category mapping for the per-category breakdown.
    """
    category_of = {p.service_type: (p.category or "other") for p in plan}
    costed = [r for r in records if r.cost is not None]

    total = sum(r.cost for r in costed)
    this_year = sum(
        r.cost for r in costed if r.timestamp and r.timestamp.year == now.year
    )
    by_cat: dict[str, float] = {}
    for r in costed:
        cat = category_of.get(r.service_type, "other")
        by_cat[cat] = by_cat.get(cat, 0.0) + r.cost

    by_category = [
        {"category": c, "total": round(v, 2)}
        for c, v in sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return {
        "total": round(total, 2),
        "this_year": round(this_year, 2),
        "services_count": len(costed),
        "avg": round(total / len(costed), 2) if costed else 0.0,
        "by_category": by_category,
    }


def summarize(alerts: list[MaintenanceAlert]) -> dict:
    """Return {upcoming, overdue, critical} counts from computed alerts."""
    overdue = sum(1 for a in alerts if a.status == "overdue")
    upcoming = sum(1 for a in alerts if a.status == "due_soon")
    critical = sum(
        1 for a in alerts if a.status == "overdue" and a.priority == "urgent"
    )
    return {"upcoming": upcoming, "overdue": overdue, "critical": critical}
