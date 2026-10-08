"""History queries follow the user's time zone for calendar days."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from leapconnect.domain.telemetry.models import VehicleSnapshot
from leapconnect.infrastructure.persistence.sqlite_adapter import (
    SqlAlchemyRepository,
)

ROME = ZoneInfo("Europe/Rome")


@pytest.fixture
async def repo(tmp_path):
    repo = SqlAlchemyRepository(f"sqlite+aiosqlite:///{tmp_path}/history.db")
    await repo.init_db()
    # 22:30 UTC on Aug 1 is 00:30 on Aug 2 in Rome (summer, UTC+2).
    for ts, soc in (
        (datetime(2026, 8, 1, 12, 0), 50),
        (datetime(2026, 8, 1, 22, 30), 80),
        (datetime(2026, 8, 2, 9, 0), 90),
    ):
        await repo.save_snapshot(
            VehicleSnapshot(vin="V1", timestamp=ts, battery_soc=soc)
        )
    return repo


async def test_day_range_is_a_local_day(repo):
    utc_day = await repo.get_history(
        "V1", from_date="2026-08-01", to_date="2026-08-01", tz=UTC
    )
    rome_day = await repo.get_history(
        "V1", from_date="2026-08-01", to_date="2026-08-01", tz=ROME
    )
    assert [s.battery_soc for s in utc_day] == [50, 80]
    assert [s.battery_soc for s in rome_day] == [50]


async def test_daily_summary_groups_by_local_day(repo):
    rome = await repo.get_daily_summary("V1", days=3650, tz=ROME)
    assert [(d["date"], d["sample_count"], d["avg_soc"]) for d in rome] == [
        ("2026-08-01", 1, 50),
        ("2026-08-02", 2, 85),
    ]
    utc = await repo.get_daily_summary("V1", days=3650)
    assert [(d["date"], d["sample_count"]) for d in utc] == [
        ("2026-08-01", 2),
        ("2026-08-02", 1),
    ]
