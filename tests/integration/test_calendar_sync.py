"""Integration tests for CalendarSync (identity-map idempotency)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from growth.application.calendar_sync import CalendarSync
from growth.domain.reminders import (
    Reminder,
    ReminderStatus,
    ReminderTarget,
)
from growth.domain.reminders.recurrence import (
    RecurrenceFrequency,
    RecurrenceRule,
)
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId
from growth.infrastructure.projections.calendar import CalendarProjection
from growth.infrastructure.storage.identity_map import (
    IdentityMap,
    init_identity_map,
)
from growth.infrastructure.storage.reminder_repos import (
    ReminderRepository,
    init_reminder_db,
)

NOW = datetime(2026, 8, 13, 10, 0, tzinfo=UTC)


class FakeAdapter:
    def __init__(self) -> None:
        self.events: dict[str, object] = {}
        self.next_id = 0
        self.create_calls = 0
        self.update_calls = 0
        self.fail_create: set[str] = set()

    def create_event(self, payload: object) -> str:
        self.create_calls += 1
        if payload.summary in self.fail_create:  # type: ignore[attr-defined]
            raise RuntimeError("provider down")
        self.next_id += 1
        event_id = f"evt-{self.next_id}"
        self.events[event_id] = payload
        return event_id

    def update_event(self, event_id: str, payload: object) -> None:
        self.update_calls += 1
        self.events[event_id] = payload


def _new_db() -> tuple[sqlite3.Connection, ReminderRepository, IdentityMap]:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    init_reminder_db(db)
    init_identity_map(db)
    return db, ReminderRepository(db), IdentityMap(db)


def _reminder(*, title: str = "Study", due: datetime | None = None) -> Reminder:
    return Reminder(
        id=InternalId(),
        space_id=DEFAULT_SPACE_ID,
        title=title,
        due_at=due or datetime(2026, 8, 13, 18, 0, tzinfo=UTC),
        target_type=ReminderTarget.SPACE,
        created_at=NOW,
        updated_at=NOW,
    )


def _sync(
    db: sqlite3.Connection, repo: ReminderRepository, adapter: FakeAdapter
) -> CalendarSync:
    return CalendarSync(
        repo,
        IdentityMap(db),
        CalendarProjection(),
        adapter,
    )


class TestCalendarSync:
    def test_creates_events_for_pending_reminders(self) -> None:
        db, repo, _ = _new_db()
        r1 = _reminder(title="Math review")
        r2 = _reminder(title="Physics", due=datetime(2026, 8, 14, 9, 0, tzinfo=UTC))
        repo.save(r1)
        repo.save(r2)
        adapter = FakeAdapter()
        sync = _sync(db, repo, adapter)

        result = sync.push(DEFAULT_SPACE_ID, now=NOW)

        assert result.created == ["Math review", "Physics"]
        assert result.updated == []
        assert result.errors == 0
        assert adapter.create_calls == 2
        assert len(adapter.events) == 2

    def test_second_push_updates_instead_of_duplicating(self) -> None:
        db, repo, _ = _new_db()
        r = _reminder(title="Math review")
        repo.save(r)
        adapter = FakeAdapter()
        sync = _sync(db, repo, adapter)

        sync.push(DEFAULT_SPACE_ID, now=NOW)
        r.title = "Math review (updated)"
        repo.save(r)
        result = sync.push(DEFAULT_SPACE_ID, now=NOW)

        assert result.created == []
        assert result.updated == ["Math review (updated)"]
        assert adapter.create_calls == 1
        assert adapter.update_calls == 1
        assert len(adapter.events) == 1

    def test_past_due_reminders_are_skipped(self) -> None:
        db, repo, _ = _new_db()
        r = _reminder(title="Old", due=datetime(2026, 8, 12, 9, 0, tzinfo=UTC))
        repo.save(r)
        adapter = FakeAdapter()
        sync = _sync(db, repo, adapter)

        result = sync.push(DEFAULT_SPACE_ID, now=NOW)

        assert result.created == []
        assert result.skipped == []
        assert adapter.create_calls == 0

    def test_fired_reminders_are_not_pushed(self) -> None:
        db, repo, _ = _new_db()

        r = _reminder(title="Done")
        r.status = ReminderStatus.FIRED
        repo.save(r)
        adapter = FakeAdapter()
        sync = _sync(db, repo, adapter)

        result = sync.push(DEFAULT_SPACE_ID, now=NOW)

        assert result.created == []
        assert adapter.create_calls == 0

    def test_failure_is_isolated_per_reminder(self) -> None:
        db, repo, _ = _new_db()
        good = _reminder(title="Good")
        bad = _reminder(title="Bad")
        repo.save(good)
        repo.save(bad)
        adapter = FakeAdapter()
        adapter.fail_create = {"Bad"}
        sync = _sync(db, repo, adapter)

        result = sync.push(DEFAULT_SPACE_ID, now=NOW)

        assert result.created == ["Good"]
        assert result.errors == 1
        assert len(adapter.events) == 1

    def test_recurring_reminder_pushes_current_occurrence(self) -> None:
        db, repo, _ = _new_db()
        rule = RecurrenceRule(freq=RecurrenceFrequency.DAILY, interval=1)
        r = Reminder(
            id=InternalId(),
            space_id=DEFAULT_SPACE_ID,
            title="Daily habit",
            due_at=datetime(2026, 8, 13, 18, 0, tzinfo=UTC),
            target_type=ReminderTarget.SPACE,
            recurrence=rule,
            created_at=NOW,
            updated_at=NOW,
        )
        repo.save(r)
        adapter = FakeAdapter()
        sync = _sync(db, repo, adapter)

        result = sync.push(DEFAULT_SPACE_ID, now=NOW)

        assert result.created == ["Daily habit"]
        assert adapter.create_calls == 1
