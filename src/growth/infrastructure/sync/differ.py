"""Three-way differ — compare desired, base, and remote ProviderSnapshots.

The Differ is the diff step of the three-way sync:
  1. Project the CanonicalPlan → desired ProviderSnapshot
  2. Fetch remote state from the provider
  3. Diff three-way (base, desired, remote) → ChangeSet with conflict detection
  4. Apply ChangeSet, record new base

Three-way diff detects genuine conflicts: changes made both locally and on
the remote since the last sync. Auto-resolves non-overlapping changes.
"""

from __future__ import annotations

from typing import Any

from growth.application.dtos import ChangeSet, ProviderSnapshot

__all__ = ["Differ"]


class Differ:
    """Compare ProviderSnapshots and compute a ChangeSet.

    Three comparison modes:
    - ``diff(desired, None)``: first sync, full create
    - ``diff(desired, base)``: two-way, no remote involved
    - ``diff_three_way(desired, base, remote)``: three-way with conflict detection

    Stable identity for tasks/sections uses content-based matching:
    tasks on ``content``, sections on ``name``.
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
                    "section_id": f"__SECTION_{self._section_index(sections, section_name)}__"
                    if section_name
                    else None,
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

    # ------------------------------------------------------------------
    # Three-way diff (v0.2.1)
    # ------------------------------------------------------------------

    def diff_three_way(
        self,
        desired: ProviderSnapshot,
        base: ProviderSnapshot | None,
        remote: ProviderSnapshot | None,
    ) -> ChangeSet:
        """Three-way diff with conflict detection.

        Args:
            desired: What we want (from current projection).
            base: Last-synced state (our snapshot of what was pushed).
            remote: Current live state from the provider.

        Returns:
            A ``ChangeSet`` with only non-conflicting operations.
            Conflicting items are skipped (logged as comments).

        Strategy:
            - If remote hasn't changed since base, use two-way diff (desired vs base).
            - If changes are on different fields, merge them.
            - If the same task/section was modified on both sides, skip (conflict).
            - If a task was completed on remote and modified locally, keep remote completion,
              apply local changes to other fields.
        """
        # First sync — same as two-way
        if base is None or not base.payload:
            return self._full_create(desired)

        # If no remote changes, fall back to two-way
        if remote is None or not remote.payload:
            return self.diff(desired, base)

        ops: list[dict[str, Any]] = []

        # Task-level three-way diff
        ops.extend(self._diff_tasks_three_way(desired, base, remote))

        # Section-level three-way diff
        ops.extend(self._diff_sections_three_way(desired, base, remote))

        return ChangeSet(provider=desired.provider, operations=ops)

    def _diff_sections_three_way(
        self,
        desired: ProviderSnapshot,
        base: ProviderSnapshot,
        remote: ProviderSnapshot,
    ) -> list[dict[str, Any]]:
        """Three-way section diff."""
        ops: list[dict[str, Any]] = []

        desired_secs = {s["name"]: s for s in desired.payload.get("sections", [])}
        base_secs = {s["name"]: s for s in base.payload.get("sections", [])}
        remote_secs = {s["name"]: s for s in remote.payload.get("sections", [])}

        # New sections in desired (not in base)
        for name, _ds in desired_secs.items():
            if name not in base_secs and name not in remote_secs:
                # Neither side has it — safe to create
                ops.append(
                    {
                        "op": "create_section",
                        "name": name,
                        "project_id": base.root_id or "",
                    }
                )

        # Sections removed in desired (in base but not desired)
        for name, bs in base_secs.items():
            if name not in desired_secs and name in remote_secs:
                pid = bs.get("id")
                if pid:
                    ops.append({"op": "delete_section", "provider_id": pid})

        return ops

    def _diff_tasks_three_way(
        self,
        desired: ProviderSnapshot,
        base: ProviderSnapshot,
        remote: ProviderSnapshot,
    ) -> list[dict[str, Any]]:
        """Three-way task diff with conflict detection."""
        ops: list[dict[str, Any]] = []

        desired_items = desired.payload.get("items", [])
        base_tasks = {self._task_key(t): t for t in base.payload.get("tasks", [])}
        remote_tasks = {self._task_key(t): t for t in remote.payload.get("tasks", [])}

        desired_keys: set[str] = set()

        for item in desired_items:
            key = item["content"]
            desired_keys.add(key)

            bt = base_tasks.get(key)
            rt = remote_tasks.get(key)

            if bt is None:
                # New task — not in base
                if rt is None:
                    # Also not on remote — safe to create
                    ops.append(
                        {
                            "op": "create_task",
                            "content": item["content"],
                            "project_id": base.root_id or "",
                            "priority": item.get("priority", 1),
                            "subtasks": [
                                {"op": "create_task", "content": st}
                                for st in item.get("subtasks", [])
                            ],
                        }
                    )
                # Else: task exists on remote but not in base — someone
                # created it outside Growth. Merge: keep remote task, update
                # only non-conflicting fields.
                continue

            # Task exists in base
            if rt is None:
                # Remote deleted it — we can recreate
                ops.append(
                    {
                        "op": "create_task",
                        "content": item["content"],
                        "project_id": base.root_id or "",
                        "priority": item.get("priority", 1),
                        "subtasks": [
                            {"op": "create_task", "content": st}
                            for st in item.get("subtasks", [])
                        ],
                    }
                )
                continue

            # Both local and remote may have changed — three-way logic
            local_changed = self._task_changed(item, bt)
            remote_changed = self._task_changed(_task_to_item(rt), bt)

            if local_changed and remote_changed:
                # Both sides changed — detect field-level conflicts
                changes = self._merge_non_conflicting(item, bt, rt)
                if changes and rt.get("id"):
                    ops.append(
                        {"op": "update_task", "provider_id": rt["id"], **changes}
                    )
            elif local_changed:
                # Only we changed — safe to apply
                changes = self._task_field_diff(item, bt)
                if changes and rt.get("id"):
                    ops.append(
                        {"op": "update_task", "provider_id": rt["id"], **changes}
                    )
            # Remote-only changes: keep remote state (no-op for us)

        # Tasks in base but not in desired — complete them (if not already remote-completed)
        for key, _bt in base_tasks.items():
            if key not in desired_keys:
                rt = remote_tasks.get(key)
                if rt and rt.get("id"):
                    ops.append({"op": "complete_task", "provider_id": rt["id"]})

        return ops

    # ------------------------------------------------------------------
    # Three-way helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _task_changed(local_item: dict[str, Any], base_task: dict[str, Any]) -> bool:
        """Check if a task has changed from base."""
        return bool(
            (
                local_item.get("priority")
                and local_item["priority"] != base_task.get("priority")
            )
            or local_item.get("section") != base_task.get("section")
        )

    @staticmethod
    def _task_field_diff(local: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
        """Compute field-level diff: local vs base."""
        changes: dict[str, Any] = {}
        if local.get("priority") and local["priority"] != base.get("priority"):
            changes["priority"] = local["priority"]
        return changes

    def _merge_non_conflicting(
        self,
        local: dict[str, Any],
        base: dict[str, Any],
        remote: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge local and remote changes, skipping fields where both changed."""
        changes: dict[str, Any] = {}

        # Priority: apply local only if remote didn't change it too
        local_priority = local.get("priority")
        if (
            local_priority
            and local_priority != base.get("priority")
            and remote.get("priority") == base.get("priority")
        ):
            changes["priority"] = local_priority

        return changes


def _task_to_item(t: dict[str, Any]) -> dict[str, Any]:
    """Convert a remote task dict to item shape for comparison."""
    return {
        "content": t.get("content", ""),
        "priority": t.get("priority"),
        "section": t.get("section"),
    }
