"""Thin wrapper around the official ``todoist-api-python`` SDK.

The wrapper exists for three reasons:

1. Hide SDK object construction so the rest of the code stays readable.
2. Surface a uniform, small interface that :class:`DryRunClient` also
   implements (duck typing — no shared base class needed).
3. Translate SDK/Auth errors into clear messages with hints.
"""

from __future__ import annotations

from typing import Any

from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Project, Section, Task


class TodoistError(RuntimeError):
    """Raised when a Todoist API call fails or auth is missing."""


class TodoistClient:
    """A small facade over :class:`todoist_api_python.api.TodoistAPI`.

    Each ``add_*`` method returns the created SDK object so callers can use
    its ``id`` for follow-up calls (e.g. linking subtasks to a parent task).
    """

    def __init__(self, token: str) -> None:
        if not token or not token.strip():
            raise TodoistError(
                "Todoist API token is empty. Set TODOIST_API_TOKEN in your "
                "environment or .env file (see .env.example)."
            )
        try:
            self._api = TodoistAPI(token.strip())
        except Exception as exc:  # SDK raises various auth/config errors.
            raise TodoistError(f"Failed to initialize Todoist client: {exc}") from exc

    # -- creation methods --------------------------------------------------

    def add_project(self, name: str) -> Project:
        """Create a new project. Returns the created :class:`Project`."""

        try:
            return self._api.add_project(name=name)
        except Exception as exc:
            raise TodoistError(f"Failed to create project '{name}': {exc}") from exc

    def add_section(self, name: str, project_id: str) -> Section:
        """Create a section inside a project. Returns the created :class:`Section`."""

        try:
            return self._api.add_section(name=name, project_id=project_id)
        except Exception as exc:
            raise TodoistError(
                f"Failed to create section '{name}': {exc}"
            ) from exc

    def add_task(
        self,
        content: str,
        project_id: str,
        section_id: str | None = None,
        parent_id: str | None = None,
        priority: int = 1,
    ) -> Task:
        """Create a task.

        Note: ``section_id`` is ignored when ``parent_id`` is set, because
        Todoist makes subtasks inherit their parent's section. This matches
        the layout produced by :mod:`placement_exam.main`.

        Args:
            content: Task title.
            project_id: Target project.
            section_id: Target section (only for top-level tasks).
            parent_id: Parent task id (makes this a subtask).
            priority: 1 (Normal) .. 4 (Highest).

        Returns:
            The created :class:`Task`.
        """

        kwargs: dict[str, Any] = {
            "content": content,
            "project_id": project_id,
            "priority": priority,
        }
        if parent_id is not None:
            kwargs["parent_id"] = parent_id
        elif section_id is not None:
            kwargs["section_id"] = section_id

        try:
            return self._api.add_task(**kwargs)
        except Exception as exc:
            kind = "subtask" if parent_id else "task"
            raise TodoistError(
                f"Failed to create {kind} '{content}': {exc}"
            ) from exc
