"""Maintenance entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class MaintenancePlanItem:
    """A single maintenance service item in a vehicle's plan (editable)."""

    id: int | None = None
    vin: str = ""
    service_type: str = ""
    label: str = ""
    category: str = ""
    interval_km: int | None = None
    interval_months: int | None = None
    trigger_mode: str = "or"  # "or" | "km" | "time" | "and"
    priority: str = "routine"  # "routine" | "important" | "urgent"
    last_done_km: int | None = None
    last_done_date: datetime | None = None
    enabled: bool = True
    notes: str | None = None
    source: str = "catalog"  # "catalog" | "repo" | "local"
    source_ref: str | None = None  # repo/pack slug the item was imported from


@dataclass
class MaintenanceRecord:
    """A completed maintenance intervention (service log entry)."""

    id: int | None = None
    vin: str = ""
    service_type: str = ""
    label: str = ""
    timestamp: datetime | None = None
    mileage_km: int | None = None
    cost: float | None = None
    provider: str | None = None
    notes: str | None = None


@dataclass
class MaintenanceAlert:
    """Computed alert for an upcoming or overdue maintenance item."""

    plan_item_id: int
    service_type: str
    label: str
    category: str
    priority: str
    status: str  # "upcoming" | "overdue" | "critical"
    due_km: int | None = None
    due_date: datetime | None = None
    current_km: int | None = None
    remaining_km: int | None = None
    remaining_days: int | None = None


@dataclass
class MaintenanceRepo:
    """A community repository the user has added."""

    id: int | None = None
    type: str = "github"  # "github" | "url"
    url: str = ""
    name: str | None = None
    author: str | None = None
    description: str | None = None
    branch: str | None = None
    added_at: datetime | None = None
    last_fetched_at: datetime | None = None
    etag: str | None = None
    status: str = "ok"  # "ok" | "error" | "pending"
    # Cached manifest: list of available packs (slug/file/name/model_compat).
    manifest: list[dict] | None = None


@dataclass
class MaintenancePack:
    """A cached maintenance pack (from a repo, URL, or uploaded file)."""

    id: int | None = None
    repo_id: int | None = None
    slug: str = ""
    name: str | None = None
    version: int | None = None
    author: str | None = None
    model_compat: list[str] | None = None
    # Full pack payload: {schema, name, author, version, model_compat, items[]}.
    payload: dict | None = None
    fetched_at: datetime | None = None
