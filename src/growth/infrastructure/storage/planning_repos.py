"""SQLite-backed in-memory repositories for the planning domain.

v0.1 uses an in-memory SQLite database for development. Persistence to
disk (``GROWTH_DATA_DIR/growth.db``) lands in v0.2 when the sync engine
needs durable state.

Design: one repository per aggregate root, with simple CRUD + list-by-parent.
No ORM — raw sqlite3 with dataclass rows.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from uuid import UUID

from growth.application.ports.repository import EntityNotFoundError, Repository
from growth.domain.planning import Goal, Milestone, Priority, Project, Task, Workspace
from growth.domain.shared import InternalId, SpaceId

__all__ = [
    "GoalRepository",
    "MilestoneRepository",
    "ProjectRepository",
    "TaskRepository",
    "WorkspaceRepository",
    "init_db",
    "new_in_memory_db",
]


def new_in_memory_db() -> sqlite3.Connection:
    """Return an in-memory SQLite database with the schema applied.

    Not thread-safe. Designed for single-threaded CLI use.
    Threaded access (future) should use WAL mode.
    """
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    init_db(db)
    return db


def init_db(db: sqlite3.Connection) -> None:
    """Create the planning schema if it does not exist."""
    db.executescript("""
    CREATE TABLE IF NOT EXISTS workspaces (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        space_id TEXT NOT NULL,
        description TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES workspaces(id),
        title TEXT NOT NULL,
        space_id TEXT NOT NULL,
        description TEXT,
        color TEXT,
        emoji TEXT,
        is_archived INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS goals (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL REFERENCES projects(id),
        title TEXT NOT NULL,
        space_id TEXT NOT NULL,
        description TEXT,
        priority TEXT,
        target_date TEXT,
        completed_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS milestones (
        id TEXT PRIMARY KEY,
        goal_id TEXT NOT NULL REFERENCES goals(id),
        title TEXT NOT NULL,
        space_id TEXT NOT NULL,
        target_date TEXT,
        completed_at TEXT,
        "order" INTEGER DEFAULT 0,
        raw_description TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        space_id TEXT NOT NULL,
        description TEXT,
        priority TEXT,
        parent_id TEXT REFERENCES tasks(id),
        due_at TEXT,
        completed_at TEXT,
        tags TEXT DEFAULT '[]',
        estimated_minutes INTEGER,
        source_ref TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------


def _to_priority(raw: str | None) -> Priority | None:
    if raw is None:
        return None
    return Priority(raw)


def _ts(raw: str) -> datetime:
    """Parse an ISO UTC timestamp from SQLite."""
    return datetime.fromisoformat(raw)


def _now() -> str:
    """Current UTC time as ISO string for SQLite storage."""
    return datetime.now(UTC).isoformat()


def _uid(raw: str) -> InternalId:
    return InternalId(UUID(raw))


# ---------------------------------------------------------------------------
# WorkspaceRepository
# ---------------------------------------------------------------------------


class WorkspaceRepository(Repository[Workspace]):
    """SQLite-backed workspace persistence."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def get(self, id: InternalId) -> Workspace:
        row = self._db.execute(
            "SELECT * FROM workspaces WHERE id = ?", (str(id.value),)
        ).fetchone()
        if row is None:
            raise EntityNotFoundError(f"Workspace {id} not found")
        return Workspace(
            id=InternalId(UUID(row["id"])),
            title=row["title"],
            space_id=SpaceId(UUID(row["space_id"])),
            description=row["description"],
            created_at=_ts(row["created_at"]),
            updated_at=_ts(row["updated_at"]),
        )

    def save(self, entity: Workspace) -> None:
        row = self._db.execute(
            "SELECT id FROM workspaces WHERE id = ?", (str(entity.id.value),)
        ).fetchone()
        if row is None:
            self._db.execute(
                """INSERT INTO workspaces (id, title, space_id, description, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    str(entity.id.value),
                    entity.title,
                    str(entity.space_id.value),
                    entity.description,
                    entity.created_at.isoformat(),
                    entity.updated_at.isoformat(),
                ),
            )
        else:
            entity.updated_at = datetime.now(UTC)
            self._db.execute(
                """UPDATE workspaces SET title=?, description=?, updated_at=?
                   WHERE id=?""",
                (
                    entity.title,
                    entity.description,
                    entity.updated_at.isoformat(),
                    str(entity.id.value),
                ),
            )

    def delete(self, id: InternalId) -> None:
        cur = self._db.execute("DELETE FROM workspaces WHERE id = ?", (str(id.value),))
        if cur.rowcount == 0:
            raise EntityNotFoundError(f"Workspace {id} not found")

    def list_all(self) -> list[Workspace]:
        rows = self._db.execute(
            "SELECT * FROM workspaces ORDER BY created_at"
        ).fetchall()
        return [
            Workspace(
                id=_uid(r["id"]),
                title=r["title"],
                space_id=SpaceId(UUID(r["space_id"])),
                description=r["description"],
                created_at=_ts(r["created_at"]),
                updated_at=_ts(r["updated_at"]),
            )
            for r in rows
        ]


# ---------------------------------------------------------------------------
# ProjectRepository
# ---------------------------------------------------------------------------


class ProjectRepository(Repository[Project]):
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def get(self, id: InternalId) -> Project:
        row = self._db.execute(
            "SELECT * FROM projects WHERE id = ?", (str(id.value),)
        ).fetchone()
        if row is None:
            raise EntityNotFoundError(f"Project {id} not found")
        return _row_to_project(row)

    def save(self, entity: Project) -> None:
        row = self._db.execute(
            "SELECT id FROM projects WHERE id = ?", (str(entity.id.value),)
        ).fetchone()
        if row is None:
            self._db.execute(
                """INSERT INTO projects (id, workspace_id, title, space_id, description, color, emoji,
                   is_archived, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(entity.id.value),
                    str(entity.workspace_id.value),
                    entity.title,
                    str(entity.space_id.value),
                    entity.description,
                    entity.color,
                    entity.emoji,
                    1 if entity.is_archived else 0,
                    entity.created_at.isoformat(),
                    entity.updated_at.isoformat(),
                ),
            )
        else:
            entity.updated_at = datetime.now(UTC)
            self._db.execute(
                """UPDATE projects SET title=?, description=?, color=?, emoji=?,
                   is_archived=?, updated_at=? WHERE id=?""",
                (
                    entity.title,
                    entity.description,
                    entity.color,
                    entity.emoji,
                    1 if entity.is_archived else 0,
                    entity.updated_at.isoformat(),
                    str(entity.id.value),
                ),
            )

    def delete(self, id: InternalId) -> None:
        cur = self._db.execute("DELETE FROM projects WHERE id = ?", (str(id.value),))
        if cur.rowcount == 0:
            raise EntityNotFoundError(f"Project {id} not found")

    def list_by_workspace(self, workspace_id: InternalId) -> list[Project]:
        rows = self._db.execute(
            "SELECT * FROM projects WHERE workspace_id = ? ORDER BY created_at",
            (str(workspace_id.value),),
        ).fetchall()
        return [_row_to_project(r) for r in rows]


def _row_to_project(r: sqlite3.Row) -> Project:
    return Project(
        id=_uid(r["id"]),
        workspace_id=_uid(r["workspace_id"]),
        title=r["title"],
        space_id=SpaceId(UUID(r["space_id"])),
        description=r["description"],
        color=r["color"],
        emoji=r["emoji"],
        is_archived=bool(r["is_archived"]),
        created_at=_ts(r["created_at"]),
        updated_at=_ts(r["updated_at"]),
    )


# ---------------------------------------------------------------------------
# GoalRepository
# ---------------------------------------------------------------------------


class GoalRepository(Repository[Goal]):
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def get(self, id: InternalId) -> Goal:
        row = self._db.execute(
            "SELECT * FROM goals WHERE id = ?", (str(id.value),)
        ).fetchone()
        if row is None:
            raise EntityNotFoundError(f"Goal {id} not found")
        return _row_to_goal(row)

    def save(self, entity: Goal) -> None:
        row = self._db.execute(
            "SELECT id FROM goals WHERE id = ?", (str(entity.id.value),)
        ).fetchone()
        if row is None:
            self._db.execute(
                """INSERT INTO goals (id, project_id, title, space_id, description,
                   priority, target_date, completed_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(entity.id.value),
                    str(entity.project_id.value),
                    entity.title,
                    str(entity.space_id.value),
                    entity.description,
                    entity.priority.value if entity.priority else None,
                    entity.target_date.isoformat() if entity.target_date else None,
                    entity.completed_at.isoformat() if entity.completed_at else None,
                    entity.created_at.isoformat(),
                    entity.updated_at.isoformat(),
                ),
            )
        else:
            entity.updated_at = datetime.now(UTC)
            self._db.execute(
                """UPDATE goals SET title=?, description=?, priority=?,
                   target_date=?, completed_at=?, updated_at=? WHERE id=?""",
                (
                    entity.title,
                    entity.description,
                    entity.priority.value if entity.priority else None,
                    entity.target_date.isoformat() if entity.target_date else None,
                    entity.completed_at.isoformat() if entity.completed_at else None,
                    entity.updated_at.isoformat(),
                    str(entity.id.value),
                ),
            )

    def delete(self, id: InternalId) -> None:
        cur = self._db.execute("DELETE FROM goals WHERE id = ?", (str(id.value),))
        if cur.rowcount == 0:
            raise EntityNotFoundError(f"Goal {id} not found")

    def list_by_project(self, project_id: InternalId) -> list[Goal]:
        rows = self._db.execute(
            "SELECT * FROM goals WHERE project_id = ? ORDER BY created_at",
            (str(project_id.value),),
        ).fetchall()
        return [_row_to_goal(r) for r in rows]


def _row_to_goal(r: sqlite3.Row) -> Goal:
    return Goal(
        id=_uid(r["id"]),
        project_id=_uid(r["project_id"]),
        title=r["title"],
        space_id=SpaceId(UUID(r["space_id"])),
        description=r["description"],
        priority=_to_priority(r["priority"]),
        target_date=_ts(r["target_date"]) if r["target_date"] else None,
        completed_at=_ts(r["completed_at"]) if r["completed_at"] else None,
        created_at=_ts(r["created_at"]),
        updated_at=_ts(r["updated_at"]),
    )


# ---------------------------------------------------------------------------
# MilestoneRepository
# ---------------------------------------------------------------------------


class MilestoneRepository(Repository[Milestone]):
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def get(self, id: InternalId) -> Milestone:
        row = self._db.execute(
            "SELECT * FROM milestones WHERE id = ?", (str(id.value),)
        ).fetchone()
        if row is None:
            raise EntityNotFoundError(f"Milestone {id} not found")
        return _row_to_milestone(row)

    def save(self, entity: Milestone) -> None:
        row = self._db.execute(
            "SELECT id FROM milestones WHERE id = ?", (str(entity.id.value),)
        ).fetchone()
        if row is None:
            self._db.execute(
                """INSERT INTO milestones (id, goal_id, title, space_id, target_date,
                   completed_at, "order", raw_description, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(entity.id.value),
                    str(entity.goal_id.value),
                    entity.title,
                    str(entity.space_id.value),
                    entity.target_date.isoformat() if entity.target_date else None,
                    entity.completed_at.isoformat() if entity.completed_at else None,
                    entity.order,
                    entity.raw_description,
                    entity.created_at.isoformat(),
                    entity.updated_at.isoformat(),
                ),
            )
        else:
            entity.updated_at = datetime.now(UTC)
            self._db.execute(
                """UPDATE milestones SET title=?, target_date=?, completed_at=?,
                   "order"=?, raw_description=?, updated_at=? WHERE id=?""",
                (
                    entity.title,
                    entity.target_date.isoformat() if entity.target_date else None,
                    entity.completed_at.isoformat() if entity.completed_at else None,
                    entity.order,
                    entity.raw_description,
                    entity.updated_at.isoformat(),
                    str(entity.id.value),
                ),
            )

    def delete(self, id: InternalId) -> None:
        cur = self._db.execute("DELETE FROM milestones WHERE id = ?", (str(id.value),))
        if cur.rowcount == 0:
            raise EntityNotFoundError(f"Milestone {id} not found")

    def list_by_goal(self, goal_id: InternalId) -> list[Milestone]:
        rows = self._db.execute(
            'SELECT * FROM milestones WHERE goal_id = ? ORDER BY "order"',
            (str(goal_id.value),),
        ).fetchall()
        return [_row_to_milestone(r) for r in rows]


def _row_to_milestone(r: sqlite3.Row) -> Milestone:
    return Milestone(
        id=_uid(r["id"]),
        goal_id=_uid(r["goal_id"]),
        title=r["title"],
        space_id=SpaceId(UUID(r["space_id"])),
        target_date=_ts(r["target_date"]) if r["target_date"] else None,
        completed_at=_ts(r["completed_at"]) if r["completed_at"] else None,
        order=r["order"],
        raw_description=r["raw_description"],
        created_at=_ts(r["created_at"]),
        updated_at=_ts(r["updated_at"]),
    )


# ---------------------------------------------------------------------------
# TaskRepository
# ---------------------------------------------------------------------------


class TaskRepository(Repository[Task]):
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def get(self, id: InternalId) -> Task:
        row = self._db.execute(
            "SELECT * FROM tasks WHERE id = ?", (str(id.value),)
        ).fetchone()
        if row is None:
            raise EntityNotFoundError(f"Task {id} not found")
        return _row_to_task(row)

    def save(self, entity: Task) -> None:
        row = self._db.execute(
            "SELECT id FROM tasks WHERE id = ?", (str(entity.id.value),)
        ).fetchone()
        if row is None:
            self._db.execute(
                """INSERT INTO tasks (id, title, space_id, description, priority,
                   parent_id, due_at, completed_at, tags, estimated_minutes,
                   source_ref, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(entity.id.value),
                    entity.title,
                    str(entity.space_id.value),
                    entity.description,
                    entity.priority.value if entity.priority else None,
                    str(entity.parent_id.value) if entity.parent_id else None,
                    entity.due_at.isoformat() if entity.due_at else None,
                    entity.completed_at.isoformat() if entity.completed_at else None,
                    json.dumps(entity.tags),
                    entity.estimated_minutes,
                    entity.source_ref,
                    entity.created_at.isoformat(),
                    entity.updated_at.isoformat(),
                ),
            )
        else:
            entity.updated_at = datetime.now(UTC)
            self._db.execute(
                """UPDATE tasks SET title=?, description=?, priority=?, parent_id=?,
                   due_at=?, completed_at=?, tags=?, estimated_minutes=?,
                   source_ref=?, updated_at=? WHERE id=?""",
                (
                    entity.title,
                    entity.description,
                    entity.priority.value if entity.priority else None,
                    str(entity.parent_id.value) if entity.parent_id else None,
                    entity.due_at.isoformat() if entity.due_at else None,
                    entity.completed_at.isoformat() if entity.completed_at else None,
                    json.dumps(entity.tags),
                    entity.estimated_minutes,
                    entity.source_ref,
                    entity.updated_at.isoformat(),
                    str(entity.id.value),
                ),
            )

    def delete(self, id: InternalId) -> None:
        cur = self._db.execute("DELETE FROM tasks WHERE id = ?", (str(id.value),))
        if cur.rowcount == 0:
            raise EntityNotFoundError(f"Task {id} not found")

    def list_top_level(self, space_id: SpaceId) -> list[Task]:
        rows = self._db.execute(
            "SELECT * FROM tasks WHERE space_id = ? AND parent_id IS NULL ORDER BY created_at",
            (str(space_id.value),),
        ).fetchall()
        return [_row_to_task(r) for r in rows]

    def list_by_parent(self, parent_id: InternalId) -> list[Task]:
        rows = self._db.execute(
            "SELECT * FROM tasks WHERE parent_id = ? ORDER BY created_at",
            (str(parent_id.value),),
        ).fetchall()
        return [_row_to_task(r) for r in rows]


def _row_to_task(r: sqlite3.Row) -> Task:
    return Task(
        id=_uid(r["id"]),
        title=r["title"],
        space_id=SpaceId(UUID(r["space_id"])),
        description=r["description"],
        priority=_to_priority(r["priority"]),
        parent_id=_uid(r["parent_id"]) if r["parent_id"] else None,
        due_at=_ts(r["due_at"]) if r["due_at"] else None,
        completed_at=_ts(r["completed_at"]) if r["completed_at"] else None,
        tags=json.loads(r["tags"]) if r["tags"] else [],
        estimated_minutes=r["estimated_minutes"],
        source_ref=r["source_ref"],
        created_at=_ts(r["created_at"]),
        updated_at=_ts(r["updated_at"]),
    )
