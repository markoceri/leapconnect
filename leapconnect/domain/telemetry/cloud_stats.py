"""Date windows for the Leapmotor cloud statistics endpoints.

The windowed cloud statistics (consumption breakdown, daily mileage/energy)
take timezone-aware ``start``/``end`` datetimes. The UI picks whole days in
the user's time zone; this turns them into an aware UTC window.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, tzinfo

from leapconnect.domain.charging.sessions import day_range_bounds

# Longest window accepted, in days (one leap year).
MAX_WINDOW_DAYS = 366


def cloud_window(
    first: date, last: date, tz: tzinfo = UTC
) -> tuple[datetime, datetime]:
    """``[first day 00:00, day after last 00:00)`` in ``tz``, as aware UTC.

    Raises ``ValueError`` when ``last`` precedes ``first`` or the window spans
    more than ``MAX_WINDOW_DAYS`` days.
    """
    if last < first:
        raise ValueError("'to_date' must not precede 'from_date'")
    if (last - first).days + 1 > MAX_WINDOW_DAYS:
        raise ValueError(f"the window cannot exceed {MAX_WINDOW_DAYS} days")
    start, end = day_range_bounds(first, last, tz)
    return start.replace(tzinfo=UTC), end.replace(tzinfo=UTC)
