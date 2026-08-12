"""Reminders domain — time-based notifications attached to tasks/goals.

v0.5 introduces the reminder aggregate: a lightweight, time-bound
notification tied to a target (space, task, or goal). Reminders are
*fired* by the scheduling engine when ``due_at`` passes while the
status is ``PENDING``; users may also dismiss or cancel them.

The scheduling engine (``growth.application.scheduler``) advances
recurring reminders using ``RecurrenceRule``; the Google Calendar
projection lands later in v0.5. This module ships the aggregate,
statuses, recurrence support, and the ``ReminderDue`` event.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from growth.domain.reminders.recurrence import (
    RecurrenceFrequency,
    RecurrenceRule,
)
from growth.domain.shared import InternalId, SpaceId

__all__ = [
    "RecurrenceFrequency",
    "RecurrenceRule",
    "Reminder",
    "ReminderDue",
    "ReminderStatus",
    "ReminderTarget",
]


class ReminderStatus(StrEnum):
    """Lifecycle of a reminder."""

    PENDING = "pending"
    FIRED = "fired"
    DISMISSED = "dismissed"
    CANCELLED = "cancelled"


class ReminderTarget(StrEnum):
    """What a reminder is attached to."""

    SPACE = "space"
    TASK = "task"
    GOAL = "goal"


@dataclass(slots=True)
class Reminder:
    """A single time-bound notification.

    Immutable identity (``id``); mutable fields (``status``) are updated
    in place, mirroring the Attachment aggregate.
    """

    id: InternalId
    space_id: SpaceId
    title: str
    due_at: datetime
    created_at: datetime
    updated_at: datetime
    target_type: ReminderTarget = ReminderTarget.SPACE
    target_id: InternalId | None = None
    status: ReminderStatus = ReminderStatus.PENDING
    recurrence: RecurrenceRule | None = None
    occurrences: int = 0

    def is_due(self, now: datetime) -> bool:
        """``True`` when the reminder should have fired already."""
        return self.status is ReminderStatus.PENDING and self.due_at <= now

    @property
    def is_recurring(self) -> bool:
        """``True`` when this reminder re-arms itself after firing."""
        return self.recurrence is not None


@dataclass(frozen=True, slots=True)
class ReminderDue:
    """Published when a pending reminder's due time passes."""

    reminder_id: InternalId
    space_id: SpaceId
    title: str
    due_at: datetime

    @property
    def event_type(self) -> str:
        return "reminders.reminder.due"
