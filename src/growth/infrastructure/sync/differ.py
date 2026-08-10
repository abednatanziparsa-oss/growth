"""Two-way differ — compare desired vs base ProviderSnapshot to produce a ChangeSet.

The Differ is the diff step of the three-way sync:
  1. Project the CanonicalPlan → desired ProviderSnapshot
  2. Diff desired vs last-synced (base) → ChangeSet
  3. Fetch remote state, detect conflicts (v0.2.1), apply ChangeSet

For v0.2 the differ handles two-way (desired vs base). Three-way conflict
detection is a v0.2.1 follow-up.
"""

from __future__ import annotations

from typing import Any

from growth.application.dtos import ChangeSet, ProviderSnapshot

__all__ = ["Differ"]


class Differ:
    """Compare two ProviderSnapshots and compute a ChangeSet.

    Stable identity for tasks/sections without provider ids uses
    content-based matching: tasks are matched on ``content``,
    sections on ``name``.
    """

    def diff(
        self, desired: ProviderSnapshot, base: ProviderSnapshot | None
    ) -> ChangeSet:
        """Compute operations to move from ``base`` to ``desired``.

        Args:
            desired: The projected snapshot (what we want).
            base: The last-synced snapshot, or ``None`` for first sync.

        Returns:
            A ``ChangeSet`` whose operations transition base → desired.
        """
        operations: list[dict[str, Any]] = []

        if base is None or not base.payload:
            # First sync — create everything from scratch.
            return self._full_create(desired)

        # Compute section diffs
        operations.extend(self._diff_sections(desired, base))

        # Compute task diffs
        operations.extend(self._diff_tasks(desired, base))

        return ChangeSet(
            provider=desired.provider,
            operations=operations,
        )

    # ------------------------------------------------------------------
    # Full create (first sync)
    # ------------------------------------------------------------------

    def _full_create(self, desired: ProviderSnapshot) -> ChangeSet:
        """Generate a ChangeSet that creates the entire project from scratch."""
        ops: list[dict[str, Any]] = []
        payload = desired.payload

        project_name = payload.get("project_name", "Growth Plan")
        ops.append({"op": "create_project", "name": project_name})

        sections = payload.get("sections", [])
        for idx, section in enumerate(sections):
            ops.append(
                {
                    "op": "create_section",
                    "name": section["name"],
                    "project_id": "__PROJECT__",  # placeholder, resolved at apply time
                    "_index": idx,
                }
            )

        items = payload.get("items", [])
        for item in items:
            section_name = item.get("section", "")
            ops.append(
                {
                    "op": "create_task",
                    "content": item["content"],
                    "section_id": f"__SECTION_{self._section_index(sections, section_name)}__" if section_name else None,
                    "priority": item.get("priority", 1),
                    "subtasks": [
                        {"op": "create_task", "content": st, "priority": item.get("priority", 1)}
                        for st in item.get("subtasks", [])
                    ],
                }
            )

        return ChangeSet(provider=desired.provider, operations=ops)

    # ------------------------------------------------------------------
    # Section diffs
    # ------------------------------------------------------------------

    def _diff_sections(
        self, desired: ProviderSnapshot, base: ProviderSnapshot
    ) -> list[dict[str, Any]]:
        """Compute section-level operations."""
        ops: list[dict[str, Any]] = []

        desired_sections = desired.payload.get("sections", [])
        base_sections = base.payload.get("sections", [])

        desired_names = {s["name"] for s in desired_sections}
        base_names = {s["name"] for s in base_sections}
        base_by_name = {s["name"]: s for s in base_sections}

        # New sections
        for s in desired_sections:
            if s["name"] not in base_names:
                ops.append(
                    {
                        "op": "create_section",
                        "name": s["name"],
                        "project_id": base.root_id or "",
                    }
                )

        # Removed sections
        for name in base_names - desired_names:
            bs = base_by_name[name]
            pid = bs.get("id")
            if pid:
                ops.append(
                    {
                        "op": "delete_section",
                        "provider_id": pid,
                    }
                )

        return ops

    # ------------------------------------------------------------------
    # Task diffs
    # ------------------------------------------------------------------

    def _diff_tasks(
        self, desired: ProviderSnapshot, base: ProviderSnapshot
    ) -> list[dict[str, Any]]:
        """Compute task-level operations."""
        ops: list[dict[str, Any]] = []

        desired_items = desired.payload.get("items", [])
        base_items = base.payload.get("tasks", [])

        # Index base tasks by content for stable matching
        base_by_content: dict[str, dict[str, Any]] = {}
        for t in base_items:
            key = self._task_key(t)
            base_by_content[key] = t

        desired_keys: set[str] = set()

        # New or changed tasks
        for item in desired_items:
            key = item["content"]
            desired_keys.add(key)

            if key not in base_by_content:
                # New task
                ops.append(
                    {
                        "op": "create_task",
                        "content": item["content"],
                        "section_id": self._resolve_section_id(
                            item.get("section", ""), desired, base
                        ),
                        "project_id": base.root_id or "",
                        "priority": item.get("priority", 1),
                        "subtasks": [
                            {
                                "op": "create_task",
                                "content": st,
                                "priority": item.get("priority", 1),
                            }
                            for st in item.get("subtasks", [])
                        ],
                    }
                )
            else:
                # Existing task — check for changes
                bt = base_by_content[key]
                changes: dict[str, Any] = {}

                if item.get("priority") and item["priority"] != bt.get("priority"):
                    changes["priority"] = item["priority"]

                new_section = self._resolve_section_id(
                    item.get("section", ""), desired, base
                )
                if new_section and new_section != bt.get("section_id"):
                    changes["section_id"] = new_section

                if changes and bt.get("id"):
                    ops.append(
                        {
                            "op": "update_task",
                            "provider_id": bt["id"],
                            **changes,
                        }
                    )

        # Removed tasks (complete them)
        for key, bt in base_by_content.items():
            if key not in desired_keys and bt.get("id"):
                ops.append(
                    {
                        "op": "complete_task",
                        "provider_id": bt["id"],
                    }
                )

        return ops

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _task_key(task: dict[str, Any]) -> str:
        """Stable identity key for a task: its content string."""
        return str(task.get("content", ""))

    @staticmethod
    def _section_index(sections: list[dict[str, Any]], name: str) -> int:
        """Find the index of a section by name."""
        for i, s in enumerate(sections):
            if s["name"] == name:
                return i
        return -1

    def _resolve_section_id(
        self,
        section_name: str,
        _desired: ProviderSnapshot,
        base: ProviderSnapshot,
    ) -> str | None:
        """Resolve a section name to a provider id using base snapshot data.

        For sections that already exist in base, return their id.
        For new sections, the caller will handle id assignment post-creation.
        """
        if not section_name:
            return None

        # Try base sections
        for s in base.payload.get("sections", []):
            if s.get("name") == section_name and s.get("id"):
                return str(s["id"])

        return None
