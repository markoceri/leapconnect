"""Maintenance pack normalization & validation (pure domain service)."""

from __future__ import annotations

PACK_SCHEMA = "leapconnect.maintenance.pack/1"

# The factory maintenance schedules now live in this community repository as
# "official" packs (one per model), instead of an embedded catalog. The repo is
# auto-registered and its packs power the per-vehicle plan auto-generation.
OFFICIAL_REPO_URL = "https://github.com/markoceri/leapconnect-maintenance-packs"

# Fields that make up a maintenance service item in a pack/catalog.
ITEM_FIELDS = (
    "service_type",
    "label",
    "category",
    "interval_km",
    "interval_months",
    "trigger_mode",
    "priority",
    "notes",
)


def normalize_item(raw: dict) -> dict:
    """Validate and normalize a single service item from a pack."""
    if not isinstance(raw, dict):
        raise ValueError("item must be an object")
    service_type = (raw.get("service_type") or "").strip()
    if not service_type:
        raise ValueError("item is missing 'service_type'")
    label = (raw.get("label") or service_type).strip()

    interval_km = raw.get("interval_km")
    interval_months = raw.get("interval_months")
    if interval_km is not None:
        interval_km = int(interval_km)
    if interval_months is not None:
        interval_months = int(interval_months)

    trigger_mode = raw.get("trigger_mode") or "or"
    if trigger_mode not in ("or", "and", "km", "time"):
        trigger_mode = "or"
    priority = raw.get("priority") or "routine"
    if priority not in ("routine", "important", "urgent"):
        priority = "routine"

    return {
        "service_type": service_type,
        "label": label,
        "category": (raw.get("category") or "other").strip(),
        "interval_km": interval_km,
        "interval_months": interval_months,
        "trigger_mode": trigger_mode,
        "priority": priority,
        "notes": raw.get("notes"),
    }


def normalize_pack(payload: dict) -> dict:
    """Validate and normalize a maintenance pack payload.

    Returns a dict with the canonical pack shape. Raises ``ValueError`` when
    the payload is structurally invalid.
    """
    if not isinstance(payload, dict):
        raise ValueError("pack must be a JSON object")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("pack must contain a non-empty 'items' array")

    items = [normalize_item(it) for it in raw_items]

    model_compat = payload.get("model_compat")
    if model_compat is not None and not isinstance(model_compat, list):
        model_compat = [str(model_compat)]

    version = payload.get("version")
    if version is not None:
        try:
            version = int(version)
        except (TypeError, ValueError):
            version = None

    return {
        "schema": payload.get("schema") or PACK_SCHEMA,
        "name": payload.get("name") or "Untitled pack",
        "author": payload.get("author"),
        "version": version,
        "description": payload.get("description"),
        "model_compat": model_compat,
        "items": items,
    }


def pack_applies_to_model(pack: dict, model_key: str) -> bool:
    """A pack applies if it declares no compat list, or lists this model.

    Matching is loose on the base model (``C10`` matches ``C10_REEV``).
    """
    compat = pack.get("model_compat")
    if not compat:
        return True
    base = (model_key or "").split("_")[0].upper()
    for m in compat:
        mu = str(m).upper()
        if mu == (model_key or "").upper() or mu.split("_")[0] == base:
            return True
    return False


def official_pack_for_model(packs: list, model_key: str) -> object | None:
    """Pick the official pack whose model_compat lists this exact model_key.

    Matching is exact (not the loose base-model match) because, e.g., C10 (BEV)
    and C10_REEV have different factory schedules.
    """
    for pack in packs:
        compat = (pack.payload or {}).get("model_compat") or pack.model_compat or []
        if model_key in compat:
            return pack
    return None


def factory_items_for_model(packs: list, model_key: str) -> list[dict]:
    """Return the factory service items for a model from the official packs."""
    pack = official_pack_for_model(packs, model_key)
    if not pack:
        return []
    return (pack.payload or {}).get("items", [])
