"""Tests for the persisted GPS hemisphere memory."""

import json
from types import SimpleNamespace

from leapconnect.application.hemisphere_memory import SETTING_KEY, HemisphereMemory

VIN = "LTEST000000000001"


class FakeRepo:
    def __init__(self, settings=None):
        self.settings = dict(settings or {})
        self.writes = 0

    async def get_setting(self, key):
        return self.settings.get(key)

    async def save_setting(self, key, value):
        self.settings[key] = value
        self.writes += 1


def _status(lat, lon, *, signed):
    location = SimpleNamespace(
        latitude=lat, longitude=lon, latitude_signed=signed, longitude_signed=signed
    )
    return SimpleNamespace(location=location, collect_time=None)


async def test_restored_memory_puts_west_car_back_in_its_hemisphere():
    """After a restart, an absolute-value reading gets the saved West sign back."""
    repo = FakeRepo()
    memory = HemisphereMemory(repo)
    guard = await memory.load_guard()
    guard.apply(VIN, _status(38.7, -9.1, signed=True))
    await memory.save(guard)

    # Restart: a fresh memory and guard loaded from the saved setting.
    restored = await HemisphereMemory(repo).load_guard()
    status = restored.apply(VIN, _status(38.7, 9.1, signed=False))

    assert status.location.longitude == -9.1
    assert status.location.latitude == 38.7


async def test_save_writes_only_when_state_changes():
    repo = FakeRepo()
    memory = HemisphereMemory(repo)
    guard = await memory.load_guard()

    await memory.save(guard)
    assert repo.writes == 0  # nothing learned yet

    guard.apply(VIN, _status(38.7, -9.1, signed=True))
    await memory.save(guard)
    await memory.save(guard)
    assert repo.writes == 1
    assert json.loads(repo.settings[SETTING_KEY])[VIN]["longitude"]["sign"] == -1


async def test_unreadable_setting_starts_from_an_empty_memory():
    repo = FakeRepo({SETTING_KEY: "{not json"})
    guard = await HemisphereMemory(repo).load_guard()
    assert guard.export_state() == {}


async def test_save_without_guard_is_a_noop():
    repo = FakeRepo()
    await HemisphereMemory(repo).save(None)
    assert repo.writes == 0
