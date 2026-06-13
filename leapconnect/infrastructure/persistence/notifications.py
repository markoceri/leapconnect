"""Notification persistence: channels, geofences, Telegram (SQLAlchemy/SQLite)."""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from leapconnect.application.ports.repositories import (
    NotificationRepository,
)
from leapconnect.domain.notifications.models import (
    Geofence,
    NotificationChannel,
    NotificationPreference,
    TelegramUser,
)
from leapconnect.infrastructure.persistence.base import SqlRepositoryBase
from leapconnect.infrastructure.persistence.tables import (
    GeofenceRow,
    NotificationChannelRow,
    NotificationPreferenceRow,
    TelegramLinkTokenRow,
    TelegramUserRow,
)

# Channel-config fields that are secrets and must be encrypted at rest.
_SECRET_CONFIG_KEYS = ("bot_token",)


class SqlNotificationRepository(SqlRepositoryBase, NotificationRepository):
    """Channels, preferences, geofences, Telegram users and link tokens."""

    def _config_to_json(self, config: dict) -> str:
        """Serialize a channel config, encrypting its secret fields."""
        stored = dict(config)
        for key in _SECRET_CONFIG_KEYS:
            if stored.get(key):
                stored[key] = self._cipher.encrypt(stored[key])
        return json.dumps(stored)

    def _config_from_json(self, config_json: str | None) -> dict:
        """Deserialize a channel config, decrypting its secret fields."""
        config = json.loads(config_json) if config_json else {}
        for key in _SECRET_CONFIG_KEYS:
            if config.get(key):
                config[key] = self._cipher.decrypt(config[key])
        return config

    async def get_notification_channels(self) -> list[NotificationChannel]:
        """Return all notification channels."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(NotificationChannelRow).order_by(NotificationChannelRow.id.asc())
            )
            rows = result.scalars().all()
        return [
            NotificationChannel(
                id=r.id,
                channel_type=r.channel_type,
                config=self._config_from_json(r.config_json),
                enabled=r.enabled,
                created_at=r.created_at,
            )
            for r in rows
        ]

    async def get_notification_channel(
        self, channel_id: int
    ) -> NotificationChannel | None:
        """Return a single notification channel by ID."""
        async with self._session_factory() as session:
            row = await session.get(NotificationChannelRow, channel_id)
            if not row:
                return None
            return NotificationChannel(
                id=row.id,
                channel_type=row.channel_type,
                config=self._config_from_json(row.config_json),
                enabled=row.enabled,
                created_at=row.created_at,
            )

    async def save_notification_channel(
        self, channel: NotificationChannel
    ) -> NotificationChannel:
        """Create or update a notification channel. Returns the saved channel."""
        async with self._session_factory() as session:
            if channel.id:
                row = await session.get(NotificationChannelRow, channel.id)
                if row:
                    row.channel_type = channel.channel_type
                    row.config_json = self._config_to_json(channel.config)
                    row.enabled = channel.enabled
                    await session.commit()
                    channel.id = row.id
                    return channel
            # Create new
            row = NotificationChannelRow(
                channel_type=channel.channel_type,
                config_json=self._config_to_json(channel.config),
                enabled=channel.enabled,
                created_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
            channel.id = row.id
            channel.created_at = row.created_at
            return channel

    async def delete_notification_channel(self, channel_id: int) -> bool:
        """Delete a notification channel and its preferences."""
        async with self._session_factory() as session:
            row = await session.get(NotificationChannelRow, channel_id)
            if not row:
                return False
            # Delete associated preferences
            prefs = await session.execute(
                select(NotificationPreferenceRow).where(
                    NotificationPreferenceRow.channel_id == channel_id
                )
            )
            for pref in prefs.scalars().all():
                await session.delete(pref)
            await session.delete(row)
            await session.commit()
            return True

    # -- notification preferences --------------------------------------------

    async def get_notification_preferences(
        self, channel_id: int
    ) -> list[NotificationPreference]:
        """Return all preferences for a channel."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(NotificationPreferenceRow).where(
                    NotificationPreferenceRow.channel_id == channel_id
                )
            )
            rows = result.scalars().all()
        return [
            NotificationPreference(
                id=r.id,
                channel_id=r.channel_id,
                event_type=r.event_type,
                enabled=r.enabled,
                config=json.loads(r.config_json) if r.config_json else None,
            )
            for r in rows
        ]

    async def save_notification_preferences(
        self, channel_id: int, preferences: list[NotificationPreference]
    ) -> None:
        """Upsert notification preferences for a channel (replaces all)."""
        async with self._session_factory() as session:
            # Delete existing
            existing = await session.execute(
                select(NotificationPreferenceRow).where(
                    NotificationPreferenceRow.channel_id == channel_id
                )
            )
            for row in existing.scalars().all():
                await session.delete(row)
            # Insert new
            for pref in preferences:
                session.add(
                    NotificationPreferenceRow(
                        channel_id=channel_id,
                        event_type=pref.event_type,
                        enabled=pref.enabled,
                        config_json=json.dumps(pref.config) if pref.config else None,
                    )
                )
            await session.commit()

    # -- geofences -----------------------------------------------------------

    async def get_geofences(self, vin: str | None = None) -> list[Geofence]:
        """Return geofences, optionally filtered by VIN."""
        conditions = []
        if vin:
            conditions.append((GeofenceRow.vin == vin) | (GeofenceRow.vin.is_(None)))
        stmt = select(GeofenceRow).order_by(GeofenceRow.id.asc())
        if conditions:
            stmt = stmt.where(*conditions)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [
            Geofence(
                id=r.id,
                vin=r.vin,
                name=r.name,
                shape_type=r.shape_type or "circle",
                latitude=r.latitude,
                longitude=r.longitude,
                radius_m=r.radius_m,
                points=json.loads(r.points_json) if r.points_json else None,
                notify_on_enter=r.notify_on_enter,
                notify_on_exit=r.notify_on_exit,
                enabled=r.enabled,
            )
            for r in rows
        ]

    async def save_geofence(self, geofence: Geofence) -> Geofence:
        """Create or update a geofence."""
        async with self._session_factory() as session:
            if geofence.id:
                row = await session.get(GeofenceRow, geofence.id)
                if row:
                    row.vin = geofence.vin
                    row.name = geofence.name
                    row.shape_type = geofence.shape_type
                    row.latitude = geofence.latitude
                    row.longitude = geofence.longitude
                    row.radius_m = geofence.radius_m
                    row.points_json = (
                        json.dumps(geofence.points) if geofence.points else None
                    )
                    row.notify_on_enter = geofence.notify_on_enter
                    row.notify_on_exit = geofence.notify_on_exit
                    row.enabled = geofence.enabled
                    await session.commit()
                    return geofence
            # Create new
            row = GeofenceRow(
                vin=geofence.vin,
                name=geofence.name,
                shape_type=geofence.shape_type,
                latitude=geofence.latitude,
                longitude=geofence.longitude,
                radius_m=geofence.radius_m,
                points_json=json.dumps(geofence.points) if geofence.points else None,
                notify_on_enter=geofence.notify_on_enter,
                notify_on_exit=geofence.notify_on_exit,
                enabled=geofence.enabled,
            )
            session.add(row)
            await session.commit()
            geofence.id = row.id
            return geofence

    async def delete_geofence(self, geofence_id: int) -> bool:
        """Delete a geofence by ID."""
        async with self._session_factory() as session:
            row = await session.get(GeofenceRow, geofence_id)
            if not row:
                return False
            await session.delete(row)
            await session.commit()
            return True

    # -- telegram users ------------------------------------------------------

    async def get_telegram_users(self, status: str | None = None) -> list[TelegramUser]:
        """Return all telegram users, optionally filtered by status."""
        async with self._session_factory() as session:
            stmt = select(TelegramUserRow)
            if status:
                stmt = stmt.where(TelegramUserRow.status == status)
            stmt = stmt.order_by(TelegramUserRow.created_at.desc())
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                TelegramUser(
                    id=r.id,
                    chat_id=r.chat_id,
                    username=r.username,
                    first_name=r.first_name,
                    last_name=r.last_name,
                    status=r.status,
                    linked_token=r.linked_token,
                    created_at=r.created_at,
                    approved_at=r.approved_at,
                )
                for r in rows
            ]

    async def get_telegram_user_by_chat_id(self, chat_id: str) -> TelegramUser | None:
        """Return a single telegram user by chat_id, or None."""
        async with self._session_factory() as session:
            stmt = select(TelegramUserRow).where(TelegramUserRow.chat_id == chat_id)
            result = await session.execute(stmt)
            r = result.scalar_one_or_none()
            if not r:
                return None
            return TelegramUser(
                id=r.id,
                chat_id=r.chat_id,
                username=r.username,
                first_name=r.first_name,
                last_name=r.last_name,
                status=r.status,
                linked_token=r.linked_token,
                created_at=r.created_at,
                approved_at=r.approved_at,
            )

    async def save_telegram_user(self, user: TelegramUser) -> TelegramUser:
        """Create or update a telegram user."""
        async with self._session_factory() as session:
            # Check if user already exists
            stmt = select(TelegramUserRow).where(
                TelegramUserRow.chat_id == user.chat_id
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                row.username = user.username
                row.first_name = user.first_name
                row.last_name = user.last_name
                row.status = user.status
                row.linked_token = user.linked_token
                row.approved_at = user.approved_at
            else:
                row = TelegramUserRow(
                    chat_id=user.chat_id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    status=user.status,
                    linked_token=user.linked_token,
                    created_at=user.created_at or datetime.now(UTC),
                    approved_at=user.approved_at,
                )
                session.add(row)
            await session.commit()
            user.id = row.id
            return user

    async def update_telegram_user_status(self, chat_id: str, status: str) -> bool:
        """Update status of a telegram user. Returns False if not found."""
        async with self._session_factory() as session:
            stmt = select(TelegramUserRow).where(TelegramUserRow.chat_id == chat_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return False
            row.status = status
            if status == "approved":
                row.approved_at = datetime.now(UTC)
            await session.commit()
            return True

    async def delete_telegram_user(self, chat_id: str) -> bool:
        """Remove a telegram user entirely."""
        async with self._session_factory() as session:
            stmt = select(TelegramUserRow).where(TelegramUserRow.chat_id == chat_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def get_approved_chat_ids(self) -> set[str]:
        """Return the set of all approved Telegram chat IDs."""
        async with self._session_factory() as session:
            stmt = select(TelegramUserRow.chat_id).where(
                TelegramUserRow.status == "approved"
            )
            result = await session.execute(stmt)
            return {r[0] for r in result.all()}

    # -- telegram link tokens ------------------------------------------------

    async def create_link_token(self, expires_minutes: int = 10) -> str:
        """Generate a new deep-link token. Returns the token string."""
        token = secrets.token_urlsafe(24)
        now = datetime.now(UTC).replace(tzinfo=None)
        row = TelegramLinkTokenRow(
            token=token,
            created_at=now,
            expires_at=now + timedelta(minutes=expires_minutes),
            used=False,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
        return token

    async def validate_link_token(self, token: str) -> bool:
        """Validate and consume a token. Returns True if valid."""
        async with self._session_factory() as session:
            stmt = select(TelegramLinkTokenRow).where(
                TelegramLinkTokenRow.token == token
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return False
            if row.used:
                return False
            if row.expires_at < datetime.now(UTC).replace(tzinfo=None):
                return False
            row.used = True
            await session.commit()
            return True
