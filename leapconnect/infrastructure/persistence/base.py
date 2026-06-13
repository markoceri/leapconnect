"""Shared plumbing for the per-context SQLAlchemy repositories."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from leapconnect.infrastructure.secrets import SecretCipher


class SqlRepositoryBase:
    """Holds the async session factory and secret cipher shared by all repos."""

    def __init__(
        self, session_factory: async_sessionmaker, cipher: SecretCipher
    ) -> None:
        self._session_factory = session_factory
        self._cipher = cipher
