"""Recurrence rules for reminders — v0.5 scheduling engine.

A ``RecurrenceRule`` describes a repeating schedule in the style of a
minimal RFC 5545 RRULE: a frequency (daily / weekly / monthly), an
interval ("every N units"), and optional bounds (``until`` or
``count``). The rule is a pure value object: it computes the next
occurrence after a given date but holds no state of its own. State
(how many occurrences have fired) lives on the Reminder aggregate
(``occurrences``), which keeps the rule immutable and testable.

The engine (see ``growth.application.scheduler``) advances recurring
reminders: when a due reminder fires and the rule still has a next
occurrence, the reminder is re-armed with ``due_at`` set to it.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

__all__ = ["RecurrenceFrequency", "RecurrenceRule"]


class RecurrenceFrequency(StrEnum):
    """Unit of recurrence."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


def _days_in_month(year: int, month: int) -> int:
    """Number of days in ``month`` of ``year`` (handles leap years)."""
    return calendar.monthrange(year, month)[1]


@dataclass(frozen=True, slots=True)
class RecurrenceRule:
    """Immutable description of a repeating schedule.

    Args:
        freq: Unit of recurrence (daily, weekly, monthly).
        interval: Repeat every ``interval`` units (>= 1).
        until: Last allowed occurrence time (inclusive); ``None`` = no
            end date.
        count: Maximum number of occurrences; ``None`` = unlimited.

    The rule is exhausted when either bound is hit: an occurrence after
    ``until``, or more than ``count`` total occurrences.
    """

    freq: RecurrenceFrequency
    interval: int = 1
    until: datetime | None = None
    count: int | None = None

    def __post_init__(self) -> None:
        if self.interval < 1:
            raise ValueError(f"interval must be >= 1, got {self.interval}")
        if self.count is not None and self.count < 1:
            raise ValueError(f"count must be >= 1, got {self.count}")

    def next_occurrence(self, current: datetime, occurrences: int) -> datetime | None:
        """Next due time strictly after ``current``.

        Args:
            current: The occurrence that just fired.
            occurrences: How many times this series has already fired
                (including the one that just fired). Used to enforce
                ``count``.

        Returns:
            The next ``datetime``, or ``None`` when the series is
            exhausted (``until`` passed or ``count`` reached).
        """
        candidate = self._advance(current)
        if self.until is not None and candidate > self.until:
            return None
        if self.count is not None and occurrences >= self.count:
            return None
        return candidate

    def _advance(self, current: datetime) -> datetime:
        """Compute the occurrence after ``current`` without bounds."""
        if self.freq is RecurrenceFrequency.DAILY:
            return current + timedelta(days=self.interval)
        if self.freq is RecurrenceFrequency.WEEKLY:
            return current + timedelta(weeks=self.interval)

        # Monthly: add calendar months, clamping the day to the target
        # month's length (Jan 31 + 1 month -> Feb 28/29).
        month_index = current.month - 1 + self.interval
        year = current.year + month_index // 12
        month = month_index % 12 + 1
        day = min(current.day, _days_in_month(year, month))
        return current.replace(year=year, month=month, day=day)
