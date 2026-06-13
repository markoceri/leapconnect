"""Notification event catalog and message templates (domain).

Defines every notification event the system can emit, its configuration
schema, and the human-readable message templates.
"""

from __future__ import annotations

EVENT_CATALOG: list[dict] = [
    # Charging
    {
        "event_type": "charge_start",
        "label": "Charging started",
        "description": "Notify when the vehicle starts charging",
        "category": "charging",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "charge_stop",
        "label": "Charging stopped",
        "description": "Notify when charging ends",
        "category": "charging",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "charge_interrupted",
        "label": "Charging interrupted",
        "description": "Notify if charging stops before reaching the SOC target",
        "category": "charging",
        "has_image": True,
        "configurable": True,
        "config_schema": {
            "soc_target": {
                "label": "Target SOC",
                "type": "number",
                "default": 80,
                "min": 20,
                "max": 100,
                "unit": "%",
            }
        },
    },
    {
        "event_type": "soc_threshold_high",
        "label": "SOC above threshold",
        "description": "Notify when the SOC rises above the configured threshold",
        "category": "charging",
        "has_image": True,
        "configurable": True,
        "config_schema": {
            "threshold": {
                "label": "SOC threshold",
                "type": "number",
                "default": 80,
                "min": 10,
                "max": 100,
                "unit": "%",
            }
        },
    },
    {
        "event_type": "soc_threshold_low",
        "label": "SOC below threshold",
        "description": "Notify when the SOC drops below the configured threshold",
        "category": "charging",
        "has_image": True,
        "configurable": True,
        "config_schema": {
            "threshold": {
                "label": "SOC threshold",
                "type": "number",
                "default": 20,
                "min": 5,
                "max": 90,
                "unit": "%",
            }
        },
    },
    {
        "event_type": "plugged_in",
        "label": "Plugged in",
        "description": "Notify when the charging cable is connected",
        "category": "charging",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "unplugged",
        "label": "Unplugged",
        "description": "Notify when the charging cable is disconnected",
        "category": "charging",
        "has_image": True,
        "configurable": False,
    },
    # Driving
    {
        "event_type": "driving_start",
        "label": "Driving started",
        "description": "Notify when the vehicle starts moving",
        "category": "driving",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "parked",
        "label": "Vehicle parked",
        "description": "Notify when the vehicle is parked",
        "category": "driving",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "ignition_on",
        "label": "Ignition on",
        "description": "Notify when the vehicle is turned on",
        "category": "driving",
        "has_image": False,
        "configurable": False,
    },
    {
        "event_type": "ignition_off",
        "label": "Ignition off",
        "description": "Notify when the vehicle is turned off",
        "category": "driving",
        "has_image": False,
        "configurable": False,
    },
    # Security
    {
        "event_type": "locked",
        "label": "Vehicle locked",
        "description": "Notify when the vehicle is locked",
        "category": "security",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "unlocked",
        "label": "Vehicle unlocked",
        "description": "Notify when the vehicle is unlocked",
        "category": "security",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "movement_alert",
        "label": "Movement alert",
        "description": "Notify if the vehicle moves while parked and off (anti-theft)",
        "category": "security",
        "has_image": True,
        "configurable": True,
        "config_schema": {
            "distance_m": {
                "label": "Distance threshold",
                "type": "number",
                "default": 50,
                "min": 10,
                "max": 1000,
                "unit": "m",
            },
            "tracking_interval": {
                "label": "Auto-track interval (0=off)",
                "type": "number",
                "default": 0,
                "min": 0,
                "max": 300,
                "unit": "s",
            },
        },
    },
    {
        "event_type": "geofence_enter",
        "label": "Geofence enter",
        "description": "Notify when the vehicle enters a configured zone",
        "category": "security",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "geofence_exit",
        "label": "Geofence exit",
        "description": "Notify when the vehicle exits a configured zone",
        "category": "security",
        "has_image": True,
        "configurable": False,
    },
    {
        "event_type": "unlocked_timeout",
        "label": "Unlocked too long",
        "description": "Notify if the vehicle stays unlocked for too long while parked",
        "category": "security",
        "has_image": True,
        "configurable": True,
        "config_schema": {
            "timeout_minutes": {
                "label": "Timeout",
                "type": "number",
                "default": 30,
                "min": 5,
                "max": 240,
                "unit": "min",
            }
        },
    },
    # Maintenance
    {
        "event_type": "tire_pressure_alert",
        "label": "Tire pressure alert",
        "description": "Notify when tire pressure is outside the configured range",
        "category": "maintenance",
        "has_image": False,
        "configurable": True,
        "config_schema": {
            "min_bar": {
                "label": "Minimum pressure",
                "type": "number",
                "default": 2.2,
                "min": 1.5,
                "max": 3.0,
                "unit": "bar",
            },
            "max_bar": {
                "label": "Maximum pressure",
                "type": "number",
                "default": 3.0,
                "min": 2.5,
                "max": 4.0,
                "unit": "bar",
            },
        },
    },
    {
        "event_type": "range_low",
        "label": "Low range",
        "description": "Notify when estimated range drops below the threshold",
        "category": "maintenance",
        "has_image": True,
        "configurable": True,
        "config_schema": {
            "threshold_km": {
                "label": "Range threshold",
                "type": "number",
                "default": 50,
                "min": 10,
                "max": 200,
                "unit": "km",
            }
        },
    },
    # -- Maintenance reminders ------------------------------------------------
    {
        "event_type": "maintenance_upcoming",
        "label": "Service due soon",
        "description": (
            "Notify when a maintenance item is approaching its due date/mileage"
        ),
        "category": "maintenance",
        "has_image": False,
        "configurable": True,
        "config_schema": {
            "warn_days": {
                "label": "Warning days before due",
                "type": "number",
                "default": 14,
                "min": 1,
                "max": 90,
                "unit": "days",
            },
        },
    },
    {
        "event_type": "maintenance_overdue",
        "label": "Service overdue",
        "description": "Notify when a maintenance item has passed its due date/mileage",
        "category": "maintenance",
        "has_image": False,
        "configurable": True,
        "config_schema": {},
    },
    {
        "event_type": "maintenance_critical",
        "label": "Critical maintenance",
        "description": "Notify for urgent/critical overdue maintenance items",
        "category": "maintenance",
        "has_image": False,
        "configurable": True,
        "config_schema": {},
    },
]

# Lookup map
EVENT_CATALOG_MAP: dict[str, dict] = {e["event_type"]: e for e in EVENT_CATALOG}

# Dynamic image policy: disabled by default except for key charging plug events.
IMAGE_ENABLED_BY_DEFAULT_EVENTS: set[str] = {
    "charge_start",
    "charge_stop",
    "plugged_in",
    "unplugged",
}

# Events that come directly from TransitionDetector
TRANSITION_EVENTS = {
    "charge_start",
    "charge_stop",
    "plugged_in",
    "unplugged",
    "locked",
    "unlocked",
    "driving_start",
    "parked",
    "ignition_on",
    "ignition_off",
}

# ---------------------------------------------------------------------------
# Message templates
# ---------------------------------------------------------------------------

MESSAGE_TEMPLATES: dict[str, dict[str, str]] = {
    "charge_start": {
        "title": "🔌 Charging started",
        "body": "SOC: {soc}% — Range: {range} km",
    },
    "charge_stop": {
        "title": "✅ Charging complete",
        "body": "SOC: {soc}% — Range: {range} km",
    },
    "charge_interrupted": {
        "title": "⚠️ Charging interrupted",
        "body": "SOC: {soc}% (target: {soc_target}%) — Range: {range} km",
    },
    "soc_threshold_high": {
        "title": "🔋 SOC above threshold",
        "body": "SOC: {soc}% (threshold: {threshold}%) — Range: {range} km",
    },
    "soc_threshold_low": {
        "title": "🪫 SOC below threshold",
        "body": "SOC: {soc}% (threshold: {threshold}%) — Range: {range} km",
    },
    "plugged_in": {
        "title": "🔌 Plugged in",
        "body": "SOC: {soc}% — Range: {range} km",
    },
    "unplugged": {
        "title": "🔌 Unplugged",
        "body": "SOC: {soc}% — Range: {range} km",
    },
    "driving_start": {
        "title": "🚗 Driving",
        "body": "SOC: {soc}% — Range: {range} km",
    },
    "parked": {
        "title": "🅿️ Parked",
        "body": "SOC: {soc}% — Range: {range} km",
    },
    "ignition_on": {
        "title": "🔑 Ignition on",
        "body": "SOC: {soc}% — Range: {range} km",
    },
    "ignition_off": {
        "title": "🔑 Ignition off",
        "body": "SOC: {soc}% — Range: {range} km",
    },
    "locked": {
        "title": "🔒 Locked",
        "body": "",
    },
    "unlocked": {
        "title": "🔓 Unlocked",
        "body": "",
    },
    "movement_alert": {
        "title": "🚨 Movement alert!",
        "body": (
            "Vehicle moved {distance}m while parked and off!\n\n"
            '📍 <a href="https://www.google.com/maps?q={lat},{lon}">'
            "View on map</a>"
        ),
    },
    "geofence_enter": {
        "title": "📍 Entered zone",
        "body": 'Vehicle entered zone "{zone_name}"',
    },
    "geofence_exit": {
        "title": "📍 Left zone",
        "body": 'Vehicle left zone "{zone_name}"',
    },
    "unlocked_timeout": {
        "title": "⚠️ Unlocked too long",
        "body": "Vehicle has been unlocked for {minutes} minutes",
    },
    "tire_pressure_alert": {
        "title": "⚠️ Tire pressure alert",
        "body": "{details}",
    },
    "range_low": {
        "title": "🪫 Low range",
        "body": "Estimated range: {range} km (threshold: {threshold_km} km)",
    },
    "maintenance_upcoming": {
        "title": "🔧 Service due soon — {service_label}",
        "body": (
            "{service_label} is due in {remaining_days} days "
            "({remaining_km} km remaining).\n"
            "Due: {due_date}\n"
            "Vehicle: {vehicle_name}"
        ),
    },
    "maintenance_overdue": {
        "title": "⚠️ Service overdue — {service_label}",
        "body": (
            "{service_label} is overdue by {overdue_days} days "
            "({overdue_km} km over).\n"
            "Due: {due_date}\n"
            "Vehicle: {vehicle_name}"
        ),
    },
    "maintenance_critical": {
        "title": "🚨 Critical maintenance — {service_label}",
        "body": (
            "{service_label} is critically overdue!\n"
            "Vehicle: {vehicle_name}\n"
            "Please schedule service immediately."
        ),
    },
}
