"""Time helpers.

The database stores timezone-naive timestamps in UTC. These helpers keep that
convention in one place and avoid the deprecated ``datetime.utcnow()``.
"""

from datetime import datetime, timezone

import pytz


def utcnow() -> datetime:
    """Return the current time as a naive UTC datetime.

    Stored values use naive UTC, so we strip the tzinfo after computing an
    aware UTC timestamp (``datetime.utcnow()`` is deprecated since 3.12).

    Returns:
        Naive ``datetime`` in UTC.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_month_to_utc_range(
    year: int, month: int, tz_name: str
) -> tuple[datetime, datetime]:
    """Get the UTC half-open range covering a calendar month in a timezone.

    Args:
        year: Calendar year.
        month: Calendar month (1-12).
        tz_name: IANA timezone name (e.g. ``Europe/Moscow``).

    Returns:
        Tuple ``(start_utc, end_utc)`` of naive UTC datetimes where the range is
        ``start_utc <= ts < end_utc``.
    """
    tz = pytz.timezone(tz_name)
    start_local = tz.localize(datetime(year, month, 1))
    if month == 12:
        end_local = tz.localize(datetime(year + 1, 1, 1))
    else:
        end_local = tz.localize(datetime(year, month + 1, 1))

    start_utc = start_local.astimezone(pytz.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(pytz.utc).replace(tzinfo=None)
    return start_utc, end_utc


def local_year_to_utc_range(year: int, tz_name: str) -> tuple[datetime, datetime]:
    """Get the UTC half-open range covering a calendar year in a timezone.

    Args:
        year: Calendar year.
        tz_name: IANA timezone name.

    Returns:
        Tuple ``(start_utc, end_utc)`` of naive UTC datetimes.
    """
    tz = pytz.timezone(tz_name)
    start_local = tz.localize(datetime(year, 1, 1))
    end_local = tz.localize(datetime(year + 1, 1, 1))
    start_utc = start_local.astimezone(pytz.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(pytz.utc).replace(tzinfo=None)
    return start_utc, end_utc


def current_local_year_month(tz_name: str) -> tuple[int, int]:
    """Get the current (year, month) in the given timezone.

    Args:
        tz_name: IANA timezone name.

    Returns:
        Tuple ``(year, month)``.
    """
    now = datetime.now(pytz.timezone(tz_name))
    return now.year, now.month
