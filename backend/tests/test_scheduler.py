"""Scheduler timing and configuration (pure, no DB)."""

from datetime import datetime
from zoneinfo import ZoneInfo

from scheduler import (
    DEFAULT_HOUR,
    DEFAULT_TZ,
    _configured_hour,
    _configured_tz,
    seconds_until_next_run,
)

PARIS = ZoneInfo("Europe/Paris")


def test_next_run_is_later_today_when_target_is_ahead():
    now = datetime(2026, 7, 4, 5, 0, tzinfo=PARIS)
    assert seconds_until_next_run(now, hour=6) == 3600  # one hour later


def test_next_run_rolls_to_tomorrow_when_target_has_passed():
    now = datetime(2026, 7, 4, 7, 0, tzinfo=PARIS)
    # 06:00 already passed → next is 06:00 tomorrow, 23 h away.
    assert seconds_until_next_run(now, hour=6) == 23 * 3600


def test_configured_hour_defaults_and_reads_env(monkeypatch):
    monkeypatch.delenv("RECURRENCE_HOUR", raising=False)
    assert _configured_hour() == DEFAULT_HOUR

    monkeypatch.setenv("RECURRENCE_HOUR", "2")
    assert _configured_hour() == 2

    # Invalid or out-of-range values fall back to the default.
    monkeypatch.setenv("RECURRENCE_HOUR", "nope")
    assert _configured_hour() == DEFAULT_HOUR
    monkeypatch.setenv("RECURRENCE_HOUR", "42")
    assert _configured_hour() == DEFAULT_HOUR


def test_configured_tz_defaults_and_falls_back(monkeypatch):
    monkeypatch.delenv("RECURRENCE_TZ", raising=False)
    assert _configured_tz() == ZoneInfo(DEFAULT_TZ)

    monkeypatch.setenv("RECURRENCE_TZ", "America/New_York")
    assert _configured_tz() == ZoneInfo("America/New_York")

    # Unknown timezone → default.
    monkeypatch.setenv("RECURRENCE_TZ", "Not/AZone")
    assert _configured_tz() == ZoneInfo(DEFAULT_TZ)
