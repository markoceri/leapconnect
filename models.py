"""DEPRECATED compatibility shim.

The persistence/domain models moved into ``leapconnect.domain.*`` as part of
the hexagonal-architecture refactoring. Import from there instead:

    from leapconnect.domain.telemetry import VehicleSnapshot

This module re-exports every historical name and will be removed in a future
release.
"""

from __future__ import annotations

from leapconnect.domain.charging.models import (
    ChargingPriceTier,
    ChargingSessionCost,
    ChargingTimeBand,
)
from leapconnect.domain.maintenance.models import (
    MaintenanceAlert,
    MaintenancePack,
    MaintenancePlanItem,
    MaintenanceRecord,
    MaintenanceRepo,
)
from leapconnect.domain.notifications.models import (
    Geofence,
    NotificationChannel,
    NotificationPreference,
    TelegramLinkToken,
    TelegramUser,
)
from leapconnect.domain.settings.models import (
    DEFAULT_INTERVAL_MINUTES,
    AbrpSettings,
    LiveRefreshSettings,
    MqttSettings,
    SchedulerSettings,
    UserPreferences,
)
from leapconnect.domain.telemetry.models import VehicleEvent, VehicleSnapshot

__all__ = [
    "DEFAULT_INTERVAL_MINUTES",
    "AbrpSettings",
    "ChargingPriceTier",
    "ChargingSessionCost",
    "ChargingTimeBand",
    "Geofence",
    "LiveRefreshSettings",
    "MaintenanceAlert",
    "MaintenancePack",
    "MaintenancePlanItem",
    "MaintenanceRecord",
    "MaintenanceRepo",
    "MqttSettings",
    "NotificationChannel",
    "NotificationPreference",
    "SchedulerSettings",
    "TelegramLinkToken",
    "TelegramUser",
    "UserPreferences",
    "VehicleEvent",
    "VehicleSnapshot",
]
