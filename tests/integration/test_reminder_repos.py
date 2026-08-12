"""Integration tests for the SQLite ReminderRepository."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from growth.application.ports.reminders import (
    ReminderRepository as ReminderRepositoryPort,
)
from growth.application.ports.repository import EntityNotFoundError
from growth.domain.reminders import (
    RecurrenceFrequency,
    RecurrenceRule,
    Reminder,
    ReminderStatus,
    ReminderTarget,
)
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId, SpaceId
from growth.infrastructure.storage.reminder_repos import (
    ReminderRepository,
    init_reminder_db,
)


def _new_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    init_reminder_db(db)
    return db


def _reminder(
    *,
    title: str = "Study",
    due_at: datetime = datetime(2026, 8, 12, 9, 0, tzinfo=UTC),
    status: ReminderStatus = ReminderStatus.PENDING,
    target: InternalId | None = None,
    space_id=DEFAULT_SPACE_ID,
    recurrence: RecurrenceRule | None = None,
) -> Reminder:
    now = datetime(2026, 8, 12, 8, 0, tzinfo=UTC)
    return Reminder(
        id=InternalId(),
        space_id=space_id,
        title=title,
        due_at=due_at,
        target_type=ReminderTarget.TASK if target else ReminderTarget.SPACE,
        target_id=target,
        status=status,
        recurrence=recurrence,
        created_at=now,
        updated_at=now,
    )


class TestReminderRepository:
    def test_implements_port(self) -> None:
        assert isinstance(ReminderRepository(_new_db()), ReminderRepositoryPort)

    def test_save_and_get(self) -> None:
        db = _new_db()
        repo = ReminderRepository(db)
        r = _reminder(title="Read chapter 1")

        repo.save(r)
        got = repo.get(r.id)

        assert got.title == "Read chapter 1"
        assert got.id == r.id
        assert got.status is ReminderStatus.PENDING

    def test_get_missing_raises(self) -> None:
        db = _new_db()
        repo = ReminderRepository(db)

        with pytest.raises(EntityNotFoundError):
            repo.get(InternalId())

    def test_update_status(self) -> None:
        db = _new_db()
        repo = ReminderRepository(db)
        r = _reminder()

        repo.save(r)
        r.status = ReminderStatus.FIRED
        r.updated_at = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
        repo.save(r)

        assert repo.get(r.id).status is ReminderStatus.FIRED

    def test_delete(self) -> None:
        db = _new_db()
        repo = ReminderRepository(db)
        r = _reminder()

        repo.save(r)
        repo.delete(r.id)

        with pytest.raises(EntityNotFoundError):
            repo.get(r.id)

    def test_delete_missing_raises(self) -> None:
        db = _new_db()
        repo = ReminderRepository(db)

        with pytest.raises(EntityNotFoundError):
            repo.delete(InternalId())

    def test_list_by_space_orders_by_due(self) -> None:
        db = _new_db()
        repo = ReminderRepository(db)
        late = _reminder(title="later", due_at=datetime(2026, 8, 12, 12, 0, tzinfo=UTC))
        early = _reminder(
            title="earlier", due_at=datetime(2026, 8, 12, 7, 0, tzinfo=UTC)
        )
        repo.save(late)
        repo.save(early)

        hits = repo.list_by_space(DEFAULT_SPACE_ID)

        assert [h.title for h in hits] == ["earlier", "later"]

    def test_list_by_space_scoped(self) -> None:
        db = _new_db()
        repo = ReminderRepository(db)
        other_space = SpaceId()
        repo.save(_reminder(title="mine"))
        repo.save(_reminder(title="theirs", space_id=other_space))

        assert len(repo.list_by_space(DEFAULT_SPACE_ID)) == 1
        assert len(repo.list_by_space(other_space)) == 1

    def test_list_pending_excludes_fired(self) -> None:
        db = _new_db()
        repo = ReminderRepository(db)
        repo.save(_reminder(title="pending one"))
        repo.save(_reminder(title="fired one", status=ReminderStatus.FIRED))

        hits = repo.list_pending(DEFAULT_SPACE_ID)

        assert [h.title for h in hits] == ["pending one"]

    def test_list_due_time_filter(self) -> None:
        db = _new_db()
        repo = ReminderRepository(db)
        now = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
        repo.save(
            _reminder(title="past", due_at=datetime(2026, 8, 12, 9, 0, tzinfo=UTC))
        )
        repo.save(_reminder(title="now", due_at=now))
        repo.save(
            _reminder(title="future", due_at=datetime(2026, 8, 12, 11, 0, tzinfo=UTC))
        )
        repo.save(
            _reminder(
                title="fired past",
                due_at=datetime(2026, 8, 12, 9, 0, tzinfo=UTC),
                status=ReminderStatus.FIRED,
            )
        )

        hits = repo.list_due(DEFAULT_SPACE_ID, now)

        assert {h.title for h in hits} == {"past", "now"}

    def test_list_due_empty(self) -> None:
        db = _new_db()
        repo = ReminderRepository(db)

        assert repo.list_due(DEFAULT_SPACE_ID, datetime.now(UTC)) == []

    def test_task_target_roundtrip(self) -> None:
        db = _new_db()
        repo = ReminderRepository(db)
        task_id = InternalId()
        r = _reminder(title="task reminder", target=task_id)

        repo.save(r)
        got = repo.get(r.id)

        assert got.target_type is ReminderTarget.TASK
        assert got.target_id == task_id

    def test_recurrence_roundtrip(self) -> None:
        db = _new_db()
        repo = ReminderRepository(db)
        rule = RecurrenceRule(
            freq=RecurrenceFrequency.WEEKLY,
            interval=2,
            until=datetime(2026, 12, 31, tzinfo=UTC),
            count=10,
        )
        r = _reminder(title="recurring", recurrence=rule)

        repo.save(r)
        got = repo.get(r.id)

        assert got.recurrence == rule
        assert got.recurrence is not None
        assert got.recurrence.freq is RecurrenceFrequency.WEEKLY
        assert got.recurrence.interval == 2
        assert got.recurrence.until == datetime(2026, 12, 31, tzinfo=UTC)
        assert got.recurrence.count == 10

    def test_recurrence_none_by_default(self) -> None:
        db = _new_db()
        repo = ReminderRepository(db)
        r = _reminder()

        repo.save(r)

        assert repo.get(r.id).recurrence is None

    def test_occurrences_persisted(self) -> None:
        db = _new_db()
        repo = ReminderRepository(db)
        r = _reminder()
        repo.save(r)

        got = repo.get(r.id)
        got.occurrences = 3
        repo.save(got)

        assert repo.get(r.id).occurrences == 3

    def test_migrates_legacy_schema(self) -> None:
        """A v0.5-pre DB (no recurrence/occurrences) gets ALTERed in place."""
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.execute(
            """
            CREATE TABLE reminders (
                id TEXT PRIMARY KEY,
                space_id TEXT NOT NULL,
                title TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT,
                due_at TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        init_reminder_db(db)
        cols = {row["name"] for row in db.execute("PRAGMA table_info(reminders)")}

        assert "recurrence" in cols
        assert "occurrences" in cols
