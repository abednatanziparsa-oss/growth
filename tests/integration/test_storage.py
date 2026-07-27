"""Integration tests for SQLite repositories."""

from __future__ import annotations

from datetime import UTC, datetime

from growth.domain.planning import Project, Task, Workspace
from growth.domain.shared import DEFAULT_SPACE_ID
from growth.infrastructure.storage.planning_repos import (
    ProjectRepository,
    TaskRepository,
    WorkspaceRepository,
    new_in_memory_db,
)


class TestWorkspaceRepo:
    def test_save_and_retrieve(self) -> None:
        db = new_in_memory_db()
        repo = WorkspaceRepository(db)
        now = datetime.now(UTC)
        ws = Workspace(
            title="Test", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now
        )

        repo.save(ws)
        result = repo.get(ws.id)

        assert result.title == "Test"

    def test_list_all(self) -> None:
        db = new_in_memory_db()
        repo = WorkspaceRepository(db)
        now = datetime.now(UTC)

        repo.save(
            Workspace(
                title="A", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now
            )
        )
        repo.save(
            Workspace(
                title="B", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now
            )
        )

        assert len(repo.list_all()) == 2


class TestProjectRepo:
    def test_list_by_workspace(self) -> None:
        db = new_in_memory_db()
        ws_repo = WorkspaceRepository(db)
        p_repo = ProjectRepository(db)
        now = datetime.now(UTC)

        ws = Workspace(
            title="WS", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now
        )
        ws_repo.save(ws)

        p = Project(
            title="P",
            workspace_id=ws.id,
            space_id=DEFAULT_SPACE_ID,
            created_at=now,
            updated_at=now,
        )
        p_repo.save(p)

        projects = p_repo.list_by_workspace(ws.id)
        assert len(projects) == 1
        assert projects[0].title == "P"


class TestTaskRepo:
    def test_list_top_level(self) -> None:
        db = new_in_memory_db()
        repo = TaskRepository(db)
        now = datetime.now(UTC)

        repo.save(
            Task(title="T1", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now)
        )
        repo.save(
            Task(title="T2", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now)
        )

        tasks = repo.list_top_level(DEFAULT_SPACE_ID)
        assert len(tasks) == 2

    def test_parent_child(self) -> None:
        db = new_in_memory_db()
        repo = TaskRepository(db)
        now = datetime.now(UTC)

        parent = Task(
            title="Parent", space_id=DEFAULT_SPACE_ID, created_at=now, updated_at=now
        )
        repo.save(parent)

        child = Task(
            title="Child",
            space_id=DEFAULT_SPACE_ID,
            parent_id=parent.id,
            created_at=now,
            updated_at=now,
        )
        repo.save(child)

        children = repo.list_by_parent(parent.id)
        assert len(children) == 1
        assert children[0].title == "Child"
