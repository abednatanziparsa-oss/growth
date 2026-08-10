"""Unit tests for Differ — two-way snapshot diff."""

from __future__ import annotations

from growth.application.dtos import ProviderSnapshot
from growth.infrastructure.sync.differ import Differ


def _snap(provider: str = "todoist", **payload: object) -> ProviderSnapshot:
    return ProviderSnapshot(
        provider=provider,
        root_id=payload.pop("_root_id", None),  # type: ignore[arg-type]
        payload=payload,  # type: ignore[arg-type]
    )


class TestDifferEmptyBase:
    """First sync — base is None or empty."""

    def test_first_sync_with_project_name(self) -> None:
        d = Differ()
        desired = _snap(project_name="My Plan", sections=[], items=[])

        cs = d.diff(desired, None)
        assert cs.provider == "todoist"
        assert len(cs.operations) == 1
        assert cs.operations[0]["op"] == "create_project"
        assert cs.operations[0]["name"] == "My Plan"

    def test_first_sync_default_project_name(self) -> None:
        d = Differ()
        desired = _snap(sections=[], items=[])

        cs = d.diff(desired, None)
        assert cs.operations[0]["name"] == "Growth Plan"

    def test_first_sync_with_sections_and_tasks(self) -> None:
        d = Differ()
        desired = _snap(
            project_name="Plan",
            sections=[{"name": "📘 Math"}],
            items=[
                {
                    "content": "Study algebra",
                    "section": "📘 Math",
                    "priority": 3,
                    "subtasks": ["Read chapter 1"],
                }
            ],
        )

        cs = d.diff(desired, None)
        assert len(cs.operations) == 3  # project + section + task
        assert cs.operations[0]["op"] == "create_project"
        assert cs.operations[1]["op"] == "create_section"
        assert cs.operations[1]["name"] == "📘 Math"
        assert cs.operations[2]["op"] == "create_task"
        assert cs.operations[2]["content"] == "Study algebra"
        assert len(cs.operations[2]["subtasks"]) == 1

    def test_first_sync_empty_base_payload(self) -> None:
        d = Differ()
        desired = _snap(project_name="Plan")
        base = _snap()  # empty payload

        cs = d.diff(desired, base)
        assert len(cs.operations) == 1
        assert cs.operations[0]["op"] == "create_project"


class TestDifferSections:
    """Section-level diff tests."""

    def test_new_section_detected(self) -> None:
        d = Differ()
        desired = _snap(
            project_name="P",
            sections=[{"name": "A"}, {"name": "B"}],
            items=[],
        )
        base = _snap(
            root_id="proj-1",
            sections=[{"name": "A"}],
            tasks=[],
        )

        cs = d.diff(desired, base)
        create_ops = [op for op in cs.operations if op["op"] == "create_section"]
        assert len(create_ops) == 1
        assert create_ops[0]["name"] == "B"

    def test_removed_section_detected(self) -> None:
        d = Differ()
        desired = _snap(
            project_name="P",
            sections=[{"name": "A"}],
            items=[],
        )
        base = _snap(
            root_id="proj-1",
            sections=[{"name": "A", "id": "sec-a"}, {"name": "B", "id": "sec-b"}],
            tasks=[],
        )

        cs = d.diff(desired, base)
        delete_ops = [op for op in cs.operations if op["op"] == "delete_section"]
        assert len(delete_ops) == 1
        assert delete_ops[0]["provider_id"] == "sec-b"

    def test_no_section_changes(self) -> None:
        d = Differ()
        desired = _snap(
            project_name="P",
            sections=[{"name": "A"}],
            items=[],
        )
        base = _snap(
            root_id="proj-1",
            sections=[{"name": "A", "id": "sec-a"}],
            tasks=[],
        )

        cs = d.diff(desired, base)
        section_ops = [op for op in cs.operations if "section" in op["op"]]
        assert len(section_ops) == 0


class TestDifferTasks:
    """Task-level diff tests."""

    def test_new_task_detected(self) -> None:
        d = Differ()
        desired = _snap(
            project_name="P",
            sections=[],
            items=[{"content": "New Task", "priority": 2}],
        )
        base = _snap(
            root_id="proj-1",
            sections=[],
            tasks=[],
        )

        cs = d.diff(desired, base)
        create_ops = [op for op in cs.operations if op["op"] == "create_task"]
        assert len(create_ops) == 1
        assert create_ops[0]["content"] == "New Task"

    def test_unchanged_task_no_op(self) -> None:
        d = Differ()
        desired = _snap(
            project_name="P",
            items=[{"content": "Stay same", "priority": 1}],
        )
        base = _snap(
            root_id="proj-1",
            tasks=[{"content": "Stay same", "priority": 1, "id": "t-1"}],
        )

        cs = d.diff(desired, base)
        task_ops = [op for op in cs.operations if "task" in op["op"]]
        assert len(task_ops) == 0

    def test_priority_change_detected(self) -> None:
        d = Differ()
        desired = _snap(
            project_name="P",
            items=[{"content": "Urgent now", "priority": 4}],
        )
        base = _snap(
            root_id="proj-1",
            tasks=[{"content": "Urgent now", "priority": 1, "id": "t-1"}],
        )

        cs = d.diff(desired, base)
        updates = [op for op in cs.operations if op["op"] == "update_task"]
        assert len(updates) == 1
        assert updates[0]["priority"] == 4

    def test_removed_task_completed(self) -> None:
        d = Differ()
        desired = _snap(
            project_name="P",
            items=[],
        )
        base = _snap(
            root_id="proj-1",
            tasks=[{"content": "Old task", "id": "t-old"}],
        )

        cs = d.diff(desired, base)
        complete_ops = [op for op in cs.operations if op["op"] == "complete_task"]
        assert len(complete_ops) == 1
        assert complete_ops[0]["provider_id"] == "t-old"


class TestDifferNoOps:
    """Empty / no-op changesets."""

    def test_empty_base_no_ops(self) -> None:
        d = Differ()
        desired = _snap(project_name="P")
        base = _snap(root_id="proj-1", sections=[], tasks=[])

        cs = d.diff(desired, base)
        assert len(cs.operations) == 0

    def test_identical_state_no_ops(self) -> None:
        d = Differ()
        desired = _snap(
            project_name="P",
            sections=[{"name": "S1"}],
            items=[{"content": "T1", "priority": 1}],
        )
        base = _snap(
            root_id="proj-1",
            sections=[{"name": "S1", "id": "s1"}],
            tasks=[{"content": "T1", "priority": 1, "id": "t1"}],
        )

        cs = d.diff(desired, base)
        assert len(cs.operations) == 0
