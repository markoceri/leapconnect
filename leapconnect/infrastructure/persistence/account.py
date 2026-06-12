"""Leapmotor account credentials and the local LeapConnect user (SQLAlchemy/SQLite)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import select

from leapconnect.application.ports.repositories import (
    AccountRepository,
)
from leapconnect.infrastructure.persistence.base import SqlRepositoryBase
from leapconnect.infrastructure.persistence.tables import (
    AccountRow,
    LeapConnectUserRow,
)


class SqlAccountRepository(SqlRepositoryBase, AccountRepository):
    """Leapmotor account credentials and the local LeapConnect user."""

    async def save_account(
        self,
        username: str,
        password: str,
        cert_path: str,
        key_path: str,
        p12_password: str | None = None,
    ) -> None:
        """Save or update account credentials."""
        async with self._session_factory() as session:
            stmt = select(AccountRow).where(AccountRow.username == username)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                existing.password = password
                existing.cert_path = cert_path
                existing.key_path = key_path
                existing.p12_password = p12_password
            else:
                session.add(
                    AccountRow(
                        username=username,
                        password=password,
                        cert_path=cert_path,
                        key_path=key_path,
                        p12_password=p12_password,
                        created_at=datetime.now(UTC),
                    )
                )
            await session.commit()

    async def get_account(self) -> dict | None:
        """Return the first saved account or None."""
        async with self._session_factory() as session:
            stmt = select(AccountRow).order_by(AccountRow.id.asc()).limit(1)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return None
            return {
                "username": row.username,
                "password": row.password,
                "cert_path": row.cert_path,
                "key_path": row.key_path,
                "p12_password": row.p12_password,
            }

    async def delete_account(self, username: str) -> None:
        """Remove an account."""
        async with self._session_factory() as session:
            stmt = select(AccountRow).where(AccountRow.username == username)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                await session.delete(row)
                await session.commit()

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 100_000
        ).hex()

    async def create_user(self, display_name: str, password: str) -> dict:
        """Create a new LeapConnect user. Returns user dict."""
        salt = secrets.token_hex(16)
        pw_hash = self._hash_password(password, salt)
        async with self._session_factory() as session:
            row = LeapConnectUserRow(
                display_name=display_name,
                password_hash=pw_hash,
                salt=salt,
                created_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
            return {"id": row.id, "display_name": row.display_name}

    async def get_user(self) -> dict | None:
        """Return the first LeapConnect user or None."""
        async with self._session_factory() as session:
            stmt = (
                select(LeapConnectUserRow)
                .order_by(LeapConnectUserRow.id.asc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return None
            return {"id": row.id, "display_name": row.display_name}

    async def verify_user_password(self, password: str) -> bool:
        """Verify the LeapConnect user password."""
        async with self._session_factory() as session:
            stmt = (
                select(LeapConnectUserRow)
                .order_by(LeapConnectUserRow.id.asc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return False
            return self._hash_password(password, row.salt) == row.password_hash

    async def update_user(
        self, display_name: str | None = None, password: str | None = None
    ) -> dict | None:
        """Update LeapConnect user display name and/or password."""
        async with self._session_factory() as session:
            stmt = (
                select(LeapConnectUserRow)
                .order_by(LeapConnectUserRow.id.asc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return None
            if display_name is not None:
                row.display_name = display_name
            if password is not None:
                row.salt = secrets.token_hex(16)
                row.password_hash = self._hash_password(password, row.salt)
            await session.commit()
            return {"id": row.id, "display_name": row.display_name}
