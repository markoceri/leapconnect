"""Key/value settings and scheduler configuration (SQLAlchemy/SQLite)."""

from __future__ import annotations

from sqlalchemy import select

from leapconnect.application.ports.repositories import (
    SettingsRepository,
)
from leapconnect.domain.settings.models import SchedulerSettings
from leapconnect.infrastructure.persistence.base import SqlRepositoryBase
from leapconnect.infrastructure.persistence.tables import (
    AppSettingRow,
)


class SqlSettingsRepository(SqlRepositoryBase, SettingsRepository):
    """Key/value settings and scheduler configuration."""

    async def load_scheduler_settings(self) -> SchedulerSettings:
        """Load scheduler settings from the DB, returning defaults if missing."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(AppSettingRow).where(
                    AppSettingRow.key.in_(
                        [
                            "scheduler_enabled",
                            "scheduler_interval",
                            "scheduler_mqtt_interval_seconds",
                            "scheduler_rate_limit_seconds",
                            "scheduler_transition_detection_enabled",
                            "scheduler_transition_poll_interval",
                            "scheduler_transition_min_event_interval",
                        ]
                    )
                )
            )
            rows = {r.key: r.value for r in result.scalars().all()}

        return SchedulerSettings(
            enabled=rows.get("scheduler_enabled", "0") == "1",
            interval_minutes=int(rows.get("scheduler_interval", "15")),
            mqtt_interval_seconds=int(
                rows.get("scheduler_mqtt_interval_seconds", "60")
            ),
            rate_limit_seconds=int(rows.get("scheduler_rate_limit_seconds", "10")),
            transition_detection_enabled=rows.get(
                "scheduler_transition_detection_enabled", "1"
            )
            == "1",
            transition_poll_interval_seconds=int(
                rows.get("scheduler_transition_poll_interval", "10")
            ),
            transition_min_event_interval_seconds=int(
                rows.get("scheduler_transition_min_event_interval", "10")
            ),
        )

    async def save_scheduler_settings(self, settings: SchedulerSettings) -> None:
        """Persist scheduler settings (upsert)."""
        pairs = {
            "scheduler_enabled": "1" if settings.enabled else "0",
            "scheduler_interval": str(settings.interval_minutes),
            "scheduler_mqtt_interval_seconds": str(settings.mqtt_interval_seconds),
            "scheduler_rate_limit_seconds": str(settings.rate_limit_seconds),
            "scheduler_transition_detection_enabled": "1"
            if settings.transition_detection_enabled
            else "0",
            "scheduler_transition_poll_interval": str(
                settings.transition_poll_interval_seconds
            ),
            "scheduler_transition_min_event_interval": str(
                settings.transition_min_event_interval_seconds
            ),
        }
        async with self._session_factory() as session:
            for key, value in pairs.items():
                existing = await session.get(AppSettingRow, key)
                if existing:
                    existing.value = value
                else:
                    session.add(AppSettingRow(key=key, value=value))
            await session.commit()

    async def get_setting(self, key: str) -> str | None:
        """Get a single app setting value."""
        async with self._session_factory() as session:
            row = await session.get(AppSettingRow, key)
            return row.value if row else None

    async def save_setting(self, key: str, value: str) -> None:
        """Save a single app setting (upsert)."""
        async with self._session_factory() as session:
            existing = await session.get(AppSettingRow, key)
            if existing:
                existing.value = value
            else:
                session.add(AppSettingRow(key=key, value=value))
            await session.commit()
