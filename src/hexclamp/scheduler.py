"""HexClamp scheduler - Timer and schedule management."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ScheduleType(str, Enum):
    """Schedule types."""

    CRON = "cron"
    INTERVAL = "interval"
    ONE_TIME = "one_time"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class Schedule:
    """Represents a scheduled task."""

    id: str
    name: str
    schedule_type: ScheduleType
    callback: Callable[..., None]
    args: tuple[Any, ...] = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_run: float | None = None
    next_run: float | None = None
    max_runs: int | None = None
    run_count: int = 0
    cron_expression: str | None = None
    interval_seconds: float | None = None


class CronExpression:
    """Cron expression parser and matcher."""

    def __init__(
        self,
        minute: str,
        hour: str,
        day_of_month: str,
        month: str,
        day_of_week: str,
    ) -> None:
        """Initialize cron expression."""
        self.minute = minute
        self.hour = hour
        self.day_of_month = day_of_month
        self.month = month
        self.day_of_week = day_of_week

    @classmethod
    def parse(cls, expression: str) -> CronExpression:
        """Parse a cron expression string."""
        parts = expression.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {expression}")
        return cls(*parts)

    def matches(self, dt: datetime) -> bool:
        """Check if this cron expression matches the given datetime."""
        python_weekday = dt.weekday()
        cron_weekday = (python_weekday + 1) % 7

        return (
            self._matches_field(self.minute, dt.minute, 0, 59)
            and self._matches_field(self.hour, dt.hour, 0, 23)
            and self._matches_field(self.day_of_month, dt.day, 1, 31)
            and self._matches_field(self.month, dt.month, 1, 12)
            and self._matches_field(self.day_of_week, cron_weekday, 0, 6)
        )

    def _matches_field(
        self,
        pattern: str,
        value: int,
        min_val: int,
        max_val: int,
    ) -> bool:
        """Check if a cron field matches a value."""
        if pattern == "*":
            return True

        if "/" in pattern:
            base, step_str = pattern.split("/")
            step = int(step_str)
            if base == "*":
                return value % step == 0
            return value >= int(base) and (value - int(base)) % step == 0

        if "-" in pattern:
            start, end = pattern.split("-")
            return int(start) <= value <= int(end)

        if "," in pattern:
            values = [int(v) for v in pattern.split(",")]
            return value in values

        return int(pattern) == value


class TimerManager:
    """Manages scheduled tasks."""

    def __init__(self) -> None:
        """Initialize timer manager."""
        self._schedules: dict[str, Schedule] = {}
        self._running = False
        self._check_interval = 1.0

    def add_cron_schedule(
        self,
        schedule_id: str,
        name: str,
        cron_expression: str,
        callback: Callable[..., None],
        *args: Any,
        **kwargs: Any,
    ) -> Schedule:
        """Add a cron-based schedule."""
        cron = CronExpression.parse(cron_expression)
        next_run = self._calculate_next_cron_run(cron, time.time())

        schedule = Schedule(
            id=schedule_id,
            name=name,
            schedule_type=ScheduleType.CRON,
            callback=callback,
            args=args,
            kwargs=kwargs,
            cron_expression=cron_expression,
            next_run=next_run,
        )
        self._schedules[schedule_id] = schedule
        return schedule

    def add_interval_schedule(
        self,
        schedule_id: str,
        name: str,
        interval_seconds: float,
        callback: Callable[..., None],
        *args: Any,
        **kwargs: Any,
    ) -> Schedule:
        """Add an interval-based schedule."""
        schedule = Schedule(
            id=schedule_id,
            name=name,
            schedule_type=ScheduleType.INTERVAL,
            callback=callback,
            args=args,
            kwargs=kwargs,
            interval_seconds=interval_seconds,
            next_run=time.time() + interval_seconds,
        )
        self._schedules[schedule_id] = schedule
        return schedule

    def add_one_time_schedule(
        self,
        schedule_id: str,
        name: str,
        run_at: float,
        callback: Callable[..., None],
        *args: Any,
        **kwargs: Any,
    ) -> Schedule:
        """Add a one-time schedule."""
        schedule = Schedule(
            id=schedule_id,
            name=name,
            schedule_type=ScheduleType.ONE_TIME,
            callback=callback,
            args=args,
            kwargs=kwargs,
            next_run=run_at,
        )
        self._schedules[schedule_id] = schedule
        return schedule

    def add_daily_schedule(
        self,
        schedule_id: str,
        name: str,
        hour: int,
        minute: int,
        callback: Callable[..., None],
        *args: Any,
        **kwargs: Any,
    ) -> Schedule:
        """Add a daily schedule at a specific time."""
        cron_expr = f"{minute} {hour} * * *"
        return self.add_cron_schedule(
            schedule_id, name, cron_expr, callback, *args, **kwargs
        )

    def add_weekly_schedule(
        self,
        schedule_id: str,
        name: str,
        day_of_week: int,
        hour: int,
        minute: int,
        callback: Callable[..., None],
        *args: Any,
        **kwargs: Any,
    ) -> Schedule:
        """Add a weekly schedule at a specific time."""
        cron_expr = f"{minute} {hour} * * {day_of_week}"
        return self.add_cron_schedule(
            schedule_id, name, cron_expr, callback, *args, **kwargs
        )

    def remove_schedule(self, schedule_id: str) -> bool:
        """Remove a schedule."""
        if schedule_id in self._schedules:
            del self._schedules[schedule_id]
            return True
        return False

    def get_schedule(self, schedule_id: str) -> Schedule | None:
        """Get a schedule by ID."""
        return self._schedules.get(schedule_id)

    def list_schedules(self) -> list[Schedule]:
        """List all schedules."""
        return list(self._schedules.values())

    def get_due_schedules(self) -> list[Schedule]:
        """Get schedules that are due to run."""
        now = time.time()
        due = []
        for schedule in self._schedules.values():
            if schedule.enabled and schedule.next_run is not None:
                if schedule.next_run <= now:
                    due.append(schedule)
        return due

    def enable(self, schedule_id: str) -> bool:
        """Enable a schedule."""
        schedule = self._schedules.get(schedule_id)
        if schedule:
            schedule.enabled = True
            return True
        return False

    def disable(self, schedule_id: str) -> bool:
        """Disable a schedule."""
        schedule = self._schedules.get(schedule_id)
        if schedule:
            schedule.enabled = False
            return True
        return False

    def tick(self) -> list[Schedule]:
        """Process one tick of the scheduler."""
        due = self.get_due_schedules()
        for schedule in due:
            self.run_schedule(schedule)
        return due

    def run_schedule(self, schedule: Schedule) -> None:
        """Run a schedule."""
        now = time.time()

        try:
            logger.debug(f"Running schedule: {schedule.name}")
            schedule.callback(*schedule.args, **schedule.kwargs)
            schedule.last_run = now
            schedule.run_count += 1

            if schedule.max_runs and schedule.run_count >= schedule.max_runs:
                self.remove_schedule(schedule.id)
                logger.info(f"Schedule {schedule.name} reached max runs, removed")
                return

            if schedule.schedule_type == ScheduleType.CRON and schedule.cron_expression:
                cron = CronExpression.parse(schedule.cron_expression)
                schedule.next_run = self._calculate_next_cron_run(cron, now)
            elif schedule.schedule_type == ScheduleType.INTERVAL:
                schedule.next_run = now + (schedule.interval_seconds or 0)
            elif schedule.schedule_type == ScheduleType.ONE_TIME:
                schedule.next_run = None
                self.remove_schedule(schedule.id)

        except Exception as e:
            logger.exception(f"Error running schedule {schedule.name}: {e}")

    def _calculate_next_cron_run(self, cron: CronExpression, from_time: float) -> float:
        """Calculate next run time for a cron expression."""
        from datetime import timedelta
        dt = datetime.fromtimestamp(from_time, tz=timezone.utc)

        # Start from next minute
        dt = dt.replace(second=0, microsecond=0) + timedelta(minutes=1)

        # Search up to 1 year forward
        for _ in range(366 * 24 * 60):
            if cron.matches(dt):
                return dt.timestamp()
            dt = dt + timedelta(minutes=1)

        return from_time + 365 * 24 * 60 * 60  # Default to one year


class Timer:
    """Simple timer for one-shot or repeating events."""

    def __init__(
        self,
        interval_seconds: float,
        callback: Callable[..., None],
        *args: Any,
        repeat: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize timer."""
        self.interval_seconds = interval_seconds
        self.callback = callback
        self.args = args
        self.kwargs = kwargs
        self.repeat = repeat
        self._start_time: float | None = None
        self._enabled = False

    def start(self) -> None:
        """Start the timer."""
        self._start_time = time.time()
        self._enabled = True

    def stop(self) -> None:
        """Stop the timer."""
        self._enabled = False

    def reset(self) -> None:
        """Reset the timer."""
        self._start_time = None
        self._enabled = False

    def time_until_fire(self) -> float | None:
        """Get seconds until timer fires. None if not started."""
        if self._start_time is None:
            return None
        elapsed = time.time() - self._start_time
        remaining = self.interval_seconds - elapsed
        return max(0.0, remaining)

    def is_due(self) -> bool:
        """Check if timer is due."""
        if not self._enabled or self._start_time is None:
            return False
        return self.time_until_fire() == 0.0

    def tick(self) -> bool:
        """Process one tick. Returns True if fired."""
        if not self.is_due():
            return False

        try:
            self.callback(*self.args, **self.kwargs)
        except Exception as e:
            logger.exception(f"Timer callback failed: {e}")

        if self.repeat:
            self._start_time = time.time()
        else:
            self._enabled = False
            self._start_time = None

        return True


def create_cron_timer(
    schedule_id: str,
    name: str,
    cron_expression: str,
    callback: Callable[..., None],
    *args: Any,
    **kwargs: Any,
) -> TimerManager:
    """Create a timer manager with a single cron schedule."""
    manager = TimerManager()
    manager.add_cron_schedule(schedule_id, name, cron_expression, callback, *args, **kwargs)
    return manager


def create_interval_timer(
    interval_seconds: float,
    callback: Callable[..., None],
    *args: Any,
    repeat: bool = True,
    **kwargs: Any,
) -> Timer:
    """Create a simple interval timer."""
    return Timer(interval_seconds, callback, *args, repeat=repeat, **kwargs)
