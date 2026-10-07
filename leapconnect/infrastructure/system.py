"""Host system probes (disk space) backed by the standard library."""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterable
from pathlib import Path

from leapconnect.domain.system import DiskUsage


def _existing(path: Path) -> Path | None:
    """The path itself or its nearest existing ancestor."""
    for candidate in (path, *path.parents):
        if candidate.exists():
            return candidate
    return None


def read_disk_usage(paths: Iterable[Path | str]) -> list[DiskUsage]:
    """Usage of each distinct filesystem holding one of ``paths``.

    Paths on the same device are reported once; missing paths resolve to
    their nearest existing parent (e.g. a data dir not created yet).
    """
    usages: list[DiskUsage] = []
    seen: set[int] = set()
    for raw in paths:
        path = _existing(Path(raw).resolve())
        if path is None:
            continue
        if path.is_file():
            path = path.parent  # report the directory, e.g. for the DB file
        dev = os.stat(path).st_dev
        if dev in seen:
            continue
        seen.add(dev)
        total, _used, free = shutil.disk_usage(path)
        usages.append(DiskUsage(path=str(path), total_bytes=total, free_bytes=free))
    return usages
