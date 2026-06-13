"""Transition detector — detects state changes in vehicle telemetry.

Compares fresh vehicle status against previously-seen state per VIN and
emits VehicleEvent objects when watched fields change. Includes per-field
deduplication to prevent flooding during rapid oscillations.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from leapconnect.domain.telemetry.models import VehicleEvent

if TYPE_CHECKING:
    from leapmotor_api.models import VehicleStatus

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Watched field definitions
# ---------------------------------------------------------------------------

# Boolean fields: emit event on any True<->False transition
BOOLEAN_FIELDS: list[dict] = [
    {
        "attr_path": "is_regening",
        "field_name": "is_regening",
        "event_true": "regen_start",
        "event_false": "regen_stop",
    },
    {
        "attr_path": "is_charging",
        "field_name": "is_charging",
        "event_true": "charge_start",
        "event_false": "charge_stop",
    },
    {
        "attr_path": "is_plugged",
        "field_name": "is_plugged",
        "event_true": "plugged_in",
        "event_false": "unplugged",
    },
    {
        "attr_path": "is_parked",
        "field_name": "is_parked",
        "event_true": "parked",
        "event_false": "driving_start",
    },
    {
        "attr_path": "is_locked",
        "field_name": "is_locked",
        "event_true": "locked",
        "event_false": "unlocked",
    },
    {
        "attr_path": "ignition.bcm_key_position_on3",
        "field_name": "ignition_on3",
        "event_true": "ignition_on",
        "event_false": "ignition_off",
    },
]

# Threshold fields: emit event when value crosses a boundary
THRESHOLD_FIELDS: list[dict] = [
    {
        "attr_path": "driving.speed",
        "field_name": "speed",
        "threshold": 0,
        "mode": "crosses_zero",  # emits when crossing 0 in either direction
        "event_above": "moving_start",
        "event_below": "moving_stop",
    },
    {
        "attr_path": "battery.soc",
        "field_name": "battery_soc",
        "mode": "delta",  # emits when absolute change >= delta_threshold
        "delta_threshold": 5,
        "event_type": "soc_change",
    },
    {
        "attr_path": "battery.charge_state",
        "field_name": "charge_state",
        "mode": "any_change",  # emits on any value change
        "event_type": "charge_state_change",
    },
]


def _get_nested_attr(obj, attr_path: str):
    """Safely get a nested attribute like 'driving.speed' from an object."""
    parts = attr_path.split(".")
    current = obj
    for part in parts:
        if current is None:
            return None
        current = getattr(current, part, None)
    return current


class TransitionDetector:
    """Detects state transitions in vehicle status and emits events."""

    def __init__(self, min_event_interval_seconds: int = 10) -> None:
        self._min_interval = min_event_interval_seconds
        # vin -> {field_name: last_known_value}
        self._previous_states: dict[str, dict[str, object]] = {}
        # vin -> {field_name: last_event_timestamp}
        self._last_event_times: dict[str, dict[str, float]] = {}

    @property
    def min_event_interval_seconds(self) -> int:
        return self._min_interval

    @min_event_interval_seconds.setter
    def min_event_interval_seconds(self, value: int) -> None:
        self._min_interval = max(1, value)

    def detect(self, vin: str, status: VehicleStatus) -> list[VehicleEvent]:
        """Compare current status against previous state and return events.

        Updates internal state tracking after comparison.
        """
        now = datetime.now(UTC)
        events: list[VehicleEvent] = []

        prev = self._previous_states.get(vin, {})
        times = self._last_event_times.setdefault(vin, {})

        new_state: dict[str, object] = {}

        # --- Boolean fields ---
        for field_def in BOOLEAN_FIELDS:
            field_name = field_def["field_name"]
            current_val = _get_nested_attr(status, field_def["attr_path"])
            new_state[field_name] = current_val

            if field_name not in prev:
                # First observation — no transition to report
                continue

            old_val = prev[field_name]
            if current_val == old_val or current_val is None:
                continue

            # Dedup check
            if not self._can_emit(times, field_name):
                continue

            event_type = (
                field_def["event_true"] if current_val else field_def["event_false"]
            )
            events.append(
                VehicleEvent(
                    vin=vin,
                    timestamp=now,
                    event_type=event_type,
                    field_name=field_name,
                    old_value=str(old_val) if old_val is not None else None,
                    new_value=str(current_val),
                )
            )
            times[field_name] = time.monotonic()
            _LOGGER.info(
                "Transition detected [%s] %s: %s -> %s (%s)",
                vin,
                field_name,
                old_val,
                current_val,
                event_type,
            )

        # --- Threshold fields ---
        for field_def in THRESHOLD_FIELDS:
            field_name = field_def["field_name"]
            current_val = _get_nested_attr(status, field_def["attr_path"])
            # Normalize enum values
            if hasattr(current_val, "value"):
                current_val = current_val.value
            new_state[field_name] = current_val

            if field_name not in prev:
                continue

            old_val = prev[field_name]
            if current_val is None or old_val is None:
                continue
            if current_val == old_val:
                continue

            mode = field_def["mode"]
            event: VehicleEvent | None = None

            if mode == "crosses_zero":
                # Only emit if the value crosses zero
                old_above = old_val > 0
                cur_above = current_val > 0
                if old_above == cur_above:
                    continue
                if not self._can_emit(times, field_name):
                    continue
                event_type = (
                    field_def["event_above"] if cur_above else field_def["event_below"]
                )
                event = VehicleEvent(
                    vin=vin,
                    timestamp=now,
                    event_type=event_type,
                    field_name=field_name,
                    old_value=str(old_val),
                    new_value=str(current_val),
                )

            elif mode == "delta":
                delta = abs(current_val - old_val)
                if delta < field_def["delta_threshold"]:
                    continue
                if not self._can_emit(times, field_name):
                    continue
                event = VehicleEvent(
                    vin=vin,
                    timestamp=now,
                    event_type=field_def["event_type"],
                    field_name=field_name,
                    old_value=str(old_val),
                    new_value=str(current_val),
                )

            elif mode == "any_change":
                if not self._can_emit(times, field_name):
                    continue
                event = VehicleEvent(
                    vin=vin,
                    timestamp=now,
                    event_type=field_def["event_type"],
                    field_name=field_name,
                    old_value=str(old_val),
                    new_value=str(current_val),
                )

            if event:
                events.append(event)
                times[field_name] = time.monotonic()
                _LOGGER.info(
                    "Transition detected [%s] %s: %s -> %s (%s)",
                    vin,
                    field_name,
                    old_val,
                    current_val,
                    event.event_type,
                )

        # Update stored state
        self._previous_states[vin] = new_state

        return events

    def _can_emit(self, times: dict[str, float], field_name: str) -> bool:
        """Check if enough time has passed since last event for this field."""
        last = times.get(field_name)
        if last is None:
            return True
        return (time.monotonic() - last) >= self._min_interval
