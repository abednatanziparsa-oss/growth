"""Unit tests for the Reminder aggregate and ReminderDue event."""

from __future__ import annotations

from datetime import UTC, datetime

from growth.application.ports.event_dispatcher import Event
from growth.domain.reminders import (
    Reminder,
    ReminderDue,
    ReminderStatus,
    ReminderTarget,
)
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId


def _reminder(**kw: object) -> Reminder:
    now = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
    defaults: dict[str, object] = {
        "id": InternalId(),
        "space_id": DEFAULT_SPACE_ID,
        "title": "Study algebra",
        "due_at": now,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(kw)
    return Reminder(**defaults)  # type: ignore[arg-type]


class TestReminder:
    def test_defaults(self) -> None:
        r = _reminder()
        assert r.status is ReminderStatus.PENDING
        assert r.target_type is ReminderTarget.SPACE
        assert r.target_id is None

    def test_is_due_when_pending_and_past(self) -> None:
        now = datetime(2026, 8, 12, 13, 0, tzinfo=UTC)
        r = _reminder(due_at=datetime(2026, 8, 12, 9, 0, tzinfo=UTC))
        assert r.is_due(now)

    def test_not_due_in_future(self) -> None:
        now = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
        r = _reminder(due_at=datetime(2026, 8, 12, 13, 0, tzinfo=UTC))
        assert not r.is_due(now)

    def test_not_due_when_fired(self) -> None:
        now = datetime(2026, 8, 12, 13, 0, tzinfo=UTC)
        r = _reminder(
            due_at=datetime(2026, 8, 12, 9, 0, tzinfo=UTC),
            status=ReminderStatus.FIRED,
        )
        assert not r.is_due(now)

    def test_due_at_boundary_inclusive(self) -> None:
        now = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
        r = _reminder(due_at=now)
        assert r.is_due(now)

    def test_task_target(self) -> None:
        task_id = InternalId()
        r = _reminder(
            target_type=ReminderTarget.TASK,
            target_id=task_id,
        )
        assert r.target_type is ReminderTarget.TASK
        assert r.target_id == task_id


class TestReminderDue:
    def test_event_type(self) -> None:
        event: Event = ReminderDue(
            reminder_id=InternalId(),
            space_id=DEFAULT_SPACE_ID,
            title="x",
            due_at=datetime(2026, 8, 12, tzinfo=UTC),
        )
        assert event.event_type == "reminders.reminder.due"
