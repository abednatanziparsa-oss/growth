"""Integration tests for the Scheduler (real repo + fake dispatcher)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime

from growth.application.ports.event_dispatcher import Event
from growth.application.scheduler import Scheduler
from growth.domain.reminders import (
    RecurrenceFrequency,
    RecurrenceRule,
    Reminder,
    ReminderDue,
    ReminderStatus,
    ReminderTarget,
)
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId
from growth.infrastructure.storage.reminder_repos import (
    ReminderRepository,
    init_reminder_db,
)


@dataclass
class FakeDispatcher:
    """Records dispatched events for assertions."""

    events: list[Event] = field(default_factory=list)

    def subscribe(self, event_type: str, handler) -> None:  # pragma: no cover
        raise NotImplementedError

    def dispatch(self, event: Event) -> None:
        self.events.append(event)


def _new_repo() -> ReminderRepository:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    init_reminder_db(db)
    return ReminderRepository(db)


def _reminder(
    *,
    title: str = "Study",
    due_at: datetime = datetime(2026, 8, 12, 9, 0, tzinfo=UTC),
    recurrence: RecurrenceRule | None = None,
) -> Reminder:
    now = datetime(2026, 8, 12, 8, 0, tzinfo=UTC)
    return Reminder(
        id=InternalId(),
        space_id=DEFAULT_SPACE_ID,
        title=title,
        due_at=due_at,
        target_type=ReminderTarget.SPACE,
        recurrence=recurrence,
        created_at=now,
        updated_at=now,
    )


NOW = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)


class TestSweepOneShot:
    def test_fires_due_reminder_and_dispatches_event(self) -> None:
        repo = _new_repo()
        dispatcher = FakeDispatcher()
        scheduler = Scheduler(repo, dispatcher)
        r = _reminder(
            title="Read chapter", due_at=datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
        )
        repo.save(r)

        result = scheduler.sweep(DEFAULT_SPACE_ID, NOW)

        assert result.total == 1
        assert [x.id for x in result.fired] == [r.id]
        assert result.rescheduled == []
        assert result.errors == 0
        assert repo.get(r.id).status is ReminderStatus.FIRED
        assert len(dispatcher.events) == 1
        event = dispatcher.events[0]
        assert isinstance(event, ReminderDue)
        assert event.reminder_id == r.id
        assert event.due_at == r.due_at  # original due time, pre-mutation
        assert event.title == "Read chapter"

    def test_ignores_future_reminders(self) -> None:
        repo = _new_repo()
        dispatcher = FakeDispatcher()
        scheduler = Scheduler(repo, dispatcher)
        future = _reminder(
            title="later", due_at=datetime(2026, 8, 12, 11, 0, tzinfo=UTC)
        )
        repo.save(future)

        result = scheduler.sweep(DEFAULT_SPACE_ID, NOW)

        assert result.total == 0
        assert repo.get(future.id).status is ReminderStatus.PENDING
        assert dispatcher.events == []

    def test_sweep_empty(self) -> None:
        repo = _new_repo()
        scheduler = Scheduler(repo, FakeDispatcher())

        result = scheduler.sweep(DEFAULT_SPACE_ID, NOW)

        assert result.total == 0
        assert result.fired == []
        assert result.rescheduled == []


class TestSweepRecurring:
    def test_reschedules_recurring_reminder(self) -> None:
        repo = _new_repo()
        dispatcher = FakeDispatcher()
        scheduler = Scheduler(repo, dispatcher)
        rule = RecurrenceRule(freq=RecurrenceFrequency.DAILY)
        r = _reminder(title="Daily habit", recurrence=rule)
        repo.save(r)

        result = scheduler.sweep(DEFAULT_SPACE_ID, NOW)

        assert [x.id for x in result.rescheduled] == [r.id]
        assert result.fired == []
        got = repo.get(r.id)
        assert got.status is ReminderStatus.PENDING
        assert got.due_at == datetime(2026, 8, 13, 9, 0, tzinfo=UTC)
        assert got.occurrences == 1
        assert len(dispatcher.events) == 1

    def test_series_ends_at_count(self) -> None:
        repo = _new_repo()
        scheduler = Scheduler(repo, FakeDispatcher())
        rule = RecurrenceRule(freq=RecurrenceFrequency.DAILY, count=2)
        r = _reminder(title="Twice", recurrence=rule)
        repo.save(r)

        first = scheduler.sweep(DEFAULT_SPACE_ID, NOW)
        assert [x.id for x in first.rescheduled] == [r.id]
        got = repo.get(r.id)
        assert got.status is ReminderStatus.PENDING
        assert got.occurrences == 1

        second_now = datetime(2026, 8, 13, 10, 0, tzinfo=UTC)
        second = scheduler.sweep(DEFAULT_SPACE_ID, second_now)
        assert [x.id for x in second.fired] == [r.id]
        got = repo.get(r.id)
        assert got.status is ReminderStatus.FIRED
        assert got.occurrences == 2

    def test_series_ends_at_until(self) -> None:
        repo = _new_repo()
        scheduler = Scheduler(repo, FakeDispatcher())
        until = datetime(2026, 8, 12, 9, 30, tzinfo=UTC)
        rule = RecurrenceRule(freq=RecurrenceFrequency.DAILY, until=until)
        r = _reminder(title="Bounded", recurrence=rule)
        repo.save(r)

        result = scheduler.sweep(DEFAULT_SPACE_ID, NOW)

        # Next occurrence (Aug 13) is past `until` -> series done.
        assert [x.id for x in result.fired] == [r.id]
        assert repo.get(r.id).status is ReminderStatus.FIRED

    def test_fire_does_not_touch_other_spaces(self) -> None:
        from growth.domain.shared import SpaceId

        repo = _new_repo()
        scheduler = Scheduler(repo, FakeDispatcher())
        other = SpaceId()
        r = _reminder(title="mine", due_at=datetime(2026, 8, 12, 9, 0, tzinfo=UTC))
        repo.save(r)
        theirs = Reminder(
            id=InternalId(),
            space_id=other,
            title="theirs",
            due_at=datetime(2026, 8, 12, 9, 0, tzinfo=UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        repo.save(theirs)

        scheduler.sweep(DEFAULT_SPACE_ID, NOW)

        assert repo.get(r.id).status is ReminderStatus.FIRED
        assert repo.get(theirs.id).status is ReminderStatus.PENDING


class TestFailureIsolation:
    def test_one_bad_row_does_not_stop_sweep(self) -> None:
        repo = _new_repo()
        dispatcher = FakeDispatcher()
        scheduler = Scheduler(repo, dispatcher)
        good = _reminder(title="good", due_at=datetime(2026, 8, 12, 9, 0, tzinfo=UTC))
        bad = _reminder(title="bad", due_at=datetime(2026, 8, 12, 8, 0, tzinfo=UTC))
        repo.save(good)
        repo.save(bad)

        original_save = repo.save

        def flaky_save(reminder: Reminder) -> None:
            if reminder.title == "bad":
                raise RuntimeError("boom")
            original_save(reminder)

        repo.save = flaky_save  # type: ignore[method-assign]

        result = scheduler.sweep(DEFAULT_SPACE_ID, NOW)

        assert result.errors == 1
        assert [x.id for x in result.fired] == [good.id]
        assert repo.get(good.id).status is ReminderStatus.FIRED
        # bad reminder stays untouched (failed before save)
        assert repo.get(bad.id).status is ReminderStatus.PENDING
