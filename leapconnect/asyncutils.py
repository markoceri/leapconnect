"""Asyncio helpers shared across layers."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Coroutine

# Strong references to fire-and-forget tasks: the event loop only keeps weak
# references, so an otherwise-unreferenced task can be garbage-collected
# mid-flight and silently never complete.
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def spawn(coro: Coroutine, *, name: str | None = None) -> asyncio.Task:
    """``asyncio.create_task`` that keeps a reference until completion."""
    task = asyncio.create_task(coro, name=name)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task
