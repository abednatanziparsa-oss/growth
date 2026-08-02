"""Integration tests for SQLite repositories — edge cases and update paths.

Extends the existing test_storage.py with delete-on-missing,
update-on-existing, optional-field roundtrips, and Goal/Milestone repos.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from growth.application.ports.repository import EntityNotFoundError
from growth.domain.planning import (
    Goal,
    Milestone,
    Priority,
    Project,
    Task,
    Workspace,
)
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId
from growth.infrastructure.storage.planning_repos import (
    GoalRepository,
    MilestoneRepository,
    ProjectRepository,
    TaskRepository,
    WorkspaceRepository,
    new_in_memory_db,
)

# ---------------------------------------------------------------------------
# Fixtures shared across classes
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


# ============================================================================
# WorkspaceRepository — edge cases
# ============================================================================


class TestWorkspaceRepoEdgeCases:
    def test_get_nonexistent_raises(self) -> None:
        db = new_in_memory_db()
        repo = WorkspaceRepository(db)
        with pytest.raises(EntityNotFoundError, match="Workspace"):
            repo.get(InternalId())

    def test_delete_nonexistent_raises(self) -> None:
        db = new_in_memory_db()
        repo = WorkspaceRepository(db)
        with pytest.raises(EntityNotFoundError, match="Workspace"):
            repo.delete(InternalId())

    def test_delete_existing(self) -> None:
        db = new_in_memory_db()
        repo = WorkspaceRepository(db)
        now = _now()
        ws = Workspace(
            title="Del", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now
        )
        repo.save(ws)
        repo.delete(ws.id)
        with pytest.raises(EntityNotFoundError):
            repo.get(ws.id)

    def test_save_update_existing(self) -> None:
        db = new_in_memory_db()
        repo = WorkspaceRepository(db)
        now = _now()
        ws = Workspace(
            title="Original",
            description="old",
            space_id=DEFAULT_SPACE_ID,
            created_at=now,
            updated_at=now,
        )
        repo.save(ws)

        ws.title = "Updated"
        ws.description = "new"
        repo.save(ws)

        result = repo.get(ws.id)
        assert result.title == "Updated"
        assert result.description == "new"


# ============================================================================
# ProjectRepository — edge cases
# ============================================================================


class TestProjectRepoEdgeCases:
    def test_get_nonexistent_raises(self) -> None:
        db = new_in_memory_db()
        repo = ProjectRepository(db)
        with pytest.raises(EntityNotFoundError, match="Project"):
            repo.get(InternalId())

    def test_delete_nonexistent_raises(self) -> None:
        db = new_in_memory_db()
        repo = ProjectRepository(db)
        with pytest.raises(EntityNotFoundError, match="Project"):
            repo.delete(InternalId())

    def test_save_update_existing_project(self) -> None:
        db = new_in_memory_db()
        now = _now()
        ws = Workspace(
            title="W", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now
        )
        WorkspaceRepository(db).save(ws)

        repo = ProjectRepository(db)
        p = Project(
            title="Orig",
            workspace_id=ws.id,
            space_id=DEFAULT_SPACE_ID,
            created_at=now,
            updated_at=now,
        )
        repo.save(p)

        p.title = "Changed"
        p.color = "#ff0000"
        p.is_archived = True
        repo.save(p)

        result = repo.get(p.id)
        assert result.title == "Changed"
        assert result.color == "#ff0000"
        assert result.is_archived is True

    def test_list_by_workspace_empty(self) -> None:
        db = new_in_memory_db()
        repo = ProjectRepository(db)
        assert repo.list_by_workspace(InternalId()) == []


# ============================================================================
# GoalRepository — happy path + edges
# ============================================================================


class TestGoalRepo:
    def test_save_and_retrieve_with_priority(self) -> None:
        db = new_in_memory_db()
        now = _now()
        ws = Workspace(
            title="W", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now
        )
        WorkspaceRepository(db).save(ws)
        p = Project(
            title="P",
            workspace_id=ws.id,
            space_id=DEFAULT_SPACE_ID,
            created_at=now,
            updated_at=now,
        )
        ProjectRepository(db).save(p)

        repo = GoalRepository(db)
        g = Goal(
            title="Goal A",
            project_id=p.id,
            space_id=DEFAULT_SPACE_ID,
            priority=Priority.HIGH,
            created_at=now,
            updated_at=now,
        )
        repo.save(g)
        result = repo.get(g.id)
        assert result.title == "Goal A"
        assert result.priority == Priority.HIGH

    def test_list_by_project(self) -> None:
        db = new_in_memory_db()
        now = _now()
        ws = Workspace(
            title="W", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now
        )
        WorkspaceRepository(db).save(ws)
        p = Project(
            title="P",
            workspace_id=ws.id,
            space_id=DEFAULT_SPACE_ID,
            created_at=now,
            updated_at=now,
        )
        ProjectRepository(db).save(p)

        repo = GoalRepository(db)
        repo.save(
            Goal(
                title="G1",
                project_id=p.id,
                space_id=DEFAULT_SPACE_ID,
                created_at=now,
                updated_at=now,
            )
        )
        repo.save(
            Goal(
                title="G2",
                project_id=p.id,
                space_id=DEFAULT_SPACE_ID,
                created_at=now,
                updated_at=now,
            )
        )

        goals = repo.list_by_project(p.id)
        assert len(goals) == 2
        assert {g.title for g in goals} == {"G1", "G2"}

    def test_save_update_existing_goal(self) -> None:
        db = new_in_memory_db()
        now = _now()
        ws = Workspace(
            title="W", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now
        )
        WorkspaceRepository(db).save(ws)
        p = Project(
            title="P",
            workspace_id=ws.id,
            space_id=DEFAULT_SPACE_ID,
            created_at=now,
            updated_at=now,
        )
        ProjectRepository(db).save(p)

        repo = GoalRepository(db)
        g = Goal(
            title="G",
            project_id=p.id,
            space_id=DEFAULT_SPACE_ID,
            created_at=now,
            updated_at=now,
        )
        repo.save(g)

        g.title = "G Updated"
        g.description = "desc"
        g.priority = Priority.LOW
        g.completed_at = _now()
        repo.save(g)

        result = repo.get(g.id)
        assert result.title == "G Updated"
        assert result.description == "desc"
        assert result.priority == Priority.LOW
        assert result.completed_at is not None

    def test_get_nonexistent_raises(self) -> None:
        db = new_in_memory_db()
        repo = GoalRepository(db)
        with pytest.raises(EntityNotFoundError, match="Goal"):
            repo.get(InternalId())

    def test_delete_nonexistent_raises(self) -> None:
        db = new_in_memory_db()
        repo = GoalRepository(db)
        with pytest.raises(EntityNotFoundError, match="Goal"):
            repo.delete(InternalId())


# ============================================================================
# MilestoneRepository — happy path + edges
# ============================================================================


class TestMilestoneRepo:
    def test_save_and_retrieve(self) -> None:
        db = new_in_memory_db()
        now = _now()
        ws = Workspace(
            title="W", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now
        )
        WorkspaceRepository(db).save(ws)
        p = Project(
            title="P",
            workspace_id=ws.id,
            space_id=DEFAULT_SPACE_ID,
            created_at=now,
            updated_at=now,
        )
        ProjectRepository(db).save(p)
        g = Goal(
            title="G",
            project_id=p.id,
            space_id=DEFAULT_SPACE_ID,
            created_at=now,
            updated_at=now,
        )
        GoalRepository(db).save(g)

        repo = MilestoneRepository(db)
        m = Milestone(
            title="Milestone 1",
            goal_id=g.id,
            space_id=DEFAULT_SPACE_ID,
            order=0,
            created_at=now,
            updated_at=now,
        )
        repo.save(m)
        result = repo.get(m.id)
        assert result.title == "Milestone 1"
        assert result.order == 0

    def test_list_by_goal(self) -> None:
        db = new_in_memory_db()
        now = _now()
        ws = Workspace(
            title="W", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now
        )
        WorkspaceRepository(db).save(ws)
        p = Project(
            title="P",
            workspace_id=ws.id,
            space_id=DEFAULT_SPACE_ID,
            created_at=now,
            updated_at=now,
        )
        ProjectRepository(db).save(p)
        g = Goal(
            title="G",
            project_id=p.id,
            space_id=DEFAULT_SPACE_ID,
            created_at=now,
            updated_at=now,
        )
        GoalRepository(db).save(g)

        repo = MilestoneRepository(db)
        repo.save(
            Milestone(
                title="M1",
                goal_id=g.id,
                space_id=DEFAULT_SPACE_ID,
                order=0,
                created_at=now,
                updated_at=now,
            )
        )
        repo.save(
            Milestone(
                title="M2",
                goal_id=g.id,
                space_id=DEFAULT_SPACE_ID,
                order=1,
                created_at=now,
                updated_at=now,
            )
        )

        milestones = repo.list_by_goal(g.id)
        assert len(milestones) == 2
        assert milestones[0].title == "M1"  # ordered by "order"
        assert milestones[1].title == "M2"

    def test_save_update_existing_milestone(self) -> None:
        db = new_in_memory_db()
        now = _now()
        ws = Workspace(
            title="W", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now
        )
        WorkspaceRepository(db).save(ws)
        p = Project(
            title="P",
            workspace_id=ws.id,
            space_id=DEFAULT_SPACE_ID,
            created_at=now,
            updated_at=now,
        )
        ProjectRepository(db).save(p)
        g = Goal(
            title="G",
            project_id=p.id,
            space_id=DEFAULT_SPACE_ID,
            created_at=now,
            updated_at=now,
        )
        GoalRepository(db).save(g)

        repo = MilestoneRepository(db)
        m = Milestone(
            title="M",
            goal_id=g.id,
            space_id=DEFAULT_SPACE_ID,
            order=0,
            created_at=now,
            updated_at=now,
        )
        repo.save(m)

        m.title = "M Updated"
        m.completed_at = _now()
        m.order = 5
        repo.save(m)

        result = repo.get(m.id)
        assert result.title == "M Updated"
        assert result.completed_at is not None
        assert result.order == 5

    def test_get_nonexistent_raises(self) -> None:
        db = new_in_memory_db()
        repo = MilestoneRepository(db)
        with pytest.raises(EntityNotFoundError, match="Milestone"):
            repo.get(InternalId())

    def test_delete_nonexistent_raises(self) -> None:
        db = new_in_memory_db()
        repo = MilestoneRepository(db)
        with pytest.raises(EntityNotFoundError, match="Milestone"):
            repo.delete(InternalId())


# ============================================================================
# TaskRepository — edge cases
# ============================================================================


class TestTaskRepoEdgeCases:
    def test_get_nonexistent_raises(self) -> None:
        db = new_in_memory_db()
        repo = TaskRepository(db)
        with pytest.raises(EntityNotFoundError, match="Task"):
            repo.get(InternalId())

    def test_delete_nonexistent_raises(self) -> None:
        db = new_in_memory_db()
        repo = TaskRepository(db)
        with pytest.raises(EntityNotFoundError, match="Task"):
            repo.delete(InternalId())

    def test_save_update_existing_task(self) -> None:
        db = new_in_memory_db()
        now = _now()
        repo = TaskRepository(db)
        t = Task(
            title="Original",
            space_id=DEFAULT_SPACE_ID,
            created_at=now,
            updated_at=now,
        )
        repo.save(t)

        t.title = "Updated"
        t.description = "new desc"
        t.priority = Priority.URGENT
        t.tags = ["urgent", "review"]
        t.estimated_minutes = 45
        repo.save(t)

        result = repo.get(t.id)
        assert result.title == "Updated"
        assert result.description == "new desc"
        assert result.priority == Priority.URGENT
        assert result.tags == ["urgent", "review"]
        assert result.estimated_minutes == 45

    def test_save_with_all_optionals_as_none(self) -> None:
        db = new_in_memory_db()
        now = _now()
        repo = TaskRepository(db)
        t = Task(
            title="Minimal",
            space_id=DEFAULT_SPACE_ID,
            created_at=now,
            updated_at=now,
        )
        # All optionals at default (None, empty list)
        repo.save(t)
        result = repo.get(t.id)
        assert result.description is None
        assert result.priority is None
        assert result.parent_id is None
        assert result.due_at is None
        assert result.completed_at is None
        assert result.tags == []
        assert result.estimated_minutes is None

    def test_list_by_parent_empty(self) -> None:
        db = new_in_memory_db()
        repo = TaskRepository(db)
        assert repo.list_by_parent(InternalId()) == []

    def test_list_top_level_empty(self) -> None:
        db = new_in_memory_db()
        repo = TaskRepository(db)
        assert repo.list_top_level(DEFAULT_SPACE_ID) == []
