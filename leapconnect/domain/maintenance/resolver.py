"""Vehicle model resolver — maps API vehicle metadata to maintenance catalog entries.

For C10, auto-detection of BEV vs REEV is attempted first;
users can override via a persisted per-VIN preference.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from leapmotor_api.models import Vehicle

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known model keys and their matching patterns
# ---------------------------------------------------------------------------
MODEL_PATTERNS: list[tuple[str, str, list[str]]] = [
    # (canonical_key, display_name, [case-insensitive patterns to match car_type])
    ("T03", "Leapmotor T03", [r"t03"]),
    ("B10", "Leapmotor B10", [r"b10"]),
    ("C10", "Leapmotor C10", [r"c10"]),
]


# ---------------------------------------------------------------------------
# REEV detection heuristics for C10
# ---------------------------------------------------------------------------
def _detect_reev(vehicle: Vehicle) -> tuple[bool, float, str]:
    """Return (is_reev, confidence, reason)."""
    reasons: list[str] = []
    signals: list[bool] = []

    # Signal 1: allocation_code contains "REEV" or "HYBRID" or "EVR"
    if vehicle.allocation_code:
        ac = str(vehicle.allocation_code).upper()
        if "REEV" in ac or "HYBRID" in ac or "EVR" in ac:
            signals.append(True)
            reasons.append(f"allocation_code={vehicle.allocation_code}")
        elif "BEV" in ac or "PURE" in ac:
            signals.append(False)
            reasons.append(f"allocation_code={vehicle.allocation_code}")

    # Signal 2: abilities include fuel-related codes (engine, fuel heating etc.)
    # Ability codes: 40 = fuel heating (from DashboardTab.vue RIGHTS mapping)
    # 380 = fuel heating right in the rights system
    ability_ids = {int(a) for a in (vehicle.abilities or [])}
    has_fuel_ability = 40 in ability_ids
    if has_fuel_ability:
        signals.append(True)
        reasons.append("fuel_heating_ability=40")

    # Signal 3: car_type includes "REEV", "HYBRID", "EVR" or "BEV", "EV"
    ct = (vehicle.car_type or "").upper()
    if "REEV" in ct or "HYBRID" in ct or "EVR" in ct:
        signals.append(True)
        reasons.append(f"car_type={vehicle.car_type}")
    elif "BEV" in ct or ct in ("EV", "PURE EV", "PUREEV"):
        signals.append(False)
        reasons.append(f"car_type={vehicle.car_type}")

    # Signal 4: seat_layout or rudder clues (rare)
    seat = (vehicle.seat_layout or "").upper()
    if "REEV" in seat or "HYBRID" in seat:
        signals.append(True)
        reasons.append(f"seat_layout={vehicle.seat_layout}")

    if not signals:
        return False, 0.0, "no_reev_signals"

    true_count = sum(1 for s in signals if s)
    false_count = sum(1 for s in signals if not s)
    total = len(signals)
    confidence = max(true_count, false_count) / total if total > 0 else 0.0

    is_reev = true_count > false_count
    reason = "; ".join(reasons) if reasons else "heuristic_default"

    return is_reev, confidence, reason


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_model(vehicle: Vehicle) -> dict:
    """Return resolved model info for a vehicle.

    Returns a dict with:
      - model_key: canonical model key (T03, B10, C10, C10_REEV)
      - display_name: human-readable model name
      - variant: None or "reev"/"bev"
      - confidence: "high" | "medium" | "low" | "manual"
      - needs_confirmation: bool (True if user should confirm C10 variant)
      - detection_reason: string explaining the detection
    """
    car_type = (vehicle.car_type or "").strip()

    # Match against known patterns
    for model_key, display_name, patterns in MODEL_PATTERNS:
        for pat in patterns:
            if re.search(pat, car_type, re.IGNORECASE):
                # Found base model
                if model_key == "C10":
                    # Attempt REEV auto-detection
                    is_reev, conf, reason = _detect_reev(vehicle)
                    if is_reev and conf >= 0.66:
                        return {
                            "model_key": "C10_REEV",
                            "display_name": "Leapmotor C10 REEV",
                            "variant": "reev",
                            "confidence": "high" if conf >= 0.9 else "medium",
                            "needs_confirmation": False,
                            "detection_reason": reason,
                        }
                    elif not is_reev and conf >= 0.66:
                        return {
                            "model_key": "C10",
                            "display_name": "Leapmotor C10",
                            "variant": "bev",
                            "confidence": "high" if conf >= 0.9 else "medium",
                            "needs_confirmation": False,
                            "detection_reason": reason,
                        }
                    else:
                        # Ambiguous — ask user
                        return {
                            "model_key": "C10",
                            "display_name": "Leapmotor C10",
                            "variant": None,
                            "confidence": "low",
                            "needs_confirmation": True,
                            "detection_reason": reason
                            if reason
                            else "ambiguous_c10_variant",
                        }
                else:
                    # Non-C10 model — no variant resolution needed
                    return {
                        "model_key": model_key,
                        "display_name": display_name,
                        "variant": None,
                        "confidence": "high",
                        "needs_confirmation": False,
                        "detection_reason": f"matched_pattern={pat}",
                    }

    # Unknown model
    _LOGGER.warning("Unrecognised car_type=%r, VIN=%s", car_type, vehicle.vin)
    return {
        "model_key": "unknown",
        "display_name": car_type or "Unknown",
        "variant": None,
        "confidence": "low",
        "needs_confirmation": True,
        "detection_reason": "no_pattern_match",
    }
