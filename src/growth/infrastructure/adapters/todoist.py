"""Todoist provider adapter — talks to the Todoist REST API.

Implements the ``ProviderAdapter`` port with full read and write
capabilities. Used by the sync engine to:
- ``fetch_current``: pull live state from Todoist
- ``apply``: execute a ChangeSet against the Todoist API
"""

from __future__ import annotations

from typing import Any

from todoist_api_python.api import TodoistAPI

from growth.application.dtos import ApplyResult, ChangeSet, ProviderSnapshot
from growth.application.errors import ProviderUnavailableError

__all__ = ["TodoistAdapter"]


class TodoistAdapter:
    """Todoist API adapter — real implementation.

    Provides ``fetch_current`` and ``apply`` as required by the
    ``ProviderAdapter`` port. The adapter is *dumb*: it translates
    generic operations into Todoist API calls and reports results.
    All intelligence (diffing, conflict resolution, identity mapping)
    lives in the sync engine.
    """

    def __init__(self, api_token: str) -> None:
        self._api = TodoistAPI(api_token)

    @property
    def provider(self) -> str:
        return "todoist"

    # ------------------------------------------------------------------
    # fetch_current — pull live state from Todoist
    # ------------------------------------------------------------------

    def fetch_current(self, root_id: str | None) -> ProviderSnapshot:
        """Pull the live state of a Todoist project.

        Args:
            root_id: The Todoist project id, or ``None`` if nothing has
                been synced yet (returns empty snapshot).

        Returns:
            A ``ProviderSnapshot`` with the project, sections, and tasks
            currently on Todoist.

        Raises:
            ProviderUnavailableError: If the API cannot be reached.
        """
        if root_id is None:
            return ProviderSnapshot(provider="todoist", root_id=None, payload={})

        try:
            project = self._get_project(root_id)
            sections = self._get_sections(root_id)
            tasks = self._get_tasks(root_id)

            return ProviderSnapshot(
                provider="todoist",
                root_id=root_id,
                payload={
                    "project": project,
                    "sections": sections,
                    "tasks": tasks,
                },
            )
        except Exception as exc:
            raise ProviderUnavailableError(
                f"Failed to fetch Todoist state for project {root_id}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # apply — execute a ChangeSet against Todoist
    # ------------------------------------------------------------------

    def apply(self, changeset: ChangeSet) -> ApplyResult:
        """Execute a ``ChangeSet`` against the Todoist API.

        Best-effort: failed operations are recorded in the result rather
        than aborting the entire batch.

        Args:
            changeset: Ordered list of operations to apply.

        Returns:
            ``ApplyResult`` with counts and per-op details.

        Raises:
            ProviderUnavailableError: On fatal errors (auth, network).
        """
        applied = 0
        failed = 0
        errors: list[str] = []
        provider_ids: dict[str, str] = {}

        for op in changeset.operations:
            try:
                result = self._apply_op(op)
                applied += 1
                if result is not None:
                    internal_id = op.get("internal_id")
                    if internal_id:
                        provider_ids[internal_id] = result
            except Exception as exc:
                failed += 1
                errors.append(
                    f"op={op.get('op', 'unknown')} "
                    f"id={op.get('internal_id', '?')}: {exc}"
                )

        return ApplyResult(
            applied=applied,
            failed=failed,
            provider_ids=provider_ids,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Operation dispatcher
    # ------------------------------------------------------------------

    def _apply_op(self, op: dict[str, Any]) -> str | None:
        """Dispatch a single operation. Returns the provider resource id for creates."""
        action = op["op"]

        handlers: dict[str, Any] = {
            "create_project": lambda: self._api.add_project(name=op["name"]).id,
            "create_section": lambda: (
                self._api.add_section(name=op["name"], project_id=op["project_id"]).id
            ),
            "create_task": lambda: self._create_task(op),
            "complete_task": lambda: self._api.complete_task(task_id=op["provider_id"]),
            "update_task": lambda: self._api.update_task(
                task_id=op["provider_id"], content=op["content"]
            ),
            "delete_project": lambda: self._api.delete_project(
                project_id=op["provider_id"]
            ),
            "delete_section": lambda: self._api.delete_section(
                section_id=op["provider_id"]
            ),
        }

        handler = handlers.get(action)
        if handler is None:
            raise ValueError(f"Unknown operation: {action}")
        result = handler()
        return result if isinstance(result, str) else None

    # ------------------------------------------------------------------
    # Task creation (with subtask recursion)
    # ------------------------------------------------------------------

    def _create_task(self, op: dict[str, Any]) -> str:
        """Create a main task + any nested subtasks. Returns the parent task id."""
        task = self._api.add_task(
            content=op["content"],
            project_id=op.get("project_id"),
            section_id=op.get("section_id"),
            parent_id=op.get("parent_id"),
            priority=op.get("priority"),
            description=op.get("description"),
        )

        for sub in op.get("subtasks", []):
            self._create_task({**sub, "parent_id": task.id})

        return task.id

    # ------------------------------------------------------------------
    # Internal helpers: fetch individual resources
    # ------------------------------------------------------------------

    def _get_project(self, project_id: str) -> dict[str, Any]:
        p = self._api.get_project(project_id)
        return {
            "id": p.id,
            "name": p.name,
            "is_archived": p.is_archived,
            "color": getattr(p, "color", None),
            "is_favorite": getattr(p, "is_favorite", None),
        }

    def _get_sections(self, project_id: str) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        for page in self._api.get_sections(project_id=project_id):
            for s in page:
                sections.append({"id": s.id, "name": s.name, "order": s.order})
        return sections

    def _get_tasks(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch ACTIVE tasks of a project (Todoist omits completed ones)."""
        tasks: list[dict[str, Any]] = []
        for page in self._api.get_tasks(project_id=project_id):
            for t in page:
                tasks.append(
                    {
                        "id": t.id,
                        "content": t.content,
                        "section_id": t.section_id,
                        "parent_id": t.parent_id,
                        "priority": t.priority,
                        # SDK 4.x Task model has no ``is_completed``; a
                        # completed task is one with ``completed_at`` set.
                        "is_completed": t.completed_at is not None,
                        "order": t.order,
                        "description": t.description,
                        "labels": t.labels,
                    }
                )
        return tasks
