"""Additional Differ tests — uncovered branches: section moves, three-way merge/conflict."""

from __future__ import annotations

from growth.application.dtos import ProviderSnapshot
from growth.infrastructure.sync.differ import Differ


def _snap(provider: str = "todoist", **payload: object) -> ProviderSnapshot:
    return ProviderSnapshot(
        provider=provider,
        root_id=payload.pop("_root_id", None),  # type: ignore[arg-type]
        payload=payload,  # type: ignore[arg-type]
    )


class TestDifferTwoWayBranches:
    def test_section_change_detected_as_update(self) -> None:
        d = Differ()
        desired = _snap(
            project_name="P",
            sections=[{"name": "B", "id": "sec-b"}],
            items=[{"content": "Move me", "section": "B"}],
        )
        base = _snap(
            _root_id="proj-1",
            sections=[{"name": "A", "id": "sec-a"}, {"name": "B", "id": "sec-b"}],
            tasks=[{"content": "Move me", "section_id": "sec-a", "id": "t-1"}],
        )

        cs = d.diff(desired, base)
        updates = [op for op in cs.operations if op["op"] == "update_task"]
        assert len(updates) == 1
        assert updates[0]["provider_id"] == "t-1"
        assert updates[0]["section_id"] == "sec-b"

    def test_new_task_with_unknown_section_gets_null_section(self) -> None:
        d = Differ()
        desired = _snap(
            project_name="P",
            sections=[],
            items=[{"content": "New", "section": "Nowhere"}],
        )
        base = _snap(
            _root_id="proj-1",
            sections=[],
            tasks=[],
        )

        cs = d.diff(desired, base)
        create_ops = [op for op in cs.operations if op["op"] == "create_task"]
        assert len(create_ops) == 1
        assert create_ops[0]["section_id"] is None

    def test_full_create_with_unknown_section_index(self) -> None:
        d = Differ()
        desired = _snap(
            project_name="P",
            sections=[{"name": "Real"}],
            items=[{"content": "Task", "section": "Ghost"}],
        )

        cs = d.diff(desired, None)
        create_ops = [op for op in cs.operations if op["op"] == "create_task"]
        assert create_ops[0]["section_id"] == "__SECTION_-1__"

    def test_task_without_priority_or_section_no_update(self) -> None:
        d = Differ()
        desired = _snap(
            project_name="P",
            items=[{"content": "Plain"}],
        )
        base = _snap(
            _root_id="proj-1",
            tasks=[
                {"content": "Plain", "priority": 1, "section_id": "s-1", "id": "t-1"}
            ],
        )

        cs = d.diff(desired, base)
        assert all(op["op"] != "update_task" for op in cs.operations)

    def test_removed_task_without_id_not_completed(self) -> None:
        d = Differ()
        desired = _snap(project_name="P", items=[])
        base = _snap(
            _root_id="proj-1",
            tasks=[{"content": "No id task"}],
        )

        cs = d.diff(desired, base)
        assert all(op["op"] != "complete_task" for op in cs.operations)

    def test_removed_section_without_id_not_deleted(self) -> None:
        d = Differ()
        desired = _snap(project_name="P", sections=[])
        base = _snap(
            _root_id="proj-1",
            sections=[{"name": "Orphan"}],
            tasks=[],
        )

        cs = d.diff(desired, base)
        assert all(op["op"] != "delete_section" for op in cs.operations)


class TestDifferThreeWayBranches:
    def test_task_created_externally_is_merged_not_duplicated(self) -> None:
        """Task exists on remote but not in base — keep remote, no create."""
        d = Differ()
        desired = _snap(
            project_name="P",
            items=[{"content": "External task", "priority": 2}],
        )
        base = _snap(_root_id="p-1", tasks=[])
        remote = _snap(
            _root_id="p-1",
            tasks=[{"content": "External task", "priority": 2, "id": "t-ext"}],
        )

        cs = d.diff_three_way(desired, base, remote)
        create_ops = [op for op in cs.operations if op["op"] == "create_task"]
        assert len(create_ops) == 0

    def test_remote_deleted_task_is_recreated(self) -> None:
        d = Differ()
        desired = _snap(
            project_name="P",
            items=[{"content": "Bring back", "priority": 1}],
        )
        base = _snap(
            _root_id="p-1",
            tasks=[{"content": "Bring back", "priority": 1, "id": "t-1"}],
        )
        remote = _snap(_root_id="p-1", tasks=[])

        cs = d.diff_three_way(desired, base, remote)
        create_ops = [op for op in cs.operations if op["op"] == "create_task"]
        assert len(create_ops) == 1
        assert create_ops[0]["content"] == "Bring back"

    def test_both_changed_priority_is_conflict(self) -> None:
        """Local and remote both changed priority — skip (conflict)."""
        d = Differ()
        desired = _snap(
            project_name="P",
            items=[{"content": "Task A", "priority": 4}],
        )
        base = _snap(
            _root_id="p-1",
            tasks=[{"content": "Task A", "priority": 1, "id": "t-1"}],
        )
        remote = _snap(
            _root_id="p-1",
            tasks=[{"content": "Task A", "priority": 3, "id": "t-1"}],
        )

        cs = d.diff_three_way(desired, base, remote)
        updates = [op for op in cs.operations if op["op"] == "update_task"]
        assert len(updates) == 0

    def test_section_created_three_way(self) -> None:
        d = Differ()
        desired = _snap(
            project_name="P",
            sections=[{"name": "Brand New"}],
            items=[],
        )
        base = _snap(_root_id="p-1", sections=[], tasks=[])
        remote = _snap(_root_id="p-1", sections=[], tasks=[])

        cs = d.diff_three_way(desired, base, remote)
        creates = [op for op in cs.operations if op["op"] == "create_section"]
        assert len(creates) == 1
        assert creates[0]["name"] == "Brand New"

    def test_section_deleted_three_way(self) -> None:
        d = Differ()
        desired = _snap(project_name="P", sections=[], items=[])
        base = _snap(
            _root_id="p-1",
            sections=[{"name": "Old", "id": "s-old"}],
            tasks=[],
        )
        remote = _snap(
            _root_id="p-1",
            sections=[{"name": "Old", "id": "s-old"}],
            tasks=[],
        )

        cs = d.diff_three_way(desired, base, remote)
        deletes = [op for op in cs.operations if op["op"] == "delete_section"]
        assert len(deletes) == 1
        assert deletes[0]["provider_id"] == "s-old"

    def test_section_already_deleted_remotely_not_deleted_again(self) -> None:
        d = Differ()
        desired = _snap(project_name="P", sections=[], items=[])
        base = _snap(
            _root_id="p-1",
            sections=[{"name": "Old", "id": "s-old"}],
            tasks=[],
        )
        remote = _snap(_root_id="p-1", sections=[], tasks=[])

        cs = d.diff_three_way(desired, base, remote)
        assert all(op["op"] != "delete_section" for op in cs.operations)

    def test_local_change_remote_unchanged_applies_section_id(self) -> None:
        d = Differ()
        desired = _snap(
            project_name="P",
            items=[{"content": "Task A", "priority": 4}],
        )
        base = _snap(
            _root_id="p-1",
            tasks=[{"content": "Task A", "priority": 1, "id": "t-1"}],
        )
        remote = _snap(
            _root_id="p-1",
            tasks=[{"content": "Task A", "priority": 1, "id": "t-1"}],
        )

        cs = d.diff_three_way(desired, base, remote)
        updates = [op for op in cs.operations if op["op"] == "update_task"]
        assert len(updates) == 1
        assert updates[0]["provider_id"] == "t-1"
        assert updates[0]["priority"] == 4
