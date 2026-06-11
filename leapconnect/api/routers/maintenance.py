"""Maintenance routes: model resolution, plan, records, overview, library,
community repositories and packs."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from leapmotor_api.exceptions import LeapmotorApiError

from leapconnect.api.deps import get_repo_or_503
from leapconnect.api.schemas import (
    MaintenanceAlertResponse,
    MaintenanceCostSummary,
    MaintenanceCustomItemCreate,
    MaintenanceLibraryItem,
    MaintenanceLibraryResponse,
    MaintenanceOverviewResponse,
    MaintenancePackImportRequest,
    MaintenancePackResponse,
    MaintenancePlanImportRequest,
    MaintenancePlanImportResult,
    MaintenancePlanItemResponse,
    MaintenancePlanItemUpdate,
    MaintenanceRecordCreate,
    MaintenanceRecordResponse,
    MaintenanceRecordUpdate,
    MaintenanceRepoCreate,
    MaintenanceRepoResponse,
)
from leapconnect.application.maintenance import ensure_plan_generated
from leapconnect.container import container
from leapconnect.domain.maintenance.engine import (
    compute_alerts,
    compute_cost_summary,
    due_soon_alerts,
    summarize,
)
from leapconnect.domain.maintenance.models import (
    MaintenancePack,
    MaintenancePlanItem,
    MaintenanceRecord,
    MaintenanceRepo,
)
from leapconnect.domain.maintenance.packs import (
    OFFICIAL_REPO_URL,
    PACK_SCHEMA,
    factory_items_for_model,
    normalize_pack,
    official_pack_for_model,
    pack_applies_to_model,
)
from leapconnect.domain.maintenance.resolver import resolve_model
from leapconnect.infrastructure.community import (
    CommunityError,
    discover_repo,
    fetch_pack_file,
    fetch_pack_url,
)

_LOGGER = logging.getLogger(__name__)

router = APIRouter()

_REPO_UNAVAILABLE = "Persistence not available"


# ---------------------------------------------------------------------------
# Model resolution helpers
# ---------------------------------------------------------------------------


async def _resolve_maintenance_model(vin: str, vehicle) -> dict:
    """Resolve the vehicle model, applying any persisted C10 variant override."""
    model_info = resolve_model(vehicle)
    if model_info.get("needs_confirmation") and container.repo:
        override = await container.repo.get_setting(f"c10_variant_{vin}")
        if override in ("bev", "reev"):
            model_info["model_key"] = "C10_REEV" if override == "reev" else "C10"
            model_info["variant"] = override
            model_info["confidence"] = "manual"
            model_info["needs_confirmation"] = False
    return model_info


async def _current_mileage_cached(vehicle) -> int | None:
    """Best-effort current odometer reading from the status cache."""
    if not container.vehicle_cache:
        return None
    try:
        status = await container.vehicle_cache.get(vehicle)
        return status.driving.total_mileage if (status and status.driving) else None
    except Exception:
        return None


async def _cache_repo_packs(repo_entity) -> int:
    """Fetch every pack listed in a repo's manifest and cache it. Returns count."""
    count = 0
    for entry in repo_entity.manifest or []:
        try:
            payload = await fetch_pack_file(
                repo_entity.url, repo_entity.branch, entry["file"]
            )
        except (CommunityError, KeyError) as exc:
            _LOGGER.warning("Skipping pack %s in %s: %s", entry, repo_entity.url, exc)
            continue
        pack = MaintenancePack(
            repo_id=repo_entity.id,
            slug=entry.get("slug") or payload.get("name"),
            name=payload.get("name"),
            version=payload.get("version"),
            author=payload.get("author"),
            model_compat=payload.get("model_compat"),
            payload=payload,
        )
        await container.repo.save_maintenance_pack(pack)
        count += 1
    return count


async def _ensure_official_packs() -> list:
    """Return the official factory packs, registering the official repo on first use.

    The factory maintenance schedule lives in the community repo (no embedded
    catalog). This lazily registers and caches it. On any network/parse failure
    it logs and returns whatever is cached (possibly empty) so the app degrades
    gracefully instead of erroring.
    """
    if not container.repo:
        return []
    repo = await container.repo.get_maintenance_repo_by_url(OFFICIAL_REPO_URL)
    if repo is None:
        try:
            discovered = await discover_repo(OFFICIAL_REPO_URL)
        except CommunityError as exc:
            _LOGGER.warning("Official maintenance repo unavailable: %s", exc)
            return []
        repo = MaintenanceRepo(
            type=discovered["type"],
            url=discovered["url"],
            name=discovered["name"],
            author=discovered["author"],
            description=discovered.get("description"),
            branch=discovered["branch"],
            added_at=datetime.now(UTC),
            last_fetched_at=datetime.now(UTC),
            status="ok",
            manifest=discovered["packs"],
        )
        repo = await container.repo.save_maintenance_repo(repo)
        await _cache_repo_packs(repo)
    return await container.repo.list_maintenance_packs(repo.id)


async def _factory_items(model_key: str) -> list[dict]:
    """Return the factory service items for a model from the official packs."""
    return factory_items_for_model(await _ensure_official_packs(), model_key)


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------


@router.get("/api/vehicles/{vin}/maintenance/model")
async def get_vehicle_maintenance_model(vin: str) -> dict:
    """Resolve the vehicle model for maintenance purposes.

    Returns the canonical model key, display name, variant (if C10),
    confidence level, and whether the user needs to confirm the C10 variant.
    """
    vehicle = container.find_vehicle(vin)
    return resolve_model(vehicle)


@router.post("/api/vehicles/{vin}/maintenance/model")
async def set_vehicle_maintenance_model(vin: str, body: dict) -> dict:
    """Override the C10 variant choice for a vehicle.

    Accepts JSON body: {"variant": "bev" | "reev"}
    Persisted per VIN via app settings.
    """
    variant = body.get("variant")
    if variant not in ("bev", "reev"):
        raise HTTPException(status_code=400, detail="variant must be 'bev' or 'reev'")

    vehicle = container.find_vehicle(vin)
    # Persist the override
    if container.repo:
        await container.repo.save_setting(f"c10_variant_{vin}", variant)

    # Re-resolve with the override applied
    base = resolve_model(vehicle)
    if variant == "reev":
        base["model_key"] = "C10_REEV"
        base["display_name"] = "Leapmotor C10 REEV"
        base["variant"] = "reev"
    else:
        base["model_key"] = "C10"
        base["display_name"] = "Leapmotor C10"
        base["variant"] = "bev"
    base["confidence"] = "manual"
    base["needs_confirmation"] = False
    base["detection_reason"] = "user_override"
    return base


@router.get("/api/vehicles/{vin}/maintenance/rules")
async def get_vehicle_maintenance_rules(vin: str) -> dict:
    """Return the official factory maintenance schedule for this vehicle."""
    vehicle = container.find_vehicle(vin)
    model_info = await _resolve_maintenance_model(vin, vehicle)

    model_key = model_info.get("model_key", "unknown")
    pack = official_pack_for_model(await _ensure_official_packs(), model_key)

    if pack is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No official factory schedule found for model '{model_key}'. "
                "The official maintenance repository may be unreachable."
            ),
        )

    return {
        "model": model_info,
        "rules": pack.payload,
    }


# ---------------------------------------------------------------------------
# Plan (CRUD)
# ---------------------------------------------------------------------------


@router.get("/api/vehicles/{vin}/maintenance/plan")
async def get_maintenance_plan(vin: str) -> list:
    """Get the maintenance plan. Auto-generates from the catalog if empty."""
    repo = get_repo_or_503(_REPO_UNAVAILABLE)

    vehicle = container.find_vehicle(vin)
    model_info = await _resolve_maintenance_model(vin, vehicle)
    model_key = model_info.get("model_key", "unknown")
    factory = await _factory_items(model_key)
    items = await ensure_plan_generated(repo, vin, factory)

    return [MaintenancePlanItemResponse(**item.__dict__) for item in items]


@router.put("/api/vehicles/{vin}/maintenance/plan/{service_type}")
async def update_maintenance_plan_item(
    vin: str, service_type: str, body: MaintenancePlanItemUpdate
):
    """Update a single maintenance plan item."""
    repo = get_repo_or_503(_REPO_UNAVAILABLE)

    item = MaintenancePlanItem(
        vin=vin,
        service_type=service_type,
        label="",
        enabled=body.enabled,
        interval_km=body.interval_km,
        interval_months=body.interval_months,
        trigger_mode=body.trigger_mode,
        priority=body.priority,
        last_done_km=body.last_done_km,
        last_done_date=body.last_done_date,
        notes=body.notes,
    )
    await repo.upsert_maintenance_plan_item(vin, item)

    # Return the updated item
    plan = await repo.get_maintenance_plan(vin)
    for p in plan:
        if p.service_type == service_type:
            return MaintenancePlanItemResponse(**p.__dict__)

    raise HTTPException(status_code=404, detail="Plan item not found after upsert")


# ---------------------------------------------------------------------------
# Records (CRUD)
# ---------------------------------------------------------------------------


@router.get("/api/vehicles/{vin}/maintenance/records")
async def get_maintenance_records(
    vin: str, service_type: str | None = None, limit: int = 20
) -> list:
    """Get completed maintenance records for a vehicle."""
    repo = get_repo_or_503(_REPO_UNAVAILABLE)

    records = await repo.get_maintenance_records(
        vin, service_type=service_type, limit=limit
    )
    return [MaintenanceRecordResponse(**r.__dict__) for r in records]


@router.post("/api/vehicles/{vin}/maintenance/records")
async def create_maintenance_record(vin: str, body: MaintenanceRecordCreate):
    """Log a completed maintenance intervention.

    If update_plan_item is True (default), the corresponding plan item's
    last_done_km and last_done_date are updated automatically.
    """
    repo = get_repo_or_503(_REPO_UNAVAILABLE)

    record = MaintenanceRecord(
        vin=vin,
        service_type=body.service_type,
        label=body.label or body.service_type,
        timestamp=body.timestamp or datetime.now(UTC),
        mileage_km=body.mileage_km,
        cost=body.cost,
        provider=body.provider,
        notes=body.notes,
    )
    await repo.save_maintenance_record(record)

    # Auto-update plan item's last-done fields
    if body.update_plan_item:
        update = MaintenancePlanItem(
            vin=vin,
            service_type=body.service_type,
            label="",
            last_done_km=body.mileage_km,
            last_done_date=record.timestamp,
        )
        await repo.upsert_maintenance_plan_item(vin, update)

    return MaintenanceRecordResponse(**record.__dict__)


async def _recalc_plan_last_done(vin: str, service_type: str) -> None:
    """Set the plan item's last_done to its most recent remaining record.

    Uses ``set_plan_item_last_done`` (not upsert) so last_done is cleared to
    NULL when no records remain.
    """
    repo = container.repo
    remaining = await repo.get_maintenance_records(
        vin, service_type=service_type, limit=1
    )
    latest = remaining[0] if remaining else None
    await repo.set_plan_item_last_done(
        vin,
        service_type,
        last_done_km=latest.mileage_km if latest else None,
        last_done_date=latest.timestamp if latest else None,
    )


@router.put("/api/vehicles/{vin}/maintenance/records/{record_id}")
async def edit_maintenance_record(
    vin: str, record_id: int, body: MaintenanceRecordUpdate
):
    """Update a maintenance record and recalculate the plan item's last-done."""
    repo = get_repo_or_503(_REPO_UNAVAILABLE)

    existing = await repo.get_maintenance_record(record_id)
    if existing is None or existing.vin != vin:
        raise HTTPException(status_code=404, detail="Record not found")

    updated = await repo.update_maintenance_record(
        record_id,
        timestamp=body.timestamp,
        mileage_km=body.mileage_km,
        cost=body.cost,
        provider=body.provider,
        notes=body.notes,
    )
    await _recalc_plan_last_done(vin, existing.service_type)
    return MaintenanceRecordResponse(**updated.__dict__)


@router.delete("/api/vehicles/{vin}/maintenance/records/{record_id}")
async def delete_maintenance_record(vin: str, record_id: int) -> dict:
    """Delete a maintenance record and recalculate the plan item's last-done."""
    repo = get_repo_or_503(_REPO_UNAVAILABLE)

    existing = await repo.get_maintenance_record(record_id)
    if existing is None or existing.vin != vin:
        raise HTTPException(status_code=404, detail="Record not found")

    await repo.delete_maintenance_record(record_id)
    await _recalc_plan_last_done(vin, existing.service_type)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


@router.get("/api/vehicles/{vin}/maintenance/overview")
async def get_maintenance_overview(vin: str):
    """Get a summary overview: model, plan, upcoming/overdue counts, next action."""
    repo = get_repo_or_503(_REPO_UNAVAILABLE)

    vehicle = container.find_vehicle(vin)
    model_info = await _resolve_maintenance_model(vin, vehicle)
    model_key = model_info.get("model_key", "unknown")
    factory = await _factory_items(model_key)
    plan = await ensure_plan_generated(repo, vin, factory)
    # All records (newest first): used for cost aggregation; first 5 are "recent".
    records = await repo.get_maintenance_records(vin, limit=None)

    now_utc = datetime.now(UTC).replace(tzinfo=None)  # naive UTC for DB comparison
    current_km = await _current_mileage_cached(vehicle)
    costs = compute_cost_summary(records, plan, now_utc)

    alerts = compute_alerts(plan, current_km, now_utc)
    counts = summarize(alerts)
    shortlist = due_soon_alerts(alerts)
    next_item = None
    if shortlist:
        next_st = shortlist[0].service_type
        next_item = next(
            (
                MaintenancePlanItemResponse(**i.__dict__)
                for i in plan
                if i.service_type == next_st
            ),
            None,
        )

    return MaintenanceOverviewResponse(
        model_key=model_key,
        display_name=model_info.get("display_name", "Unknown"),
        variant=model_info.get("variant"),
        current_km=current_km,
        total_items=len([i for i in plan if i.enabled]),
        upcoming_count=counts["upcoming"],
        overdue_count=counts["overdue"],
        critical_count=counts["critical"],
        next_item=next_item,
        due_soon=[MaintenanceAlertResponse(**a.__dict__) for a in shortlist],
        costs=MaintenanceCostSummary(**costs),
        plan=[MaintenancePlanItemResponse(**item.__dict__) for item in plan],
        recent_records=[MaintenanceRecordResponse(**r.__dict__) for r in records[:5]],
    )


@router.get("/api/vehicles/{vin}/maintenance/current-mileage")
async def get_current_mileage(vin: str) -> dict:
    """Return the vehicle's current odometer reading (km), fetched fresh."""
    client = container.get_client()
    vehicle = container.find_vehicle(vin)

    try:
        status = await client.get_vehicle_status(vehicle)
        mileage = status.driving.total_mileage if (status and status.driving) else None
    except LeapmotorApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"vin": vin, "mileage_km": mileage}


# ---------------------------------------------------------------------------
# Library (catalog + local + community packs)
# ---------------------------------------------------------------------------


def _pack_to_response(pack, in_plan_types: set[str], model_key: str):
    """Build a MaintenancePackResponse from a cached MaintenancePack."""
    payload = pack.payload or {}
    items = []
    for it in payload.get("items", []):
        items.append(
            MaintenanceLibraryItem(
                **{
                    k: it.get(k) for k in MaintenanceLibraryItem.model_fields if k in it
                },
                origin="repo",
                origin_ref=pack.slug,
                in_plan=it.get("service_type") in in_plan_types,
            )
        )
    return MaintenancePackResponse(
        id=pack.id,
        repo_id=pack.repo_id,
        slug=pack.slug,
        name=pack.name or pack.slug,
        author=pack.author,
        version=pack.version,
        description=payload.get("description"),
        model_compat=pack.model_compat,
        items=items,
        applies=pack_applies_to_model(payload, model_key),
    )


def _repo_to_response(r: MaintenanceRepo, pack_count: int) -> MaintenanceRepoResponse:
    return MaintenanceRepoResponse(
        id=r.id,
        type=r.type,
        url=r.url,
        name=r.name,
        author=r.author,
        description=r.description,
        branch=r.branch,
        added_at=r.added_at,
        last_fetched_at=r.last_fetched_at,
        status=r.status,
        pack_count=pack_count,
        is_official=r.url == OFFICIAL_REPO_URL,
    )


@router.get("/api/vehicles/{vin}/maintenance/library")
async def get_maintenance_library(vin: str) -> MaintenanceLibraryResponse:
    """Aggregated browse surface: catalog + local items + community packs.

    Each item is flagged ``in_plan`` so the UI knows what's already imported.
    """
    repo = get_repo_or_503(_REPO_UNAVAILABLE)

    vehicle = container.find_vehicle(vin)
    model_info = await _resolve_maintenance_model(vin, vehicle)
    model_key = model_info.get("model_key", "unknown")

    factory = await _factory_items(model_key)
    plan = await ensure_plan_generated(repo, vin, factory)
    in_plan_types = {i.service_type for i in plan}

    # Catalog items: the official factory schedule for the vehicle's model.
    catalog: list[MaintenanceLibraryItem] = []
    for r in factory:
        catalog.append(
            MaintenanceLibraryItem(
                service_type=r["service_type"],
                label=r["label"],
                category=r.get("category", "other"),
                interval_km=r.get("interval_km"),
                interval_months=r.get("interval_months"),
                trigger_mode=r.get("trigger_mode", "or"),
                priority=r.get("priority", "routine"),
                origin="catalog",
                in_plan=r["service_type"] in in_plan_types,
            )
        )

    # Local items: user-created plan items.
    local = [
        MaintenanceLibraryItem(
            service_type=i.service_type,
            label=i.label,
            category=i.category,
            interval_km=i.interval_km,
            interval_months=i.interval_months,
            trigger_mode=i.trigger_mode,
            priority=i.priority,
            notes=i.notes,
            origin="local",
            in_plan=True,
        )
        for i in plan
        if i.source == "local"
    ]

    # The official repo (factory schedule source) is listed like any other,
    # flagged is_official so the UI can mark it and prevent its removal.
    repos = await repo.list_maintenance_repos()
    all_packs = await repo.list_maintenance_packs()
    packs_by_repo: dict[int | None, int] = {}
    for p in all_packs:
        packs_by_repo[p.repo_id] = packs_by_repo.get(p.repo_id, 0) + 1

    repo_responses = [_repo_to_response(r, packs_by_repo.get(r.id, 0)) for r in repos]
    pack_responses = [_pack_to_response(p, in_plan_types, model_key) for p in all_packs]

    return MaintenanceLibraryResponse(
        model_key=model_key,
        display_name=model_info.get("display_name", "Unknown"),
        variant=model_info.get("variant"),
        catalog=catalog,
        local=local,
        repos=repo_responses,
        packs=pack_responses,
    )


@router.post("/api/vehicles/{vin}/maintenance/plan/import")
async def import_maintenance_plan_items(
    vin: str, body: MaintenancePlanImportRequest
) -> MaintenancePlanImportResult:
    """Explicitly import service items into the vehicle's plan.

    Honours a per-item or request-level conflict strategy when a
    ``service_type`` already exists: ``update`` | ``variant`` | ``skip``.
    """
    repo = get_repo_or_503(_REPO_UNAVAILABLE)

    existing = {i.service_type for i in await repo.get_maintenance_plan(vin)}
    result = MaintenancePlanImportResult()

    for entry in body.items:
        strategy = entry.conflict or body.on_conflict
        service_type = entry.service_type
        conflict = service_type in existing

        if conflict and strategy == "skip":
            result.skipped.append(service_type)
            continue

        outcome = "imported"
        if conflict and strategy == "variant":
            n = 2
            while f"{service_type}_v{n}" in existing:
                n += 1
            service_type = f"{service_type}_v{n}"
            outcome = "variant"
        elif conflict:
            outcome = "updated"

        item = MaintenancePlanItem(
            vin=vin,
            service_type=service_type,
            label=entry.label,
            category=entry.category,
            interval_km=entry.interval_km,
            interval_months=entry.interval_months,
            trigger_mode=entry.trigger_mode,
            priority=entry.priority,
            notes=entry.notes,
            enabled=True,
            source=body.source,
            source_ref=body.source_ref,
        )
        await repo.upsert_maintenance_plan_item(vin, item)
        existing.add(service_type)

        bucket = {
            "imported": result.imported,
            "updated": result.updated,
            "variant": result.variants,
        }[outcome]
        bucket.append(service_type)

    return result


@router.post("/api/vehicles/{vin}/maintenance/plan")
async def create_maintenance_custom_item(
    vin: str, body: MaintenanceCustomItemCreate
) -> MaintenancePlanItemResponse:
    """Create a user-defined (local) maintenance item in the plan."""
    repo = get_repo_or_503(_REPO_UNAVAILABLE)

    existing = {i.service_type for i in await repo.get_maintenance_plan(vin)}
    if body.service_type in existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A plan item with service_type '{body.service_type}' already exists"
            ),
        )

    item = MaintenancePlanItem(
        vin=vin,
        service_type=body.service_type,
        label=body.label,
        category=body.category,
        interval_km=body.interval_km,
        interval_months=body.interval_months,
        trigger_mode=body.trigger_mode,
        priority=body.priority,
        last_done_km=body.last_done_km,
        last_done_date=body.last_done_date,
        notes=body.notes,
        enabled=True,
        source="local",
    )
    await repo.upsert_maintenance_plan_item(vin, item)
    for p in await repo.get_maintenance_plan(vin):
        if p.service_type == body.service_type:
            return MaintenancePlanItemResponse(**p.__dict__)
    raise HTTPException(status_code=500, detail="Item not found after create")


@router.delete("/api/vehicles/{vin}/maintenance/plan/{service_type}")
async def delete_maintenance_plan_item(vin: str, service_type: str) -> dict:
    """Remove a plan item (un-import a community item or delete a custom one)."""
    repo = get_repo_or_503(_REPO_UNAVAILABLE)
    await repo.delete_maintenance_plan_item(vin, service_type)
    return {"deleted": service_type}


@router.get("/api/vehicles/{vin}/maintenance/export")
async def export_local_maintenance(vin: str) -> Response:
    """Export the vehicle's local (user-defined) items as a shareable pack."""
    repo = get_repo_or_503(_REPO_UNAVAILABLE)

    plan = await repo.get_maintenance_plan(vin)
    vehicle = container.find_vehicle(vin)
    model_info = await _resolve_maintenance_model(vin, vehicle)

    items = [
        {
            "service_type": i.service_type,
            "label": i.label,
            "category": i.category,
            "interval_km": i.interval_km,
            "interval_months": i.interval_months,
            "trigger_mode": i.trigger_mode,
            "priority": i.priority,
            "notes": i.notes,
        }
        for i in plan
        if i.source == "local"
    ]
    pack = {
        "schema": PACK_SCHEMA,
        "name": f"{model_info.get('display_name', 'Vehicle')} — custom maintenance",
        "version": 1,
        "model_compat": [model_info.get("model_key", "unknown")],
        "items": items,
    }
    body = json.dumps(pack, indent=2, default=str)
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; "
            "filename=leapconnect-maintenance-local.json"
        },
    )


# ---------------------------------------------------------------------------
# Community repositories & packs
# ---------------------------------------------------------------------------


@router.get("/api/maintenance/repos")
async def list_maintenance_repos() -> list[MaintenanceRepoResponse]:
    """List all maintenance repositories, including the official one."""
    repo = get_repo_or_503(_REPO_UNAVAILABLE)
    repos = await repo.list_maintenance_repos()
    packs = await repo.list_maintenance_packs()
    counts: dict[int | None, int] = {}
    for p in packs:
        counts[p.repo_id] = counts.get(p.repo_id, 0) + 1
    return [_repo_to_response(r, counts.get(r.id, 0)) for r in repos]


@router.post("/api/maintenance/repos")
async def add_maintenance_repo(
    body: MaintenanceRepoCreate,
) -> MaintenanceRepoResponse:
    """Add a community repository: discover and cache its packs."""
    repo = get_repo_or_503(_REPO_UNAVAILABLE)

    try:
        discovered = await discover_repo(body.url)
    except CommunityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing = await repo.get_maintenance_repo_by_url(discovered["url"])
    if existing:
        raise HTTPException(status_code=409, detail="Repository already added")

    repo_entity = MaintenanceRepo(
        type=discovered["type"],
        url=discovered["url"],
        name=discovered["name"],
        author=discovered["author"],
        description=discovered.get("description"),
        branch=discovered["branch"],
        added_at=datetime.now(UTC),
        last_fetched_at=datetime.now(UTC),
        status="ok",
        manifest=discovered["packs"],
    )
    repo_entity = await repo.save_maintenance_repo(repo_entity)
    count = await _cache_repo_packs(repo_entity)

    return _repo_to_response(repo_entity, count)


@router.post("/api/maintenance/repos/{repo_id}/refresh")
async def refresh_maintenance_repo(repo_id: int) -> MaintenanceRepoResponse:
    """Re-discover a repository's manifest and re-cache its packs."""
    repo = get_repo_or_503(_REPO_UNAVAILABLE)
    repo_entity = await repo.get_maintenance_repo(repo_id)
    if not repo_entity:
        raise HTTPException(status_code=404, detail="Repository not found")

    try:
        discovered = await discover_repo(repo_entity.url)
    except CommunityError as exc:
        repo_entity.status = "error"
        await repo.save_maintenance_repo(repo_entity)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    repo_entity.name = discovered["name"]
    repo_entity.author = discovered["author"]
    repo_entity.description = discovered.get("description")
    repo_entity.branch = discovered["branch"]
    repo_entity.manifest = discovered["packs"]
    repo_entity.last_fetched_at = datetime.now(UTC)
    repo_entity.status = "ok"
    repo_entity = await repo.save_maintenance_repo(repo_entity)

    # Drop old cached packs for this repo, then re-cache.
    for p in await repo.list_maintenance_packs(repo_id):
        await repo.delete_maintenance_pack(p.id)
    count = await _cache_repo_packs(repo_entity)

    return _repo_to_response(repo_entity, count)


@router.delete("/api/maintenance/repos/{repo_id}")
async def delete_maintenance_repo(repo_id: int) -> dict:
    """Remove a repository and all packs cached from it."""
    repo = get_repo_or_503(_REPO_UNAVAILABLE)
    existing = await repo.get_maintenance_repo(repo_id)
    if existing and existing.url == OFFICIAL_REPO_URL:
        raise HTTPException(
            status_code=403,
            detail="The official factory repository cannot be removed",
        )
    await repo.delete_maintenance_repo(repo_id)
    return {"deleted": repo_id}


@router.get("/api/maintenance/repos/{repo_id}/packs")
async def list_repo_packs(repo_id: int) -> list[MaintenancePackResponse]:
    """List the packs cached from a repository."""
    repo = get_repo_or_503(_REPO_UNAVAILABLE)
    packs = await repo.list_maintenance_packs(repo_id)
    return [_pack_to_response(p, set(), "unknown") for p in packs]


@router.post("/api/maintenance/packs/import")
async def import_maintenance_pack(
    body: MaintenancePackImportRequest,
) -> MaintenancePackResponse:
    """Fetch/cache a standalone pack from a raw URL or inline JSON.

    For (repo_id + slug) the already-cached pack is returned.
    """
    repo = get_repo_or_503(_REPO_UNAVAILABLE)

    if body.repo_id is not None and body.slug:
        for p in await repo.list_maintenance_packs(body.repo_id):
            if p.slug == body.slug:
                return _pack_to_response(p, set(), "unknown")
        raise HTTPException(status_code=404, detail="Pack not found in repository")

    try:
        if body.url:
            payload = await fetch_pack_url(body.url)
            slug = body.url.rstrip("/").split("/")[-1].replace(".json", "")
        elif body.inline is not None:
            payload = normalize_pack(body.inline)
            slug = (payload.get("name") or "imported").lower().replace(" ", "-")
        else:
            raise HTTPException(
                status_code=400,
                detail="Provide one of: repo_id+slug, url, or inline",
            )
    except CommunityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    pack = MaintenancePack(
        repo_id=None,
        slug=slug,
        name=payload.get("name"),
        version=payload.get("version"),
        author=payload.get("author"),
        model_compat=payload.get("model_compat"),
        payload=payload,
    )
    pack = await repo.save_maintenance_pack(pack)
    return _pack_to_response(pack, set(), "unknown")


@router.post("/api/maintenance/upload")
async def upload_maintenance_pack(
    file: UploadFile = File(...),  # noqa: B008
) -> MaintenancePackResponse:
    """Upload a maintenance pack JSON file and cache it as a standalone pack."""
    repo = get_repo_or_503(_REPO_UNAVAILABLE)

    raw = await file.read()
    try:
        payload = normalize_pack(json.loads(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid pack: {exc}") from exc

    slug = (file.filename or payload.get("name") or "uploaded").rsplit("/", 1)[-1]
    slug = slug.replace(".json", "")
    pack = MaintenancePack(
        repo_id=None,
        slug=slug,
        name=payload.get("name"),
        version=payload.get("version"),
        author=payload.get("author"),
        model_compat=payload.get("model_compat"),
        payload=payload,
    )
    pack = await repo.save_maintenance_pack(pack)
    return _pack_to_response(pack, set(), "unknown")
