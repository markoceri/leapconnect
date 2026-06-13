"""Vehicle remote-command registry with rights/ability checks.

Single source of truth shared by the REST API (generic
``POST /api/vehicles/{vin}/commands/{command}`` endpoint), the Telegram bot
and the MQTT bridge: each :class:`CommandSpec` knows how to invoke the cloud
client, which body parameters it accepts (validated by a Pydantic model) and
which vehicle right gates it.

Rights enforcement: Telegram and MQTT-discovery filtering already use the
``right`` field; the REST endpoint is **pass-through for now** (no 403 on a
missing right, matching the historical per-command routes). Once the rights
map has been validated in the field, flip the REST endpoint to enforce —
the data is already here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from leapmotor_api.async_client import AsyncLeapmotorApiClient
    from leapmotor_api.models import Vehicle

# ---------------------------------------------------------------------------
# Rights / abilities
# ---------------------------------------------------------------------------

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
    spec = COMMANDS.get(normalize_command(command))
    if spec is None:
        return False
    return vehicle_has_right(vehicle, spec.right)


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ValueParams(BaseModel):
    """Single optional position/level value (windows, sunshade)."""

    value: str | None = None


class ClimateParams(BaseModel):
    """Optional overrides for climate commands (None fields are dropped)."""

    circle: str | None = None  # "in" or "out"
    mode: str | None = None  # "cold", "hot", "wind"
    operate: str | None = None  # "manual", "auto", or "close"
    position: str | None = None  # "all"
    temperature: str | None = None  # e.g. "26"
    windlevel: int | None = None  # 1–7
    wshld: str | None = None  # "0" (off) or "1" (defrost on)


class ChargeLimitParams(BaseModel):
    limit: int = Field(ge=20, le=100)


class SeatLevelParams(BaseModel):
    position: int = Field(ge=1, le=6)
    level: int = Field(ge=0, le=3)


class SpeedLimitParams(BaseModel):
    value: str  # km/h as string


class MediaParams(BaseModel):
    operation: str  # "play", "pause", "next", "previous"


class DestinationParams(BaseModel):
    address: str = Field(min_length=1)
    address_name: str = ""
    latitude: float
    longitude: float


class FotaTaskParams(BaseModel):
    task_id: int


class RearSeatsParams(BaseModel):
    seat_info: str


# ---------------------------------------------------------------------------
# Command registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommandSpec:
    """How to invoke one remote command and which vehicle right gates it."""

    invoke: Callable[[AsyncLeapmotorApiClient, str, object], Awaitable[dict]]
    right: int | None = None
    params: type[BaseModel] | None = None
    raw_params: bool = False  # body forwarded verbatim as ``params`` dict

    @property
    def requires_params(self) -> bool:
        """True if the command cannot be invoked without a body."""
        if self.params is None:
            return False
        return any(f.is_required() for f in self.params.model_fields.values())


def _plain(method: str):
    async def call(client: AsyncLeapmotorApiClient, vin: str, _params) -> dict:
        return await getattr(client, method)(vin)

    return call


def _value(method: str, default: str | None = None):
    async def call(
        client: AsyncLeapmotorApiClient, vin: str, p: ValueParams | None
    ) -> dict:
        value = p.value if p and p.value is not None else default
        return await getattr(client, method)(vin, value=value)

    return call


def _climate(method: str):
    async def call(
        client: AsyncLeapmotorApiClient, vin: str, p: ClimateParams | None
    ) -> dict:
        params = {
            k: v for k, v in (p.model_dump() if p else {}).items() if v is not None
        } or None
        return await getattr(client, method)(vin, params=params)

    return call


def _raw(method: str):
    async def call(client: AsyncLeapmotorApiClient, vin: str, body) -> dict:
        return await getattr(client, method)(vin, params=body or {})

    return call


async def _charge_limit(client, vin: str, p: ChargeLimitParams) -> dict:
    return await client.set_charge_limit(vin, p.limit)


async def _seat_heat(client, vin: str, p: SeatLevelParams) -> dict:
    return await client.seat_heat(vin, position=p.position, level=p.level)


async def _seat_ventilation(client, vin: str, p: SeatLevelParams) -> dict:
    return await client.seat_ventilation(vin, position=p.position, level=p.level)


async def _speed_limit(client, vin: str, p: SpeedLimitParams) -> dict:
    return await client.set_speed_limit(vin, value=p.value)


async def _music(client, vin: str, p: MediaParams) -> dict:
    return await client.music(vin, operation=p.operation)


async def _video(client, vin: str, p: MediaParams) -> dict:
    return await client.video(vin, operation=p.operation)


async def _send_destination(client, vin: str, p: DestinationParams) -> dict:
    return await client.send_destination(
        vin,
        address=p.address,
        address_name=p.address_name or p.address,
        latitude=p.latitude,
        longitude=p.longitude,
    )


async def _fota_download(client, vin: str, p: FotaTaskParams) -> dict:
    return await client.fota_download(vin, task_id=p.task_id)


async def _fota_install(client, vin: str, p: FotaTaskParams) -> dict:
    return await client.fota_install(vin, task_id=p.task_id)


async def _rear_seats(client, vin: str, p: RearSeatsParams) -> dict:
    return await client.rear_seats(vin, seat_info=p.seat_info)


# Registry keys are snake_case; the public (URL/frontend) form is kebab-case —
# see normalize_command(). Rights mirror the official app's menu gating.
COMMANDS: dict[str, CommandSpec] = {
    # locks / body
    "lock": CommandSpec(_plain("lock_vehicle"), right=110),
    "unlock": CommandSpec(_plain("unlock_vehicle"), right=110),
    "trunk_open": CommandSpec(_plain("open_trunk"), right=130),
    "trunk_close": CommandSpec(_plain("close_trunk"), right=130),
    "find": CommandSpec(_plain("find_vehicle"), right=120),
    "windows": CommandSpec(_value("windows", "100"), right=230, params=ValueParams),
    "windows_open": CommandSpec(_value("open_windows"), right=230, params=ValueParams),
    "windows_close": CommandSpec(
        _value("close_windows"), right=230, params=ValueParams
    ),
    "sunshade": CommandSpec(
        _value("control_sunshade", "10"), right=161, params=ValueParams
    ),
    "sunshade_open": CommandSpec(
        _value("open_sunshade"), right=161, params=ValueParams
    ),
    "sunshade_close": CommandSpec(
        _value("close_sunshade"), right=161, params=ValueParams
    ),
    "sunroof_open": CommandSpec(_plain("open_sunroof"), right=160),
    "sunroof_close": CommandSpec(_plain("close_sunroof"), right=160),
    # climate
    "ac": CommandSpec(_climate("ac_on"), right=170, params=ClimateParams),
    "ac_off": CommandSpec(_plain("ac_off"), right=170),
    "quick_cool": CommandSpec(_climate("quick_cool"), right=170, params=ClimateParams),
    "quick_heat": CommandSpec(_climate("quick_heat"), right=170, params=ClimateParams),
    "defrost": CommandSpec(
        _climate("windshield_defrost"), right=170, params=ClimateParams
    ),
    "steering_wheel_heat_on": CommandSpec(_plain("steering_wheel_heat_on"), right=320),
    "steering_wheel_heat_off": CommandSpec(
        _plain("steering_wheel_heat_off"), right=320
    ),
    "rearview_mirror_heat_on": CommandSpec(
        _plain("rearview_mirror_heat_on"), right=440
    ),
    "rearview_mirror_heat_off": CommandSpec(
        _plain("rearview_mirror_heat_off"), right=440
    ),
    "fuel_heating_on": CommandSpec(_plain("fuel_heating_on"), right=380),
    "fuel_heating_off": CommandSpec(_plain("fuel_heating_off"), right=380),
    # charging / battery
    "charging_start": CommandSpec(_plain("start_charging"), right=193),
    "charging_stop": CommandSpec(_plain("stop_charging"), right=193),
    "battery_preheat": CommandSpec(_plain("battery_preheat"), right=190),
    "battery_preheat_off": CommandSpec(_plain("battery_preheat_off"), right=190),
    "unlock_charger": CommandSpec(_plain("unlock_charger"), right=192),
    "healthy_charging_on": CommandSpec(_plain("healthy_charging_on"), right=480),
    "healthy_charging_off": CommandSpec(_plain("healthy_charging_off"), right=480),
    "charge_limit": CommandSpec(_charge_limit, params=ChargeLimitParams),
    # seats
    "seat_heat": CommandSpec(_seat_heat, right=301, params=SeatLevelParams),
    "seat_ventilation": CommandSpec(
        _seat_ventilation, right=301, params=SeatLevelParams
    ),
    "seat_adjust": CommandSpec(_raw("seat_adjust"), right=301, raw_params=True),
    "rear_seats": CommandSpec(_rear_seats, right=301, params=RearSeatsParams),
    # security / misc
    "sentry_mode_on": CommandSpec(_plain("sentry_mode_on"), right=220),
    "sentry_mode_off": CommandSpec(_plain("sentry_mode_off"), right=220),
    "on3_on": CommandSpec(_plain("on3_on"), right=410),
    "on3_off": CommandSpec(_plain("on3_off"), right=410),
    "ble_key_restart": CommandSpec(_plain("ble_key_restart"), right=430),
    "hotspot": CommandSpec(_plain("hotspot"), right=140),
    "autopark": CommandSpec(_plain("autopark"), right=150),
    "piloted_parking": CommandSpec(_raw("piloted_parking"), right=350, raw_params=True),
    "prepare_car": CommandSpec(_raw("prepare_car"), right=360, raw_params=True),
    "speed_limit": CommandSpec(_speed_limit, right=510, params=SpeedLimitParams),
    "send_destination": CommandSpec(
        _send_destination, right=180, params=DestinationParams
    ),
    "music": CommandSpec(_music, right=270, params=MediaParams),
    "video": CommandSpec(_video, right=270, params=MediaParams),
    # firmware
    "fota_download": CommandSpec(_fota_download, right=390, params=FotaTaskParams),
    "fota_install": CommandSpec(_fota_install, right=390, params=FotaTaskParams),
}


# Legacy names still used by the Telegram bot and MQTT discovery payloads.
_ALIASES: dict[str, str] = {"ac_on": "ac"}


def normalize_command(command: str) -> str:
    """Map a public kebab-case or legacy command name to its registry key."""
    key = command.replace("-", "_")
    return _ALIASES.get(key, key)


def public_name(key: str) -> str:
    """Registry key → public kebab-case command name."""
    return key.replace("_", "-")


# ---------------------------------------------------------------------------
# Executors (Telegram bot / MQTT bridge)
# ---------------------------------------------------------------------------


async def execute_vehicle_command(
    client: AsyncLeapmotorApiClient, vehicle: Vehicle, command: str
) -> dict | None:
    """Execute a body-less vehicle command by name (Telegram bot handler).

    Checks vehicle rights/abilities before executing.
    Raises PermissionError if the command is not allowed.
    Returns None if the command is unknown or requires parameters.
    """
    spec = COMMANDS.get(normalize_command(command))
    if spec is None or spec.requires_params or spec.raw_params:
        return None
    if not vehicle_has_right(vehicle, spec.right):
        raise PermissionError(f"Command '{command}' not available for this vehicle")
    return await spec.invoke(client, vehicle.vin, None)


async def execute_mqtt_command(
    client: AsyncLeapmotorApiClient, vin: str, command: str
) -> dict | None:
    """Execute a body-less command received via MQTT.

    Returns None for unknown commands or commands that need parameters.
    """
    spec = COMMANDS.get(normalize_command(command))
    if spec is None or spec.requires_params or spec.raw_params:
        return None
    return await spec.invoke(client, vin, None)
