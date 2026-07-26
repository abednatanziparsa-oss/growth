"""Unit tests for v0.1 planning aggregates."""

from __future__ import annotations

from datetime import datetime, timezone

from growth.domain.planning import (
    Goal,
    Milestone,
    Priority,
    Project,
    Task,
    Workspace,
)
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId


class TestWorkspace:
    def test_create(self) -> None:
        now = datetime.now(timezone.utc)
        ws = Workspace(title="Personal", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now)
        assert ws.title == "Personal"
        assert ws.space_id == DEFAULT_SPACE_ID


class TestProject:
    def test_create(self) -> None:
        now = datetime.now(timezone.utc)
        ws_id = InternalId()
        p = Project(title="Exam Prep", workspace_id=ws_id, space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now)
        assert p.title == "Exam Prep"
        assert p.workspace_id == ws_id
        assert not p.is_archived


class TestGoal:
    def test_create(self) -> None:
        now = datetime.now(timezone.utc)
        p_id = InternalId()
        g = Goal(title="Math", project_id=p_id, space_id=DEFAULT_SPACE_ID, priority=Priority.HIGH, created_at=now, updated_at=now)
        assert g.title == "Math"
        assert not g.is_completed


class TestMilestone:
    def test_create(self) -> None:
        now = datetime.now(timezone.utc)
        g_id = InternalId()
        m = Milestone(title="Sets", goal_id=g_id, space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now)
        assert m.title == "Sets"
        assert not m.is_completed


class TestTask:
    def test_create(self) -> None:
        now = datetime.now(timezone.utc)
        t = Task(title="Study Chapter 1", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now)
        assert t.title == "Study Chapter 1"
        assert not t.is_completed
        assert t.is_root

    def test_complete(self) -> None:
        now = datetime.now(timezone.utc)
        t = Task(title="Done task", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now)
        t.complete(datetime.now(timezone.utc))
        assert t.is_completed
