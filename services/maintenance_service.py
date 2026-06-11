"""DEPRECATED compatibility shim.

The maintenance logic moved into the hexagonal layout:

- alert engine  → ``leapconnect.domain.maintenance.engine``
- pack handling → ``leapconnect.domain.maintenance.packs``
- plan use case → ``leapconnect.application.maintenance``

This module re-exports the historical names and will be removed in a future
release.
"""

from __future__ import annotations

from leapconnect.application.maintenance import ensure_plan_generated
from leapconnect.domain.maintenance.engine import (
    DUE_SOON_DAYS,
    DUE_SOON_KM,
    compute_alert,
    compute_alerts,
    compute_cost_summary,
    due_soon_alerts,
    summarize,
)
from leapconnect.domain.maintenance.packs import (
    ITEM_FIELDS,
    OFFICIAL_REPO_URL,
    PACK_SCHEMA,
    factory_items_for_model,
    normalize_item,
    normalize_pack,
    official_pack_for_model,
    pack_applies_to_model,
)

__all__ = [
    "DUE_SOON_DAYS",
    "DUE_SOON_KM",
    "ITEM_FIELDS",
    "OFFICIAL_REPO_URL",
    "PACK_SCHEMA",
    "compute_alert",
    "compute_alerts",
    "compute_cost_summary",
    "due_soon_alerts",
    "ensure_plan_generated",
    "factory_items_for_model",
    "normalize_item",
    "normalize_pack",
    "official_pack_for_model",
    "pack_applies_to_model",
    "summarize",
]
