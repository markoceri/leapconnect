"""In-memory ring-buffer log handler for the frontend log viewer."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime


class RingBufferHandler(logging.Handler):
    """Keeps the last N log records in memory and notifies WebSocket clients."""

    def __init__(self, capacity: int = 2000) -> None:
        super().__init__()
        self._buffer: deque[dict] = deque(maxlen=capacity)
        self._ws_clients: set = set()  # objects with an async send_json(dict)
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Store reference to the main asyncio event loop."""
        self._loop = loop

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "ts": datetime.fromtimestamp(record.created).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "name": record.name,
            "message": self.format(record),
        }
        self._buffer.append(entry)
        # Schedule broadcast to connected WS clients
        loop = self._loop
        if not loop or not self._ws_clients:
            return
        for ws in list(self._ws_clients):
            try:
                loop.call_soon_threadsafe(loop.create_task, ws.send_json(entry))
            except Exception:
                self._ws_clients.discard(ws)

    def get_entries(self, limit: int = 200) -> list[dict]:
        """Return the last *limit* log entries."""
        entries = list(self._buffer)
        return entries[-limit:]

    def register_ws(self, ws) -> None:
        self._ws_clients.add(ws)

    def unregister_ws(self, ws) -> None:
        self._ws_clients.discard(ws)
