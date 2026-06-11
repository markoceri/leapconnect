"""Persistence ports (driven-side interfaces).

Concrete adapters (e.g. ``leapconnect.infrastructure.persistence``) implement
these. The interfaces are segregated per bounded context; the combined
``VehicleHistoryRepository`` is what the composition root wires today.
"""

from __future__ import annotations

import abc
from datetime import datetime  # noqa: F401  (used in signatures)
from typing import Any

from leapconnect.domain.charging.models import (
    ChargingPriceTier,
    ChargingSessionCost,
    ChargingTimeBand,
)
from leapconnect.domain.notifications.models import (
    Geofence,
    NotificationChannel,
    NotificationPreference,
    TelegramUser,
)
from leapconnect.domain.settings.models import SchedulerSettings
from leapconnect.domain.telemetry.models import (
    VehicleEvent,
    VehicleSnapshot,
)


class TelemetryRepository(abc.ABC):
    """Telemetry persistence: snapshots, events, history queries."""

    @abc.abstractmethod
    async def init_db(self) -> None: ...

    @abc.abstractmethod
    async def close(self) -> None: ...

    @abc.abstractmethod
    async def save_snapshot(self, snapshot: VehicleSnapshot) -> None: ...

    @abc.abstractmethod
    async def save_event(self, event: VehicleEvent) -> None:
        """Persist a single state-transition event."""

    @abc.abstractmethod
    async def get_events(
        self, vin: str, *, days: int = 30, event_type: str | None = None
    ) -> list[VehicleEvent]:
        """Return events for *vin* over the last *days* days."""

    @abc.abstractmethod
    async def get_history(
        self,
        vin: str,
        *,
        days: int = 30,
        from_date: str | None = None,
        to_date: str | None = None,
        max_points: int | None = None,
    ) -> list[VehicleSnapshot]: ...

    @abc.abstractmethod
    async def get_daily_summary(
        self, vin: str, *, days: int = 30
    ) -> list[dict[str, Any]]: ...


class SettingsRepository(abc.ABC):
    """Key/value settings and scheduler configuration."""

    @abc.abstractmethod
    async def load_scheduler_settings(self) -> SchedulerSettings:
        """Load scheduler settings from the DB, returning defaults if missing."""

    @abc.abstractmethod
    async def save_scheduler_settings(self, settings: SchedulerSettings) -> None:
        """Persist scheduler settings (upsert)."""

    @abc.abstractmethod
    async def get_setting(self, key: str) -> str | None:
        """Get a single app setting value."""

    @abc.abstractmethod
    async def save_setting(self, key: str, value: str) -> None:
        """Save a single app setting (upsert)."""


class AccountRepository(abc.ABC):
    """Leapmotor account credentials and the local dashboard user."""

    @abc.abstractmethod
    async def save_account(
        self,
        username: str,
        password: str,
        cert_path: str,
        key_path: str,
        p12_password: str | None = None,
    ) -> None:
        """Save or update account credentials."""

    @abc.abstractmethod
    async def get_account(self) -> dict | None:
        """Return the first saved account or None."""

    @abc.abstractmethod
    async def delete_account(self, username: str) -> None:
        """Remove an account."""

    @abc.abstractmethod
    async def create_user(self, display_name: str, password: str) -> dict:
        """Create a new LeapConnect user. Returns user dict."""

    @abc.abstractmethod
    async def get_user(self) -> dict | None:
        """Return the first LeapConnect user or None."""

    @abc.abstractmethod
    async def verify_user_password(self, password: str) -> bool:
        """Verify the LeapConnect user password."""

    @abc.abstractmethod
    async def update_user(
        self, display_name: str | None = None, password: str | None = None
    ) -> dict | None:
        """Update LeapConnect user display name and/or password."""


class NotificationRepository(abc.ABC):
    """Notification channels, preferences, geofences, Telegram users."""

    @abc.abstractmethod
    async def get_notification_channels(self) -> list[NotificationChannel]:
        """Return all notification channels."""

    @abc.abstractmethod
    async def get_notification_channel(
        self, channel_id: int
    ) -> NotificationChannel | None:
        """Return a single notification channel by ID."""

    @abc.abstractmethod
    async def save_notification_channel(
        self, channel: NotificationChannel
    ) -> NotificationChannel:
        """Create or update a notification channel. Returns the saved channel."""

    @abc.abstractmethod
    async def delete_notification_channel(self, channel_id: int) -> bool:
        """Delete a notification channel and its preferences."""

    @abc.abstractmethod
    async def get_notification_preferences(
        self, channel_id: int
    ) -> list[NotificationPreference]:
        """Return all preferences for a channel."""

    @abc.abstractmethod
    async def save_notification_preferences(
        self, channel_id: int, preferences: list[NotificationPreference]
    ) -> None:
        """Upsert notification preferences for a channel (replaces all)."""

    @abc.abstractmethod
    async def get_geofences(self, vin: str | None = None) -> list[Geofence]:
        """Return geofences, optionally filtered by VIN."""

    @abc.abstractmethod
    async def save_geofence(self, geofence: Geofence) -> Geofence:
        """Create or update a geofence."""

    @abc.abstractmethod
    async def delete_geofence(self, geofence_id: int) -> bool:
        """Delete a geofence by ID."""

    @abc.abstractmethod
    async def get_telegram_users(self, status: str | None = None) -> list[TelegramUser]:
        """Return all telegram users, optionally filtered by status."""

    @abc.abstractmethod
    async def get_telegram_user_by_chat_id(self, chat_id: str) -> TelegramUser | None:
        """Return a single telegram user by chat_id, or None."""

    @abc.abstractmethod
    async def save_telegram_user(self, user: TelegramUser) -> TelegramUser:
        """Create or update a telegram user."""

    @abc.abstractmethod
    async def update_telegram_user_status(self, chat_id: str, status: str) -> bool:
        """Update status of a telegram user. Returns False if not found."""

    @abc.abstractmethod
    async def delete_telegram_user(self, chat_id: str) -> bool:
        """Remove a telegram user entirely."""

    @abc.abstractmethod
    async def get_approved_chat_ids(self) -> set[str]:
        """Return the set of all approved Telegram chat IDs."""

    @abc.abstractmethod
    async def create_link_token(self, expires_minutes: int = 10) -> str:
        """Generate a new deep-link token. Returns the token string."""

    @abc.abstractmethod
    async def validate_link_token(self, token: str) -> bool:
        """Validate and consume a token. Returns True if valid."""


class ChargingRepository(abc.ABC):
    """Charging price tiers, time-of-use bands and session costs."""

    @abc.abstractmethod
    async def get_price_tiers(self) -> list[ChargingPriceTier]:
        """Return all charging price tiers."""

    @abc.abstractmethod
    async def upsert_price_tier(self, tier: ChargingPriceTier) -> ChargingPriceTier:
        """Create or update a price tier."""

    @abc.abstractmethod
    async def get_time_bands(
        self, tier_id: str = "home_grid"
    ) -> list[ChargingTimeBand]:
        """Return time bands for a tier, ordered by position."""

    @abc.abstractmethod
    async def upsert_time_band(self, band: ChargingTimeBand) -> ChargingTimeBand:
        """Create or update a time band."""

    @abc.abstractmethod
    async def delete_time_band(self, band_id: int) -> bool:
        """Delete a time band by ID."""

    @abc.abstractmethod
    async def get_session_costs(
        self, vin: str, *, start: datetime | None = None, end: datetime | None = None
    ) -> list[ChargingSessionCost]:
        """Return session costs for a VIN, optionally filtered by date range."""

    @abc.abstractmethod
    async def upsert_session_cost(self, sc: ChargingSessionCost) -> ChargingSessionCost:
        """Create or update a session cost record."""

    @abc.abstractmethod
    async def delete_session_cost(self, cost_id: int) -> bool:
        """Delete a session cost record."""


class MaintenanceRepository(abc.ABC):
    """Maintenance plan, records, community repos and cached packs."""

    @abc.abstractmethod
    async def get_maintenance_plan(self, vin: str) -> list:
        """Return all plan items for a vehicle, ordered by priority then category."""

    @abc.abstractmethod
    async def upsert_maintenance_plan_item(self, vin: str, item) -> None:
        """Insert or update a single plan item (keyed by vin + service_type)."""

    @abc.abstractmethod
    async def set_plan_item_last_done(
        self, vin: str, service_type: str, *, last_done_km, last_done_date
    ) -> None:
        """Set a plan item's last_done fields explicitly (``None`` clears them)."""

    @abc.abstractmethod
    async def get_maintenance_records(
        self, vin: str, *, service_type: str | None = None, limit: int | None = 20
    ) -> list:
        """Return completed maintenance records, newest first (``limit=None`` = all)."""

    @abc.abstractmethod
    async def save_maintenance_record(self, record) -> None:
        """Persist a completed maintenance record."""

    @abc.abstractmethod
    async def update_maintenance_record(
        self,
        record_id: int,
        *,
        timestamp=None,
        mileage_km=None,
        cost=None,
        provider=None,
        notes=None,
    ) -> object | None:
        """Update an existing record's editable fields. Returns it, or None."""

    @abc.abstractmethod
    async def delete_maintenance_record(self, record_id: int) -> None:
        """Delete a maintenance record by id."""

    @abc.abstractmethod
    async def get_maintenance_record(self, record_id: int) -> object | None:
        """Get a single maintenance record by id."""

    @abc.abstractmethod
    async def delete_maintenance_plan_item(self, vin: str, service_type: str) -> None:
        """Delete a single plan item (keyed by vin + service_type)."""

    @abc.abstractmethod
    async def list_maintenance_repos(self) -> list: ...

    @abc.abstractmethod
    async def get_maintenance_repo(self, repo_id: int): ...

    @abc.abstractmethod
    async def get_maintenance_repo_by_url(self, url: str): ...

    @abc.abstractmethod
    async def save_maintenance_repo(self, repo):
        """Insert or update a repo (keyed by id when set, else by url)."""

    @abc.abstractmethod
    async def delete_maintenance_repo(self, repo_id: int) -> None:
        """Delete a repo and all packs cached from it."""

    @abc.abstractmethod
    async def list_maintenance_packs(self, repo_id: int | None = None) -> list: ...

    @abc.abstractmethod
    async def get_maintenance_pack(self, pack_id: int): ...

    @abc.abstractmethod
    async def save_maintenance_pack(self, pack):
        """Insert or update a cached pack (keyed by id, or repo_id + slug)."""

    @abc.abstractmethod
    async def delete_maintenance_pack(self, pack_id: int) -> None: ...


class VehicleHistoryRepository(
    TelemetryRepository,
    SettingsRepository,
    AccountRepository,
    NotificationRepository,
    ChargingRepository,
    MaintenanceRepository,
):
    """Combined persistence port implemented by the SQLite adapter."""
