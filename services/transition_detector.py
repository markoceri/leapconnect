"""DEPRECATED compatibility shim.

Moved to ``leapconnect.domain.telemetry.transitions``.
"""

from __future__ import annotations

from leapconnect.domain.telemetry.transitions import (
    BOOLEAN_FIELDS,
    THRESHOLD_FIELDS,
    TransitionDetector,
)

__all__ = ["BOOLEAN_FIELDS", "THRESHOLD_FIELDS", "TransitionDetector"]
