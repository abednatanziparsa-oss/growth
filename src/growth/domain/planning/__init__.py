"""Planning bounded context — aggregate roots and value objects.

The planning domain is the canonical home of structured plans.
Aggregates:

- **Workspace** — top-level container (personal, work, ...)
- **Project** — a named collection of goals (e.g. "Placement Exam Prep")
- **Goal** — a measurable outcome within a project
- **Milestone** — a checkpoint on the way to a goal
- **Task** — a single actionable item (leaf of the tree)

Design invariant: the task tree (parent/child) is a DAG enforced at the
aggregate boundary. No cycle, no orphan, max depth configurable.

See docs/adr/0002-knowledge-centric-architecture.md for the relationship
between Planning, Knowledge, and Execution.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Final

from growth.domain.shared import InternalId, SpaceId

__all__ = [
    "Goal",
    "Milestone",
    "Priority",
    "PriorityError",
    "Project",
    "Task",
    "TaskTreeError",
    "Workspace",
    "max_task_depth",
]

#: Maximum nesting depth for parent/child task relationships.
#: Configurable at construction time; this is the default.
max_task_depth: Final[int] = 5


# =============================================================================
# Value objects
# =============================================================================


class Priority(StrEnum):
    """Canonical priority vocabulary (provider-agnostic).

    Provider projections map these to provider-specific values:
    - Todoist: URGENT=4, HIGH=3, MEDIUM=2, LOW=1
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class PriorityError(ValueError):
    """Raised when a priority value cannot be mapped to ``Priority``."""


# =============================================================================
# Common base for tree-able entities
# =============================================================================


@dataclass(kw_only=True)
class _PlanNode(ABC):
    """Common base for entities that live in the plan tree.

    All plan nodes have an identity, a title, a space, and timestamps.
    Concrete subclasses add their own invariants.
    """

    id: InternalId = field(default_factory=InternalId)
    title: str
    space_id: SpaceId
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Task — leaf node, may have subtasks (tree)
# =============================================================================


@dataclass(kw_only=True, slots=True)
class Task(_PlanNode):
    """A single actionable item, optionally the root of a subtask tree.

    Tasks are the leaves of the plan tree. A task may have subtasks
    (parent/child nesting) up to ``max_task_depth`` levels deep.
    """

    description: str | None = None
    priority: Priority | None = None
    parent_id: InternalId | None = None
    """id of the parent task, or ``None`` for top-level tasks."""

    due_at: datetime | None = None
    completed_at: datetime | None = None
    tags: list[str] = field(default_factory=list)
    estimated_minutes: int | None = None
    """Optional effort estimate in minutes."""

    source_ref: str | None = None
    """Reference to the source that produced this task (file path, URL, ...)."""

    @property
    def is_completed(self) -> bool:
        """``True`` when the task has been marked done."""
        return self.completed_at is not None

    @property
    def is_root(self) -> bool:
        """``True`` when this task has no parent."""
        return self.parent_id is None

    def complete(self, at: datetime | None = None) -> None:
        """Mark this task as completed.

        Args:
            at: Completion timestamp. Defaults to now (caller provides).
        """
        self.completed_at = at
        self.updated_at = at or datetime.now()


class TaskTreeError(ValueError):
    """Raised when a task tree violates structural invariants."""


# =============================================================================
# Milestone — checkpoint on the way to a goal
# =============================================================================


@dataclass(kw_only=True, slots=True)
class Milestone(_PlanNode):
    """A named checkpoint within a Goal.

    Milestones carry a target date but are not actionable themselves.
    Tasks are attached to milestones via ``Task.parent_id`` (or the
    aggregate-level mapping that the repository materializes).
    """

    goal_id: InternalId
    target_date: datetime | None = None
    completed_at: datetime | None = None
    order: int = 0
    """Display order within the parent goal (lower = earlier)."""

    raw_description: str | None = None
    """Original description text (for rendering, not structured)."""

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None


# =============================================================================
# Goal — measurable outcome within a project
# =============================================================================


@dataclass(kw_only=True, slots=True)
class Goal(_PlanNode):
    """A measurable outcome within a Project.

    Goals contain milestones and (through the repository) tasks.
    """

    project_id: InternalId
    description: str | None = None
    priority: Priority | None = None
    target_date: datetime | None = None
    completed_at: datetime | None = None

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None


# =============================================================================
# Project — named collection of goals
# =============================================================================


@dataclass(kw_only=True, slots=True)
class Project(_PlanNode):
    """A named project within a Workspace.

    Projects contain goals, milestones, and tasks.
    """

    workspace_id: InternalId
    description: str | None = None
    color: str | None = None
    """Optional display color hint (hex or name, presentation only)."""

    emoji: str | None = None
    """Optional emoji prefix (e.g. "🧠" for a learning project)."""

    is_archived: bool = False


# =============================================================================
# Workspace — top-level container
# =============================================================================


@dataclass(kw_only=True, slots=True)
class Workspace(_PlanNode):
    """Top-level container separating contexts (personal, work, ...).

    Bootstrap ships a single default Workspace owned by the default Space.
    Multi-workspace support is additive — existing queries scoped to
    SpaceId automatically include new workspaces.
    """

    description: str | None = None
