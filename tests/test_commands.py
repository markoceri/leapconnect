"""Tests for the vehicle command registry and the generic command endpoint."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from leapmotor_api.async_client import AsyncLeapmotorApiClient

from leapconnect.api import deps
from leapconnect.application.commands import (
    COMMANDS,
    ChargeLimitParams,
    ClimateParams,
    DestinationParams,
    FotaTaskParams,
    MediaParams,
    RearSeatsParams,
    SeatLevelParams,
    SpeedLimitParams,
    ValueParams,
    command_allowed,
    execute_mqtt_command,
    execute_vehicle_command,
    normalize_command,
)

# Minimal valid params per model, used to drive every invoke in tests.
SAMPLE_PARAMS = {
    ValueParams: ValueParams(),
    ClimateParams: ClimateParams(),
    ChargeLimitParams: ChargeLimitParams(limit=50),
    SeatLevelParams: SeatLevelParams(position=1, level=1),
    SpeedLimitParams: SpeedLimitParams(value="100"),
    MediaParams: MediaParams(operation="play"),
    DestinationParams: DestinationParams(address="Home", latitude=1.0, longitude=2.0),
    FotaTaskParams: FotaTaskParams(task_id=1),
    RearSeatsParams: RearSeatsParams(seat_info="x"),
}


class TestRegistryIntegrity:
    @pytest.mark.parametrize("name", sorted(COMMANDS))
    async def test_every_command_calls_a_real_client_method(self, name):
        """Each spec must invoke a method that exists on the cloud client."""
        spec = COMMANDS[name]
        client = AsyncMock()
        params = {} if spec.raw_params else SAMPLE_PARAMS.get(spec.params)
        await spec.invoke(client, "VIN123", params)
        called = [c[0] for c in client.method_calls]
        assert len(called) == 1, f"{name} called {called}"
        method = called[0]
        assert hasattr(AsyncLeapmotorApiClient, method), (
            f"{name} -> AsyncLeapmotorApiClient.{method} does not exist"
        )
        # The VIN must always be the first positional argument
        assert client.method_calls[0][1][0] == "VIN123"

    def test_normalize_accepts_kebab_and_legacy_names(self):
        assert normalize_command("trunk-open") == "trunk_open"
        assert normalize_command("trunk_open") == "trunk_open"
        assert normalize_command("ac_on") == "ac"  # legacy Telegram/MQTT name


def _vehicle(rights=(), abilities=()):
    return SimpleNamespace(vin="VIN123", rights=list(rights), abilities=list(abilities))


class TestRightsChecks:
    def test_command_allowed_requires_right_and_ability(self):
        # lock needs right 110, granted by ability 1
        assert command_allowed(_vehicle([110], [1]), "lock") is True
        assert command_allowed(_vehicle([110], []), "lock") is False
        assert command_allowed(_vehicle([], [1]), "lock") is False

    def test_unknown_command_not_allowed(self):
        assert command_allowed(_vehicle([110], [1]), "warp-drive") is False

    async def test_telegram_executor_enforces_rights(self):
        client = AsyncMock()
        with pytest.raises(PermissionError):
            await execute_vehicle_command(client, _vehicle(), "lock")

    async def test_telegram_executor_skips_param_commands(self):
        client = AsyncMock()
        assert await execute_vehicle_command(client, _vehicle(), "charge_limit") is None

    async def test_mqtt_executor_runs_bodyless_commands(self):
        client = AsyncMock()
        client.lock_vehicle.return_value = {"status": "ok"}
        result = await execute_mqtt_command(client, "VIN123", "lock")
        assert result == {"status": "ok"}
        assert await execute_mqtt_command(client, "VIN123", "charge_limit") is None


@pytest.fixture
def command_client(auth_client):
    """Authenticated client with the cloud client stubbed out."""
    stub = AsyncMock()
    auth_client.app.dependency_overrides[deps.get_client] = lambda: stub
    yield auth_client, stub
    auth_client.app.dependency_overrides.clear()


class TestGenericCommandEndpoint:
    def test_plain_command(self, command_client):
        client, stub = command_client
        stub.lock_vehicle.return_value = {"status": "ok"}
        resp = client.post("/api/vehicles/VIN123/commands/lock")
        assert resp.status_code == 200
        stub.lock_vehicle.assert_awaited_once_with("VIN123")

    def test_kebab_name_normalization(self, command_client):
        client, stub = command_client
        stub.open_trunk.return_value = {"status": "ok"}
        resp = client.post("/api/vehicles/VIN123/commands/trunk-open")
        assert resp.status_code == 200
        stub.open_trunk.assert_awaited_once_with("VIN123")

    def test_unknown_command_404(self, command_client):
        client, _ = command_client
        resp = client.post("/api/vehicles/VIN123/commands/warp-drive")
        assert resp.status_code == 404

    def test_charge_limit_valid(self, command_client):
        client, stub = command_client
        stub.set_charge_limit.return_value = {"status": "ok"}
        resp = client.post(
            "/api/vehicles/VIN123/commands/charge-limit", json={"limit": 80}
        )
        assert resp.status_code == 200
        stub.set_charge_limit.assert_awaited_once_with("VIN123", 80)

    def test_charge_limit_out_of_range_422(self, command_client):
        client, stub = command_client
        resp = client.post(
            "/api/vehicles/VIN123/commands/charge-limit", json={"limit": 10}
        )
        assert resp.status_code == 422
        stub.set_charge_limit.assert_not_awaited()

    def test_climate_params_filtered(self, command_client):
        client, stub = command_client
        stub.ac_on.return_value = {"status": "ok"}
        resp = client.post(
            "/api/vehicles/VIN123/commands/ac", json={"temperature": "22"}
        )
        assert resp.status_code == 200
        stub.ac_on.assert_awaited_once_with("VIN123", params={"temperature": "22"})

    def test_windows_default_value(self, command_client):
        client, stub = command_client
        stub.windows.return_value = {"status": "ok"}
        resp = client.post("/api/vehicles/VIN123/commands/windows")
        assert resp.status_code == 200
        stub.windows.assert_awaited_once_with("VIN123", value="100")

    def test_requires_session(self, client):
        resp = client.post("/api/vehicles/VIN123/commands/lock")
        assert resp.status_code == 401

    def test_list_commands_availability(self, auth_client):
        vehicle = _vehicle(rights=[110], abilities=[1])
        auth_client.app.dependency_overrides[deps.get_vehicle] = lambda: vehicle
        try:
            resp = auth_client.get("/api/vehicles/VIN123/commands")
            assert resp.status_code == 200
            by_name = {c["command"]: c for c in resp.json()}
            assert by_name["lock"]["available"] is True
            assert by_name["sentry-mode-on"]["available"] is False
            assert by_name["charge-limit"]["requires_params"] is True
            assert by_name["lock"]["requires_params"] is False
        finally:
            auth_client.app.dependency_overrides.clear()
