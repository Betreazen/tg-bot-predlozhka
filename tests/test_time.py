"""Tests for time helpers (pure, no infrastructure)."""

from datetime import datetime, timezone

from bot.utils.time import (
    utcnow,
    local_month_to_utc_range,
    local_year_to_utc_range,
    current_local_year_month,
)


def test_utcnow_is_naive_and_recent():
    now = utcnow()
    assert now.tzinfo is None
    delta = abs((datetime.now(timezone.utc).replace(tzinfo=None) - now).total_seconds())
    assert delta < 5


def test_month_range_moscow_offset():
    # Moscow is UTC+3, so the local month boundary is 21:00 the previous day UTC.
    start, end = local_month_to_utc_range(2026, 1, "Europe/Moscow")
    assert start == datetime(2025, 12, 31, 21, 0, 0)
    assert end == datetime(2026, 1, 31, 21, 0, 0)
    assert start.tzinfo is None and end.tzinfo is None


def test_month_range_december_rolls_over():
    start, end = local_month_to_utc_range(2026, 12, "Europe/Moscow")
    assert start == datetime(2026, 11, 30, 21, 0, 0)
    assert end == datetime(2026, 12, 31, 21, 0, 0)


def test_month_range_utc_timezone():
    start, end = local_month_to_utc_range(2026, 3, "UTC")
    assert start == datetime(2026, 3, 1, 0, 0, 0)
    assert end == datetime(2026, 4, 1, 0, 0, 0)


def test_year_range_moscow():
    start, end = local_year_to_utc_range(2026, "Europe/Moscow")
    assert start == datetime(2025, 12, 31, 21, 0, 0)
    assert end == datetime(2026, 12, 31, 21, 0, 0)


def test_current_local_year_month():
    year, month = current_local_year_month("Europe/Moscow")
    assert isinstance(year, int) and isinstance(month, int)
    assert 1 <= month <= 12
