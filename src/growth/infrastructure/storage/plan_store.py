"""Plan store — persists the last applied canonical plan for downstream consumers.

The export and sync CLI commands need the *intended* state — the raw plan
payload — to reconstruct a ``CanonicalPlan`` faithfully. The entity tree
(Workspace → Project → Goal → Milestone → Task) loses information during
materialisation (emoji, weak flags, subtask templates, priorities), so the
raw payload is persisted here at apply time.

Each ``plan apply`` appends a row; ``latest()`` returns the most recent
plan for a space.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from growth.domain.shared import SpaceId

__all__ = ["PlanStore", "StoredPlan", "init_plan_store"]


def init_plan_store(db: sqlite3.Connection) -> None:
    """Create the ``plans`` table if it does not already exist."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            space_id TEXT NOT NULL,
            project_name TEXT NOT NULL,
            raw_payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    db.commit()


@dataclass(frozen=True, slots=True)
class StoredPlan:
    """A single persisted plan record."""

    space_id: SpaceId
    project_name: str
    raw_payload: dict[str, Any]
    created_at: datetime


class PlanStore:
    """Repository for the plan history table."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def save(
        self,
        space_id: SpaceId,
        project_name: str,
        raw_payload: dict[str, Any],
        created_at: datetime,
    ) -> None:
        """Append a plan record."""
        self._db.execute(
            """
            INSERT INTO plans (space_id, project_name, raw_payload, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                str(space_id),
                project_name,
                json.dumps(raw_payload, default=str),
                created_at.isoformat(),
            ),
        )
        self._db.commit()

    def latest(self, space_id: SpaceId) -> StoredPlan | None:
        """Return the most recent plan for ``space_id``, or ``None``."""
        row = self._db.execute(
            """
            SELECT * FROM plans
            WHERE space_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (str(space_id),),
        ).fetchone()
        if row is None:
            return None
        return StoredPlan(
            space_id=SpaceId(UUID(row["space_id"])),
            project_name=row["project_name"],
            raw_payload=json.loads(row["raw_payload"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
