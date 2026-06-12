"""Shared plumbing for the per-context SQLAlchemy repositories."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker


class SqlRepositoryBase:
    """Holds the async session factory shared by all context repositories."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory
