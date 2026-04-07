"""Tests for HexClamp scheduler."""

import pytest
from unittest.mock import Mock
import time

from hexclamp.scheduler import (
    TimerManager,
    Timer,
    CronExpression,
    Schedule,
    ScheduleType,
    create_cron_timer,
    create_interval_timer,
)


class TestCronExpression:
    """Tests for CronExpression."""

    def test_parse_simple(self):
        """Test parsing a simple cron expression."""
        cron = CronExpression.parse("0 * * * *")
        assert cron.minute == "0"
        assert cron.hour == "*"
        assert cron.day_of_month == "*"

    def test_parse_full(self):
        """Test parsing a full cron expression."""
        cron = CronExpression.parse("*/15 9-17 * * 1-5")
        assert cron.minute == "*/15"
        assert cron.hour == "9-17"
        assert cron.day_of_week == "1-5"

    def test_matches_wildcard(self):
        """Test matching wildcard."""
        from datetime import datetime, timezone

        cron = CronExpression.parse("* * * * *")
        dt = datetime(2026, 4, 7, 10, 30, tzinfo=timezone.utc)
        assert cron.matches(dt) is True

    def test_matches_minute(self):
        """Test matching specific minute."""
        from datetime import datetime, timezone

        cron = CronExpression.parse("30 * * * *")
        dt_match = datetime(2026, 4, 7, 10, 30, tzinfo=timezone.utc)
        dt_no_match = datetime(2026, 4, 7, 10, 31, tzinfo=timezone.utc)

        assert cron.matches(dt_match) is True
        assert cron.matches(dt_no_match) is False


class TestTimerManager:
    """Tests for TimerManager."""

    def test_init(self):
        """Test manager initialization."""
        manager = TimerManager()
        assert len(manager.list_schedules()) == 0

    def test_add_interval_schedule(self):
        """Test adding an interval schedule."""
        manager = TimerManager()
        callback = Mock()

        schedule = manager.add_interval_schedule(
            "test-1",
            "Test Interval",
            60.0,
            callback,
        )

        assert schedule is not None
        assert schedule.id == "test-1"
        assert schedule.interval_seconds == 60.0

    def test_add_cron_schedule(self):
        """Test adding a cron schedule."""
        manager = TimerManager()
        callback = Mock()

        schedule = manager.add_cron_schedule(
            "test-cron",
            "Test Cron",
            "0 * * * *",
            callback,
        )

        assert schedule is not None
        assert schedule.schedule_type == ScheduleType.CRON

    def test_remove_schedule(self):
        """Test removing a schedule."""
        manager = TimerManager()
        manager.add_interval_schedule("test-1", "Test", 60.0, lambda: None)

        assert manager.remove_schedule("test-1") is True
        assert manager.get_schedule("test-1") is None

    def test_enable_disable(self):
        """Test enabling and disabling schedules."""
        manager = TimerManager()
        manager.add_interval_schedule("test-1", "Test", 60.0, lambda: None)

        assert manager.disable("test-1") is True
        assert manager.get_schedule("test-1").enabled is False

        assert manager.enable("test-1") is True
        assert manager.get_schedule("test-1").enabled is True


class TestTimer:
    """Tests for Timer class."""

    def test_timer_init(self):
        """Test timer initialization."""
        timer = Timer(5.0, lambda: None)
        assert timer.interval_seconds == 5.0
        assert timer._enabled is False

    def test_timer_start_stop(self):
        """Test starting and stopping timer."""
        timer = Timer(5.0, lambda: None)
        timer.start()
        assert timer._enabled is True

        timer.stop()
        assert timer._enabled is False

    def test_time_until_fire(self):
        """Test time until fire calculation."""
        timer = Timer(10.0, lambda: None)
        assert timer.time_until_fire() is None  # Not started

        timer.start()
        remaining = timer.time_until_fire()
        assert remaining is not None
        assert 9 <= remaining <= 10  # Should be close to 10
