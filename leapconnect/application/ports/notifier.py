"""Notification system — abstract notifier interface and registry."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

_LOGGER = logging.getLogger(__name__)


@dataclass
class Notification:
    """A notification to be sent via a channel."""

    event_type: str
    title: str
    body: str  # HTML-formatted body text
    vin: str | None = None
    vehicle_name: str | None = None
    image: bytes | None = None  # PNG image bytes (optional)
    timestamp: datetime | None = None
    extra: dict = field(default_factory=dict)


class BaseNotifier(ABC):
    """Abstract base class for notification channels."""

    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """Send a text notification. Returns True on success."""
        ...

    @abstractmethod
    async def send_photo(self, notification: Notification) -> bool:
        """Send a notification with an attached photo. Returns True on success."""
        ...

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """Test the channel configuration. Returns (success, message)."""
        ...
