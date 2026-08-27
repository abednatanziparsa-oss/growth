"""Heuristic Decision Engine — deterministic, advisory recommendations.

v0.7 real implementation of the ``DecisionEngine`` port. It reads the
planning task tree and produces ``DecisionArtifact`` recommendations for
the first three stable queries:

- ``next_action``    — the single most actionable incomplete task
- ``blockers``       — incomplete tasks that are past due (overdue)
- ``priority_sort``  — every incomplete task, sorted by priority then due

Advisory-only: the engine never mutates domain state. It reads tasks
through the injected ``TaskRepository`` and returns recommendations the
caller is free to accept or ignore (see ADR-0002).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from growth.application.dtos import DecisionArtifact
from growth.application.ports.decision import DecisionQuery
from growth.domain.planning import Priority, Task
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId, SpaceId
from growth.infrastructure.noop.clock import SystemClock
from growth.infrastructure.storage.planning_repos import TaskRepository

__all__ = ["HeuristicDecisionEngine"]

#: Ordering weight for the canonical priority vocabulary (lower sorts
#: first). ``None`` (unspecified) sorts last.
_PRIORITY_RANK: dict[Priority | None, int] = {
    Priority.URGENT: 0,
    Priority.HIGH: 1,
    Priority.MEDIUM: 2,
    Priority.LOW: 3,
    None: 4,
}

#: Sentinel for "no due date" so undated tasks sort after dated ones.
_FAR_FUTURE: datetime = datetime.max.replace(tzinfo=UTC)

#: Sentinel for "no effort estimate" so unestimated tasks sort last.
_MAX_EFFORT = 1_000_000_000


class HeuristicDecisionEngine:
    """Deterministic Decision Engine over the task tree.

    Args:
        task_repo: Read-only source of planning tasks.
        now: Callable returning the current UTC datetime (injectable for
            tests; defaults to the real wall clock).
    """

    def __init__(
        self,
        task_repo: TaskRepository,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._task_repo = task_repo
        self._now = now or SystemClock().now_utc

    def recommend(
        self,
        query: DecisionQuery,
        *,
        space_id: SpaceId | None = None,
        context: dict[str, object] | None = None,
    ) -> DecisionArtifact:
        """Produce a heuristic recommendation for ``query``."""
        space = space_id or DEFAULT_SPACE_ID
        if query == "next_action":
            return self._next_action(space)
        if query == "blockers":
            return self._blockers(space)
        if query == "priority_sort":
            return self._priority_sort(space)
        return self._artifact(query, None, f"Unknown decision query '{query}'.")

    # -- query implementations --------------------------------------------

    def _next_action(self, space: SpaceId) -> DecisionArtifact:
        actionable = self._actionable(self._all_tasks(space))
        if not actionable:
            return self._artifact(
                "next_action", None, "No actionable incomplete tasks."
            )
        actionable.sort(key=_sort_key)
        best = actionable[0]
        return self._artifact(
            "next_action",
            _summary(best),
            f"Highest-priority actionable task: '{best.title}'.",
        )

    def _blockers(self, space: SpaceId) -> DecisionArtifact:
        now = self._now()
        overdue = [
            t
            for t in self._all_tasks(space)
            if not t.is_completed and t.due_at is not None and t.due_at < now
        ]
        overdue.sort(key=lambda t: t.due_at or now)
        recommendation: list[dict[str, Any]] = []
        for t in overdue:
            due = t.due_at
            assert due is not None  # filtered above
            recommendation.append(
                {
                    "task_id": str(t.id),
                    "title": t.title,
                    "due_at": due.isoformat(),
                    "overdue_minutes": int((now - due).total_seconds() // 60),
                }
            )
        reasoning = (
            f"{len(overdue)} overdue task(s)." if overdue else "No overdue tasks."
        )
        return self._artifact("blockers", recommendation, reasoning)

    def _priority_sort(self, space: SpaceId) -> DecisionArtifact:
        incomplete = [t for t in self._all_tasks(space) if not t.is_completed]
        incomplete.sort(key=_sort_key)
        recommendation = [_summary(t) for t in incomplete]
        return self._artifact(
            "priority_sort",
            recommendation,
            f"{len(incomplete)} incomplete task(s) sorted by priority.",
        )

    # -- helpers ------------------------------------------------------------

    def _all_tasks(self, space: SpaceId) -> list[Task]:
        """Depth-first walk of the whole task tree under ``space``."""
        result: list[Task] = []
        stack = list(self._task_repo.list_top_level(space))
        while stack:
            task = stack.pop()
            result.append(task)
            stack.extend(self._task_repo.list_by_parent(task.id))
        return result

    @staticmethod
    def _actionable(tasks: list[Task]) -> list[Task]:
        """Incomplete tasks with no incomplete children."""
        incomplete = [t for t in tasks if not t.is_completed]
        parents_with_open_children = {
            t.parent_id for t in incomplete if t.parent_id is not None
        }
        return [t for t in incomplete if t.id not in parents_with_open_children]

    def _artifact(
        self,
        query: str,
        recommendation: Any,
        reasoning: str,
    ) -> DecisionArtifact:
        return DecisionArtifact(
            id=InternalId(),
            capability=f"decision:{query}",
            recommendation=recommendation,
            reasoning=reasoning,
            model=None,
            prompt_version=None,
            cost_estimate=0.0,
            created_at=self._now(),
        )


def _priority_rank(priority: Priority | None) -> int:
    return _PRIORITY_RANK.get(priority, 4)


def _sort_key(task: Task) -> tuple[int, int, datetime, int, str]:
    """Sort incomplete tasks: priority → due → effort → title."""
    has_due = 0 if task.due_at is not None else 1
    due = task.due_at if task.due_at is not None else _FAR_FUTURE
    effort = (
        task.estimated_minutes if task.estimated_minutes is not None else _MAX_EFFORT
    )
    return (_priority_rank(task.priority), has_due, due, effort, task.title)


def _summary(task: Task) -> dict[str, Any]:
    """Serialize a task into an advisory recommendation payload."""
    return {
        "task_id": str(task.id),
        "title": task.title,
        "priority": task.priority.value if task.priority is not None else None,
        "due_at": task.due_at.isoformat() if task.due_at is not None else None,
        "estimated_minutes": task.estimated_minutes,
    }
