"""Scheduling engine — fires due reminders and re-arms recurring ones.

The scheduler is the v0.5 "clock" of Growth OS: given the current time
it finds every pending reminder whose ``due_at`` has passed, fires it
(publishes a ``ReminderDue`` event through the ``EventDispatcher``
port), and — when the reminder carries a ``RecurrenceRule`` and the
series is not exhausted — re-arms it with the next occurrence.

Dependencies are ports only (``ReminderRepository``,
``EventDispatcher``), so the engine is fully offline and testable; the
composition root wires real infrastructure. Failure isolation mirrors
the event dispatcher: one bad row must not stop the sweep.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from growth.application.ports.event_dispatcher import EventDispatcher
from growth.application.ports.reminders import ReminderRepository
from growth.domain.reminders import Reminder, ReminderDue, ReminderStatus
from growth.domain.shared import SpaceId

__all__ = ["Scheduler", "SweepResult"]


@dataclass(slots=True)
class SweepResult:
    """Outcome of one ``Scheduler.sweep`` run.

    Attributes:
        fired: Reminders that fired and whose series is now complete.
        rescheduled: Recurring reminders that fired and were re-armed
            with a new ``due_at`` (status back to PENDING).
        errors: Reminders that could not be processed (isolated).
    """

    fired: list[Reminder] = field(default_factory=list)
    rescheduled: list[Reminder] = field(default_factory=list)
    errors: int = 0

    @property
    def total(self) -> int:
        """Number of reminders touched by the sweep."""
        return len(self.fired) + len(self.rescheduled)


class Scheduler:
    """Fire due reminders and advance recurring schedules."""

    def __init__(
        self,
        reminders: ReminderRepository,
        dispatcher: EventDispatcher,
    ) -> None:
        self._reminders = reminders
        self._dispatcher = dispatcher

    def sweep(self, space_id: SpaceId, now: datetime | None = None) -> SweepResult:
        """Process every pending reminder due at ``now`` (default: UTC now).

        Each due reminder is handled independently: a failure marks one
        error and processing continues. Reminders are persisted before
        their ``ReminderDue`` event is dispatched, so handlers observe
        consistent state.
        """
        now = now or datetime.now(UTC)
        result = SweepResult()

        for reminder in self._reminders.list_due(space_id, now):
            try:
                self._process(reminder, now, result)
            except Exception:
                result.errors += 1

        return result

    def _process(self, reminder: Reminder, now: datetime, result: SweepResult) -> None:
        """Fire one reminder, dispatching the event and re-arming if needed."""

        due_at = reminder.due_at
        reminder.occurrences += 1

        next_due = None
        if reminder.recurrence is not None:
            next_due = reminder.recurrence.next_occurrence(due_at, reminder.occurrences)

        if next_due is not None:
            reminder.status = ReminderStatus.PENDING
            reminder.due_at = next_due
        else:
            reminder.status = ReminderStatus.FIRED

        reminder.updated_at = now
        self._reminders.save(reminder)
        if next_due is not None:
            result.rescheduled.append(reminder)
        else:
            result.fired.append(reminder)
        self._dispatcher.dispatch(
            ReminderDue(
                reminder_id=reminder.id,
                space_id=reminder.space_id,
                title=reminder.title,
                due_at=due_at,
            )
        )
