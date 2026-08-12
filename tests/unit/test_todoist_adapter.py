"""Unit tests for TodoistAdapter — mocked API, no network."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from growth.application.dtos import ChangeSet
from growth.application.errors import ProviderUnavailableError
from growth.infrastructure.adapters.todoist import TodoistAdapter


def _fake_project(**kw: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "id": "proj-1",
        "name": "Growth",
        "is_archived": False,
        "color": "red",
        "is_favorite": False,
    }
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _fake_section(**kw: object) -> SimpleNamespace:
    defaults: dict[str, object] = {"id": "sec-1", "name": "Math", "order": 1}
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _fake_task(**kw: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "id": "t-1",
        "content": "Study",
        "section_id": "sec-1",
        "parent_id": None,
        "priority": 3,
        "completed_at": None,
        "order": 1,
        "description": "",
        "labels": [],
    }
    defaults.update(kw)
    return SimpleNamespace(**defaults)


class _FakeTodoistAPI:
    """Records calls; returns predictable fake resources."""

    def __init__(self, token: str) -> None:
        self.token = token
        self.calls: list[tuple[str, dict[str, object]]] = []

    # --- creates ---------------------------------------------------------

    def add_project(self, **kw: object) -> SimpleNamespace:
        self.calls.append(("add_project", kw))
        return _fake_project(id="new-proj", name=str(kw.get("name", "")))

    def add_section(self, **kw: object) -> SimpleNamespace:
        self.calls.append(("add_section", kw))
        return _fake_section(id="new-sec", name=str(kw.get("name", "")))

    def add_task(self, **kw: object) -> SimpleNamespace:
        self.calls.append(("add_task", kw))
        return _fake_task(
            id=f"new-task-{len(self.calls)}",
            content=str(kw.get("content", "")),
        )

    # --- mutations -------------------------------------------------------

    def complete_task(self, **kw: object) -> None:
        self.calls.append(("complete_task", kw))

    def update_task(self, **kw: object) -> None:
        self.calls.append(("update_task", kw))

    def delete_project(self, **kw: object) -> None:
        self.calls.append(("delete_project", kw))

    def delete_section(self, **kw: object) -> None:
        self.calls.append(("delete_section", kw))

    # --- reads -----------------------------------------------------------

    def get_project(self, project_id: str) -> SimpleNamespace:
        self.calls.append(("get_project", {"project_id": project_id}))
        return _fake_project(id=project_id, name="Growth")

    def get_sections(self, **kw: object) -> list[list[SimpleNamespace]]:
        self.calls.append(("get_sections", kw))
        return [[_fake_section(id="sec-a"), _fake_section(id="sec-b", name="Physics")]]

    def get_tasks(self, **kw: object) -> list[list[SimpleNamespace]]:
        self.calls.append(("get_tasks", kw))
        return [
            [
                _fake_task(id="t-a", content="Study algebra"),
                _fake_task(id="t-b", content="Study geometry", parent_id="t-a"),
            ]
        ]


def _adapter(fake: _FakeTodoistAPI) -> TodoistAdapter:
    with patch("growth.infrastructure.adapters.todoist.TodoistAPI", return_value=fake):
        return TodoistAdapter("fake-token")


def _changeset(*ops: dict[str, object]) -> ChangeSet:
    return ChangeSet(provider="todoist", operations=list(ops))


class TestTodoistAdapterFetch:
    def test_fetch_current_none_root_returns_empty(self) -> None:
        fake = _FakeTodoistAPI("t")
        adapter = _adapter(fake)

        snap = adapter.fetch_current(None)

        assert snap.provider == "todoist"
        assert snap.root_id is None
        assert snap.payload == {}
        assert fake.calls == []

    def test_fetch_current_populates_snapshot(self) -> None:
        fake = _FakeTodoistAPI("t")
        adapter = _adapter(fake)

        snap = adapter.fetch_current("proj-9")

        assert snap.root_id == "proj-9"
        assert snap.payload["project"]["name"] == "Growth"
        assert [s["name"] for s in snap.payload["sections"]] == ["Math", "Physics"]
        tasks = snap.payload["tasks"]
        assert [t["content"] for t in tasks] == ["Study algebra", "Study geometry"]
        assert tasks[1]["parent_id"] == "t-a"
        assert tasks[0]["is_completed"] is False

    def test_fetch_current_maps_completed_at_to_is_completed(self) -> None:
        fake = _FakeTodoistAPI("t")
        adapter = _adapter(fake)
        fake.get_tasks = lambda **_: [  # type: ignore[method-assign]
            [
                _fake_task(id="t-done", completed_at="2026-08-10T09:00:00Z"),
                _fake_task(id="t-open"),
            ]
        ]

        snap = adapter.fetch_current("proj-9")

        by_id = {t["id"]: t["is_completed"] for t in snap.payload["tasks"]}
        assert by_id == {"t-done": True, "t-open": False}

    def test_fetch_current_wraps_api_errors(self) -> None:
        class _BoomAPI(_FakeTodoistAPI):
            def get_project(self, project_id: str) -> SimpleNamespace:  # type: ignore[override]
                raise RuntimeError("network down")

        adapter = _adapter(_BoomAPI("t"))

        with pytest.raises(ProviderUnavailableError, match="proj-9"):
            adapter.fetch_current("proj-9")


class TestTodoistAdapterApply:
    def test_apply_create_ops_tracks_provider_ids(self) -> None:
        fake = _FakeTodoistAPI("t")
        adapter = _adapter(fake)

        cs = _changeset(
            {"op": "create_project", "name": "Plan", "internal_id": "id-proj"},
            {
                "op": "create_section",
                "name": "Math",
                "project_id": "new-proj",
                "internal_id": "id-sec",
            },
            {"op": "create_task", "content": "Study", "internal_id": "id-task"},
        )
        result = adapter.apply(cs)

        assert result.applied == 3
        assert result.failed == 0
        assert result.errors == []
        assert result.provider_ids == {
            "id-proj": "new-proj",
            "id-sec": "new-sec",
            "id-task": "new-task-3",
        }

    def test_apply_create_task_with_subtask_recursion(self) -> None:
        fake = _FakeTodoistAPI("t")
        adapter = _adapter(fake)

        cs = _changeset(
            {
                "op": "create_task",
                "content": "Parent",
                "subtasks": [{"op": "create_task", "content": "Child", "subtasks": []}],
            }
        )
        result = adapter.apply(cs)

        assert result.applied == 1
        task_calls = [c for c in fake.calls if c[0] == "add_task"]
        assert len(task_calls) == 2
        parent_kw = task_calls[0][1]
        child_kw = task_calls[1][1]
        assert parent_kw["content"] == "Parent"
        assert child_kw["content"] == "Child"
        # child was created with parent_id = parent's returned task id
        assert child_kw["parent_id"] == "new-task-1"

    def test_apply_mutation_ops(self) -> None:
        fake = _FakeTodoistAPI("t")
        adapter = _adapter(fake)

        cs = _changeset(
            {"op": "complete_task", "provider_id": "t-1"},
            {"op": "update_task", "provider_id": "t-2", "content": "Renamed"},
            {"op": "delete_project", "provider_id": "p-1"},
            {"op": "delete_section", "provider_id": "s-1"},
        )
        result = adapter.apply(cs)

        assert result.applied == 4
        assert result.failed == 0
        assert result.provider_ids == {}
        assert {c[0] for c in fake.calls} == {
            "complete_task",
            "update_task",
            "delete_project",
            "delete_section",
        }

    def test_apply_records_per_op_failures(self) -> None:
        class _FlakyAPI(_FakeTodoistAPI):
            def add_project(self, **kw: object) -> SimpleNamespace:
                raise RuntimeError("boom")

        fake = _FlakyAPI("t")
        adapter = _adapter(fake)

        cs = _changeset(
            {"op": "create_project", "name": "P", "internal_id": "id-p"},
            {"op": "complete_task", "provider_id": "t-1"},
        )
        result = adapter.apply(cs)

        assert result.applied == 1
        assert result.failed == 1
        assert len(result.errors) == 1
        assert "boom" in result.errors[0]
        assert result.provider_ids == {}

    def test_apply_unknown_op_fails_that_op(self) -> None:
        fake = _FakeTodoistAPI("t")
        adapter = _adapter(fake)

        cs = _changeset({"op": "teleport", "internal_id": "x"})
        result = adapter.apply(cs)

        assert result.applied == 0
        assert result.failed == 1
        assert "Unknown operation: teleport" in result.errors[0]

    def test_apply_op_missing_internal_id_not_tracked(self) -> None:
        fake = _FakeTodoistAPI("t")
        adapter = _adapter(fake)

        cs = _changeset({"op": "create_project", "name": "P"})
        result = adapter.apply(cs)

        assert result.applied == 1
        assert result.provider_ids == {}


class TestTodoistAdapterOps:
    def test_provider_property(self) -> None:
        assert _adapter(_FakeTodoistAPI("t")).provider == "todoist"

    def test_apply_op_unknown_raises(self) -> None:
        adapter = _adapter(_FakeTodoistAPI("t"))
        with pytest.raises(ValueError, match="Unknown operation"):
            adapter._apply_op({"op": "nope"})

    def test_apply_op_returns_id_for_creates_none_for_mutations(self) -> None:
        adapter = _adapter(_FakeTodoistAPI("t"))
        assert adapter._apply_op({"op": "create_project", "name": "P"}) == "new-proj"
        assert adapter._apply_op({"op": "complete_task", "provider_id": "t"}) is None
