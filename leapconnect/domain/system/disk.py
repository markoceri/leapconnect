"""Disk-space health: usage snapshot and low-space alert rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

GB = 1024**3

# While space stays low, the alert is repeated at most this often.
LOW_DISK_REMINDER = timedelta(hours=24)


@dataclass
class DiskAlertSettings:
    """Global low-disk thresholds (``0`` disables one; both ``0`` = off)."""

    min_free_gb: float = 1.0
    min_free_percent: float = 10.0

    @property
    def enabled(self) -> bool:
        return self.min_free_gb > 0 or self.min_free_percent > 0

    def describe(self) -> str:
        """Human-readable thresholds, e.g. ``below 1 GB or 10%``."""
        parts = []
        if self.min_free_gb > 0:
            parts.append(f"{self.min_free_gb:g} GB")
        if self.min_free_percent > 0:
            parts.append(f"{self.min_free_percent:g}%")
        return "below " + " or ".join(parts) if parts else "off"


@dataclass(frozen=True)
class DiskUsage:
    """Free/total space of the filesystem holding a path."""

    path: str
    total_bytes: int
    free_bytes: int

    @property
    def free_gb(self) -> float:
        return self.free_bytes / GB

    @property
    def total_gb(self) -> float:
        return self.total_bytes / GB

    @property
    def free_percent(self) -> float:
        return self.free_bytes / self.total_bytes * 100 if self.total_bytes else 0.0


def is_low_disk(usage: DiskUsage, limits: DiskAlertSettings) -> bool:
    """True when free space is under either threshold (``0`` disables one)."""
    below_gb = limits.min_free_gb > 0 and usage.free_gb < limits.min_free_gb
    below_pct = (
        limits.min_free_percent > 0 and usage.free_percent < limits.min_free_percent
    )
    return below_gb or below_pct


def low_disk_alert_due(
    is_low: bool,
    last_sent: datetime | None,
    now: datetime,
    reminder: timedelta = LOW_DISK_REMINDER,
) -> bool:
    """Alert on the first low reading, then once per ``reminder`` while low.

    Callers reset ``last_sent`` when space recovers, re-arming the alert.
    """
    if not is_low:
        return False
    return last_sent is None or now - last_sent >= reminder
