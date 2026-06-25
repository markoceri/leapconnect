"""Settings persistence helpers (application layer).

Maps the key/value settings table to typed settings objects, and computes
session costs from the user's pricing configuration.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from leapconnect.domain.charging.costing import calculate_tou_cost, flat_cost
from leapconnect.domain.settings.models import (
    AbrpSettings,
    MqttSettings,
    UserPreferences,
)

if TYPE_CHECKING:
    from leapconnect.application.ports.repositories import AppRepository
    from leapconnect.domain.charging.models import ChargingSessionCost


async def load_preferences(repo: AppRepository) -> UserPreferences:
    """Load user preferences from DB, falling back to defaults."""
    raw = await repo.get_setting("electricity_price_kwh")
    theme_raw = await repo.get_setting("theme")
    ds_enabled_raw = await repo.get_setting("downsampling_enabled")
    ds_max_points_raw = await repo.get_setting("downsampling_max_points")
    solar_raw = await repo.get_setting("has_solar_panels")
    pricing_mode_raw = await repo.get_setting("home_pricing_mode")
    auto_theme_raw = await repo.get_setting("auto_theme_from_vehicle")
    return UserPreferences(
        electricity_price_kwh=float(raw) if raw else 0.25,
        theme=theme_raw if theme_raw in ("dark", "light", "vehicle") else "dark",
        downsampling_enabled=ds_enabled_raw != "false" if ds_enabled_raw else True,
        downsampling_max_points=int(ds_max_points_raw) if ds_max_points_raw else 2000,
        has_solar_panels=solar_raw == "true" if solar_raw else False,
        home_pricing_mode=pricing_mode_raw
        if pricing_mode_raw in ("flat", "time_of_use")
        else "flat",
        auto_theme_from_vehicle=auto_theme_raw == "true" if auto_theme_raw else False,
    )


async def calculate_session_cost(
    repo: AppRepository,
    tier_id: str,
    energy_kwh: float,
    start_ts: datetime | None,
    end_ts: datetime | None,
) -> float:
    """Calculate cost for a session, using TOU bands if applicable."""
    prefs = await load_preferences(repo)
    tiers = {t.id: t for t in await repo.get_price_tiers()}
    tier = tiers.get(tier_id)
    if not tier:
        return 0.0

    # If home_grid + time_of_use mode, split by time bands
    if (
        tier_id == "home_grid"
        and prefs.home_pricing_mode == "time_of_use"
        and start_ts
        and end_ts
    ):
        bands = await repo.get_time_bands("home_grid")
        if bands:
            return calculate_tou_cost(
                energy_kwh, start_ts, end_ts, bands, tier.price_kwh
            )

    return flat_cost(energy_kwh, tier.price_kwh)


async def recompute_session_energy(
    repo: AppRepository, sc: ChargingSessionCost
) -> float | None:
    """Measure a session's total energy from the stored snapshots.

    Returns the battery dump-energy delta (kWh) between the first and last
    snapshot inside the session window, or ``None`` when there aren't at least
    two snapshots with an energy reading to measure it.
    """
    if not sc.start_ts:
        return None
    end_ts = sc.end_ts
    from_date = sc.start_ts.date().isoformat()
    to_date = (end_ts or datetime.now()).date().isoformat()
    history = await repo.get_history(
        sc.vin, from_date=from_date, to_date=to_date, max_points=None
    )
    snaps = [
        s
        for s in history
        if s.battery_dump_energy is not None
        and s.timestamp >= sc.start_ts
        and (end_ts is None or s.timestamp <= end_ts)
    ]
    if len(snaps) < 2:
        return None
    energy = abs(snaps[-1].battery_dump_energy - snaps[0].battery_dump_energy) / 1000
    return round(energy, 2) if energy > 0 else None


async def recalculate_session(
    repo: AppRepository, sc: ChargingSessionCost
) -> ChargingSessionCost:
    """Refresh a session's total energy and cost from current data in place.

    Re-measures ``energy_kwh`` from the stored snapshots and recomputes ``cost``
    using the tier's current price (TOU-aware). This is the single source of
    truth for finalizing a session, shared by the auto-finalize on charge stop
    and the manual "recalculate" action. Energy is left untouched when it cannot
    be measured, so a cost computed mid-session is never silently discarded.
    """
    energy = await recompute_session_energy(repo, sc)
    if energy is not None:
        sc.energy_kwh = energy
    if sc.energy_kwh is not None:
        sc.cost = await calculate_session_cost(
            repo, sc.tier_id, sc.energy_kwh, sc.start_ts, sc.end_ts
        )
    return sc


async def load_mqtt_settings(repo: AppRepository | None) -> MqttSettings:
    """Load MQTT settings from the database."""
    if not repo:
        return MqttSettings()
    settings = MqttSettings()
    enabled = await repo.get_setting("mqtt_enabled")
    settings.enabled = enabled == "1" if enabled else False
    settings.broker = await repo.get_setting("mqtt_broker") or ""
    port_str = await repo.get_setting("mqtt_port")
    settings.port = int(port_str) if port_str else 1883
    settings.username = await repo.get_setting("mqtt_username") or ""
    settings.password = await repo.get_setting("mqtt_password") or ""
    use_tls = await repo.get_setting("mqtt_use_tls")
    settings.use_tls = use_tls == "1" if use_tls else False
    settings.discovery_prefix = (
        await repo.get_setting("mqtt_discovery_prefix") or "homeassistant"
    )
    settings.topic_prefix = await repo.get_setting("mqtt_topic_prefix") or "leapconnect"
    return settings


async def save_mqtt_settings(
    repo: AppRepository | None, settings: MqttSettings
) -> None:
    """Persist MQTT settings to the database."""
    if not repo:
        return
    await repo.save_setting("mqtt_enabled", "1" if settings.enabled else "0")
    await repo.save_setting("mqtt_broker", settings.broker)
    await repo.save_setting("mqtt_port", str(settings.port))
    await repo.save_setting("mqtt_username", settings.username)
    await repo.save_setting("mqtt_password", settings.password)
    await repo.save_setting("mqtt_use_tls", "1" if settings.use_tls else "0")
    await repo.save_setting("mqtt_discovery_prefix", settings.discovery_prefix)
    await repo.save_setting("mqtt_topic_prefix", settings.topic_prefix)


async def load_abrp_settings(repo: AppRepository | None) -> AbrpSettings:
    """Load ABRP settings from the database."""
    if not repo:
        return AbrpSettings()
    settings = AbrpSettings()
    enabled = await repo.get_setting("abrp_enabled")
    settings.enabled = enabled == "1" if enabled else False
    settings.user_token = await repo.get_setting("abrp_user_token") or ""
    return settings


async def save_abrp_settings(
    repo: AppRepository | None, settings: AbrpSettings
) -> None:
    """Persist ABRP settings to the database."""
    if not repo:
        return
    await repo.save_setting("abrp_enabled", "1" if settings.enabled else "0")
    await repo.save_setting("abrp_user_token", settings.user_token)


# ---------------------------------------------------------------------------
# Per-vehicle accent colour selection
# ---------------------------------------------------------------------------
_VEHICLE_COLORS_KEY = "vehicle_theme_colors"


async def load_vehicle_colors(repo: AppRepository) -> dict[str, str]:
    """Return the persisted ``{vin: palette_color_key}`` accent selections."""
    raw = await repo.get_setting(_VEHICLE_COLORS_KEY)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


async def save_vehicle_color(
    repo: AppRepository, vin: str, color_key: str | None
) -> dict[str, str]:
    """Set or clear a vehicle's accent colour, returning the updated map.

    Passing ``None`` removes the override so the vehicle falls back to the
    default accent.
    """
    colors = await load_vehicle_colors(repo)
    if color_key:
        colors[vin] = color_key
    else:
        colors.pop(vin, None)
    await repo.save_setting(_VEHICLE_COLORS_KEY, json.dumps(colors))
    return colors
