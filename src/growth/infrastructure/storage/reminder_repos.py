"""SQLite-backed repository for the Reminder aggregate."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from uuid import UUID

from growth.application.ports.repository import EntityNotFoundError
from growth.domain.reminders import Reminder, ReminderStatus, ReminderTarget
from growth.domain.shared import InternalId, SpaceId

__all__ = ["ReminderRepository", "init_reminder_db"]


def init_reminder_db(db: sqlite3.Connection) -> None:
    """Create the reminders table if missing."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS reminders (
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
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_reminders_due "
        "ON reminders (space_id, status, due_at)"
    )
    db.commit()


def _row_to_reminder(row: sqlite3.Row) -> Reminder:
    return Reminder(
        id=InternalId(UUID(row["id"])),
        space_id=SpaceId(UUID(row["space_id"])),
        title=row["title"],
        target_type=ReminderTarget(row["target_type"]),
        target_id=InternalId(UUID(row["target_id"])) if row["target_id"] else None,
        due_at=datetime.fromisoformat(row["due_at"]),
        status=ReminderStatus(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


class ReminderRepository:
    """SQLite persistence for Reminder aggregates."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get(self, id: InternalId) -> Reminder:
        row = self._db.execute(
            "SELECT * FROM reminders WHERE id = ?", (str(id.value),)
        ).fetchone()
        if row is None:
            raise EntityNotFoundError(f"Reminder {id} not found")
        return _row_to_reminder(row)

    def save(self, reminder: Reminder) -> None:
        row = self._db.execute(
            "SELECT id FROM reminders WHERE id = ?", (str(reminder.id.value),)
        ).fetchone()
        if row is None:
            self._db.execute(
                """
                INSERT INTO reminders (
                    id, space_id, title, target_type, target_id,
                    due_at, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(reminder.id.value),
                    str(reminder.space_id.value),
                    reminder.title,
                    reminder.target_type.value,
                    str(reminder.target_id.value) if reminder.target_id else None,
                    reminder.due_at.isoformat(),
                    reminder.status.value,
                    reminder.created_at.isoformat(),
                    reminder.updated_at.isoformat(),
                ),
            )
        else:
            self._db.execute(
                """
                UPDATE reminders SET title=?, target_type=?, target_id=?,
                   due_at=?, status=?, updated_at=? WHERE id=?
                """,
                (
                    reminder.title,
                    reminder.target_type.value,
                    str(reminder.target_id.value) if reminder.target_id else None,
                    reminder.due_at.isoformat(),
                    reminder.status.value,
                    reminder.updated_at.isoformat(),
                    str(reminder.id.value),
                ),
            )
        self._db.commit()

    def delete(self, id: InternalId) -> None:
        cur = self._db.execute("DELETE FROM reminders WHERE id = ?", (str(id.value),))
        if cur.rowcount == 0:
            raise EntityNotFoundError(f"Reminder {id} not found")
        self._db.commit()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_by_space(self, space_id: SpaceId) -> list[Reminder]:
        rows = self._db.execute(
            "SELECT * FROM reminders WHERE space_id = ? ORDER BY due_at ASC",
            (str(space_id.value),),
        ).fetchall()
        return [_row_to_reminder(r) for r in rows]

    def list_pending(self, space_id: SpaceId) -> list[Reminder]:
        rows = self._db.execute(
            "SELECT * FROM reminders WHERE space_id = ? AND status = 'pending' "
            "ORDER BY due_at ASC",
            (str(space_id.value),),
        ).fetchall()
        return [_row_to_reminder(r) for r in rows]

    def list_due(self, space_id: SpaceId, now: datetime) -> list[Reminder]:
        rows = self._db.execute(
            "SELECT * FROM reminders WHERE space_id = ? AND status = 'pending' "
            "AND due_at <= ? ORDER BY due_at ASC",
            (str(space_id.value), now.isoformat()),
        ).fetchall()
        return [_row_to_reminder(r) for r in rows]
