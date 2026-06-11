"""Vehicle remote-command execution with rights/ability checks.

Shared by the REST API, the Telegram bot and the MQTT bridge.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from leapmotor_api.async_client import AsyncLeapmotorApiClient
    from leapmotor_api.models import Vehicle

# Command-to-right mapping (same as MQTT HA service)
COMMAND_RIGHTS: dict[str, int | None] = {
    "lock": 110,
    "unlock": 110,
    "trunk_open": 130,
    "trunk_close": 130,
    "find": 120,
    "windows_open": 230,
    "windows_close": 230,
    "charging_start": 193,
    "charging_stop": 193,
    "battery_preheat": 190,
    "battery_preheat_off": 190,
    "unlock_charger": 192,
    "sunroof_open": 160,
    "sunroof_close": 160,
    "defrost": 170,
    "ac_on": None,
    "ac_off": None,
    "sentry_mode_on": None,
    "sentry_mode_off": None,
    "steering_wheel_heat_on": None,
    "steering_wheel_heat_off": None,
}

# Ability → Rights mapping (mirrors mqtt_ha)
ABILITY_TO_RIGHTS: dict[int, list[int]] = {
    1: [110],
    2: [120],
    3: [130],
    4: [150],
    6: [170],
    9: [171],
    10: [190],
    11: [161],
    12: [230],
    14: [301],
    15: [320],
    17: [170, 171],
    18: [460],
    24: [130],
    25: [160],
    30: [180],
    34: [510],
    35: [340],
    36: [230],
    38: [360, 361],
    40: [380],
    42: [370],
    43: [370],
    48: [192],
    50: [220],
    52: [180],
}

RIGHTS_WITH_ABILITY: set[int] = set()
for _rl in ABILITY_TO_RIGHTS.values():
    RIGHTS_WITH_ABILITY.update(_rl)


def vehicle_has_right(vehicle: Vehicle, right: int | None) -> bool:
    """Check if a vehicle has the required right+ability permission."""
    if right is None:
        return True
    user_rights = {r.value if hasattr(r, "value") else int(r) for r in vehicle.rights}
    if right not in user_rights:
        return False
    if right in RIGHTS_WITH_ABILITY:
        hw_rights: set[int] = set()
        for a in vehicle.abilities:
            a_val = a.value if hasattr(a, "value") else int(a)
            mapped = ABILITY_TO_RIGHTS.get(a_val, [])
            hw_rights.update(mapped)
        if right not in hw_rights:
            return False
    return True


def command_allowed(vehicle: Vehicle, command: str) -> bool:
    """Check if a command is permitted for the vehicle (menu filtering)."""
    return vehicle_has_right(vehicle, COMMAND_RIGHTS.get(command))


async def execute_vehicle_command(
    client: AsyncLeapmotorApiClient, vehicle: Vehicle, command: str
) -> dict | None:
    """Execute a vehicle command by name. Used by the Telegram bot handler.

    Checks vehicle rights/abilities before executing.
    Raises PermissionError if the command is not allowed.
    Returns None if the command is unknown.
    """
    required_right = COMMAND_RIGHTS.get(command)
    if command in COMMAND_RIGHTS and not vehicle_has_right(vehicle, required_right):
        raise PermissionError(f"Command '{command}' not available for this vehicle")

    command_map = {
        "lock": client.lock_vehicle,
        "unlock": client.unlock_vehicle,
        "trunk_open": client.open_trunk,
        "trunk_close": client.close_trunk,
        "find": client.find_vehicle,
        "windows_open": client.open_windows,
        "windows_close": client.close_windows,
        "charging_start": client.start_charging,
        "charging_stop": client.stop_charging,
        "battery_preheat": client.battery_preheat,
        "battery_preheat_off": client.battery_preheat_off,
        "unlock_charger": client.unlock_charger,
        "sunroof_open": client.open_sunroof,
        "sunroof_close": client.close_sunroof,
        "defrost": client.windshield_defrost,
        "ac_on": client.ac_on,
        "ac_off": client.ac_off,
        "sentry_mode_on": client.sentry_mode_on,
        "sentry_mode_off": client.sentry_mode_off,
        "steering_wheel_heat_on": client.steering_wheel_heat_on,
        "steering_wheel_heat_off": client.steering_wheel_heat_off,
    }
    fn = command_map.get(command)
    if not fn:
        return None
    return await fn(vehicle.vin)


# MQTT accepts a wider command set than the REST/Telegram map above.
MQTT_COMMAND_METHODS: dict[str, str] = {
    "lock": "lock_vehicle",
    "unlock": "unlock_vehicle",
    "trunk_open": "open_trunk",
    "trunk_close": "close_trunk",
    "find": "find_vehicle",
    "windows_open": "open_windows",
    "windows_close": "close_windows",
    "charging_start": "start_charging",
    "charging_stop": "stop_charging",
    "battery_preheat": "battery_preheat",
    "battery_preheat_off": "battery_preheat_off",
    "unlock_charger": "unlock_charger",
    "sunroof_open": "open_sunroof",
    "sunroof_close": "close_sunroof",
    "on3_on": "on3_on",
    "on3_off": "on3_off",
    "ble_key_restart": "ble_key_restart",
    "hotspot": "hotspot",
    "autopark": "autopark",
    "defrost": "windshield_defrost",
    "ac_on": "ac_on",
    "ac_off": "ac_off",
    "sentry_mode_on": "sentry_mode_on",
    "sentry_mode_off": "sentry_mode_off",
    "steering_wheel_heat_on": "steering_wheel_heat_on",
    "steering_wheel_heat_off": "steering_wheel_heat_off",
    "fuel_heating_on": "fuel_heating_on",
    "fuel_heating_off": "fuel_heating_off",
    "rearview_mirror_heat_on": "rearview_mirror_heat_on",
    "rearview_mirror_heat_off": "rearview_mirror_heat_off",
    "healthy_charging_on": "healthy_charging_on",
    "healthy_charging_off": "healthy_charging_off",
}


async def execute_mqtt_command(
    client: AsyncLeapmotorApiClient, vin: str, command: str
) -> dict | None:
    """Execute a command received via MQTT. Returns None for unknown commands."""
    method_name = MQTT_COMMAND_METHODS.get(command)
    if not method_name:
        return None
    return await getattr(client, method_name)(vin)
