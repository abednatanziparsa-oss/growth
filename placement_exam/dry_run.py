"""Dry-run "client" that simulates Todoist creation locally.

Implements the same surface as :class:`placement_exam.todoist_client.TodoistClient`
so that ``main.py`` can swap between real and simulated execution by simply
choosing a different client object. No network calls are made.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _FakeResource:
    """A minimal stand-in for a Todoist project/section/task object."""

    id: str
    name: str


class DryRunClient:
    """Collects the actions that *would* be sent to Todoist and prints them.

    Counters (``projects``, ``sections``, ``parent_tasks``, ``subtasks``)
    are incremented as actions are recorded, so the caller can print a summary
    at the end without re-counting the plan.
    """

    def __init__(self) -> None:
        self.projects = 0
        self.sections = 0
        self.parent_tasks = 0
        self.subtasks = 0
        self._id_counter = 0

    # -- helpers -----------------------------------------------------------

    def _next_id(self) -> str:
        self._id_counter += 1
        return f"dry-{self._id_counter}"

    # -- same interface as TodoistClient -----------------------------------

    def add_project(self, name: str) -> _FakeResource:
        """Record a project creation."""

        self.projects += 1
        print(f"[dry-run] PROJECT  : {name}")
        return _FakeResource(id=self._next_id(), name=name)

    def add_section(self, name: str, project_id: str) -> _FakeResource:
        """Record a section creation."""

        self.sections += 1
        print(f"[dry-run] SECTION  : {name}")
        return _FakeResource(id=self._next_id(), name=name)

    def add_task(
        self,
        content: str,
        project_id: str,
        section_id: str | None = None,
        parent_id: str | None = None,
        priority: int = 1,
    ) -> _FakeResource:
        """Record a task creation (parent or subtask)."""

        if parent_id is None:
            self.parent_tasks += 1
            label = "PARENT   "
        else:
            self.subtasks += 1
            label = "subtask  "
        prio_tag = f" (P{5 - priority})" if priority else ""
        print(f"[dry-run] {label}: {content}{prio_tag}")
        return _FakeResource(id=self._next_id(), name=content)
