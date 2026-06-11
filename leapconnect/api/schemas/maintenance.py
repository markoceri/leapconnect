"""Maintenance plan, records, alerts, library, repos and packs DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MaintenancePlanItemResponse(BaseModel):
    id: int
    vin: str = ""
    service_type: str
    label: str
    category: str
    interval_km: int | None = None
    interval_months: int | None = None
    trigger_mode: str = "or"
    priority: str = "routine"
    last_done_km: int | None = None
    last_done_date: datetime | None = None
    enabled: bool = True
    notes: str | None = None
    source: str = "catalog"
    source_ref: str | None = None


class MaintenancePlanItemUpdate(BaseModel):
    enabled: bool | None = None
    interval_km: int | None = None
    interval_months: int | None = None
    trigger_mode: str | None = None
    priority: str | None = None
    last_done_km: int | None = None
    last_done_date: datetime | None = None
    notes: str | None = None


class MaintenanceRecordResponse(BaseModel):
    id: int
    vin: str = ""
    service_type: str
    label: str
    timestamp: datetime | None = None
    mileage_km: int | None = None
    cost: float | None = None
    provider: str | None = None
    notes: str | None = None


class MaintenanceRecordCreate(BaseModel):
    service_type: str
    label: str = ""
    timestamp: datetime | None = None
    mileage_km: int | None = None
    cost: float | None = None
    provider: str | None = None
    notes: str | None = None
    # If True, update the corresponding plan item's last_done fields
    update_plan_item: bool = True


class MaintenanceRecordUpdate(BaseModel):
    timestamp: datetime | None = None
    mileage_km: int | None = None
    cost: float | None = None
    provider: str | None = None
    notes: str | None = None


class MaintenanceAlertResponse(BaseModel):
    plan_item_id: int
    service_type: str
    label: str
    category: str
    priority: str
    status: str  # "ok" | "due_soon" | "overdue"
    due_km: int | None = None
    due_date: datetime | None = None
    current_km: int | None = None
    remaining_km: int | None = None
    remaining_days: int | None = None


class MaintenanceCostByCategory(BaseModel):
    category: str
    total: float = 0.0


class MaintenanceCostSummary(BaseModel):
    total: float = 0.0  # all-time sum of logged service costs
    this_year: float = 0.0
    services_count: int = 0  # number of records with a recorded cost
    avg: float = 0.0  # average cost per costed service
    by_category: list[MaintenanceCostByCategory] = []


class MaintenanceOverviewResponse(BaseModel):
    model_key: str
    display_name: str
    variant: str | None = None
    current_km: int | None = None
    total_items: int = 0
    upcoming_count: int = 0
    overdue_count: int = 0
    critical_count: int = 0
    next_item: MaintenancePlanItemResponse | None = None
    # Overdue + due-soon items, urgency-sorted (Overview shortlist).
    due_soon: list[MaintenanceAlertResponse] = []
    costs: MaintenanceCostSummary = MaintenanceCostSummary()
    plan: list[MaintenancePlanItemResponse] = []
    recent_records: list[MaintenanceRecordResponse] = []


class MaintenanceServiceItem(BaseModel):
    """A maintenance service item definition (catalog/pack/local)."""

    service_type: str
    label: str
    category: str = "other"
    interval_km: int | None = None
    interval_months: int | None = None
    trigger_mode: str = "or"
    priority: str = "routine"
    notes: str | None = None


class MaintenanceLibraryItem(MaintenanceServiceItem):
    """A library item with its origin and whether it's already in the plan."""

    origin: str  # "catalog" | "repo" | "local"
    origin_ref: str | None = None  # repo/pack slug for repo items
    in_plan: bool = False


class MaintenancePackResponse(BaseModel):
    id: int | None = None
    repo_id: int | None = None
    slug: str
    name: str
    author: str | None = None
    version: int | None = None
    description: str | None = None
    model_compat: list[str] | None = None
    items: list[MaintenanceLibraryItem] = []
    applies: bool = True  # matches this vehicle's model


class MaintenanceRepoResponse(BaseModel):
    id: int
    type: str
    url: str
    name: str | None = None
    author: str | None = None
    description: str | None = None
    branch: str | None = None
    added_at: datetime | None = None
    last_fetched_at: datetime | None = None
    status: str = "ok"
    pack_count: int = 0
    is_official: bool = False


class MaintenanceRepoCreate(BaseModel):
    url: str


class MaintenanceLibraryResponse(BaseModel):
    model_key: str
    display_name: str
    variant: str | None = None
    catalog: list[MaintenanceLibraryItem] = []
    local: list[MaintenanceLibraryItem] = []
    repos: list[MaintenanceRepoResponse] = []
    packs: list[MaintenancePackResponse] = []


class MaintenancePlanImportItem(MaintenanceServiceItem):
    # Optional per-item conflict resolution; falls back to request default.
    conflict: str | None = None  # "update" | "variant" | "skip"


class MaintenancePlanImportRequest(BaseModel):
    items: list[MaintenancePlanImportItem]
    source: str = "repo"  # "repo" | "local"
    source_ref: str | None = None
    on_conflict: str = "update"  # "update" | "variant" | "skip"


class MaintenancePlanImportResult(BaseModel):
    imported: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []
    variants: list[str] = []


class MaintenanceCustomItemCreate(MaintenanceServiceItem):
    last_done_km: int | None = None
    last_done_date: datetime | None = None


class MaintenancePackImportRequest(BaseModel):
    # One of: (repo_id + slug) | url | inline
    repo_id: int | None = None
    slug: str | None = None
    url: str | None = None
    inline: dict | None = None
