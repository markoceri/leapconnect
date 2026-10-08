"""Time-of-use costing: band schedules are local time, sessions are UTC."""

from datetime import datetime
from zoneinfo import ZoneInfo

from leapconnect.domain.charging.costing import calculate_tou_cost
from leapconnect.domain.charging.models import ChargingTimeBand

ROME = ZoneInfo("Europe/Rome")
ALL_DAYS = list(range(7))

# Night band 23:00-07:00 local at 0.10 €/kWh; anything else falls back to 0.30.
NIGHT = ChargingTimeBand(
    id=1,
    name="Night",
    price_kwh=0.10,
    schedule=[
        {
            "days": ALL_DAYS,
            "start_hour": 23,
            "start_min": 0,
            "end_hour": 7,
            "end_min": 0,
        }
    ],
)


def test_bands_are_matched_in_local_time():
    # 21:00-22:00 UTC = 23:00-00:00 in Rome (summer): fully in the night band.
    start, end = datetime(2026, 8, 1, 21), datetime(2026, 8, 1, 22)
    assert calculate_tou_cost(10, start, end, [NIGHT], 0.30, ROME) == 1.0
    # Read as UTC wall-clock it would be the day price.
    assert calculate_tou_cost(10, start, end, [NIGHT], 0.30) == 3.0


def test_band_boundary_follows_dst():
    # 05:00-06:00 UTC is 07:00-08:00 in summer (day) but 06:00-07:00 in
    # winter (night) in Rome.
    summer = calculate_tou_cost(
        10, datetime(2026, 8, 3, 5), datetime(2026, 8, 3, 6), [NIGHT], 0.30, ROME
    )
    winter = calculate_tou_cost(
        10, datetime(2026, 12, 3, 5), datetime(2026, 12, 3, 6), [NIGHT], 0.30, ROME
    )
    assert (summer, winter) == (3.0, 1.0)


def test_aware_timestamps_are_converted():
    start = datetime(2026, 8, 1, 23, tzinfo=ROME)
    end = datetime(2026, 8, 2, 0, tzinfo=ROME)
    assert calculate_tou_cost(10, start, end, [NIGHT], 0.30, ROME) == 1.0
