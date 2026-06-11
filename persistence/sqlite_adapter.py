"""DEPRECATED compatibility shim.

Moved to ``leapconnect.infrastructure.persistence.sqlite_adapter``.
"""

from leapconnect.infrastructure.persistence.sqlite_adapter import *  # noqa: F401,F403
from leapconnect.infrastructure.persistence.sqlite_adapter import (  # noqa: F401
    Base,
    SQLAlchemyVehicleHistoryRepository,
)
