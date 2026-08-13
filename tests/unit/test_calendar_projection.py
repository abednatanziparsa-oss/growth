"""Unit tests for the Calendar projection (reminder -> event payload)."""

from __future__ import annotations

from datetime import UTC, datetime

from growth.domain.reminders import Reminder, ReminderTarget
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId
from growth.infrastructure.projections.calendar import (
    DEFAULT_DURATION,
    CalendarProjection,
)


def _reminder(*, title: str = "Study", due: datetime | None = None) -> Reminder:
    now = datetime(2026, 8, 13, 8, 0, tzinfo=UTC)
    return Reminder(
        id=InternalId(),
        space_id=DEFAULT_SPACE_ID,
        title=title,
        due_at=due or datetime(2026, 8, 13, 12, 0, tzinfo=UTC),
        target_type=ReminderTarget.SPACE,
        created_at=now,
        updated_at=now,
    )


class TestCalendarProjection:
    def test_projects_summary_and_times(self) -> None:
        reminder = _reminder(title="Practice graphs")
        payload = CalendarProjection().project(reminder)

        assert payload.summary == "Practice graphs"
        assert payload.start == "2026-08-13T12:00:00+00:00"
        assert payload.end == "2026-08-13T12:30:00+00:00"  # + DEFAULT_DURATION

    def test_default_duration_is_thirty_minutes(self) -> None:
        assert DEFAULT_DURATION.total_seconds() == 1800

    def test_description_carries_target(self) -> None:
        payload = CalendarProjection().project(_reminder())
        assert "space:space" in payload.description

    def test_task_target_appears_in_description(self) -> None:
        reminder = _reminder()
        reminder.target_type = ReminderTarget.TASK
        reminder.target_id = InternalId()
        payload = CalendarProjection().project(reminder)
        assert f"task:{reminder.target_id}" in payload.description

    def test_timezone_aware_start_iso(self) -> None:
        reminder = _reminder(due=datetime(2026, 8, 14, 6, 30, tzinfo=UTC))
        payload = CalendarProjection().project(reminder)
        assert payload.start.endswith("+00:00")
