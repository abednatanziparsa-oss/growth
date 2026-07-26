"""Planning domain events — published when aggregates are created/updated.

These are small immutable dataclasses carrying minimal context (ids + titles).
Subscribers (read models, analytics, workflow triggers) react to these.

Convention: events are past-tense (``ProjectCreated``, not ``CreateProject``).
"""

from __future__ import annotations

from dataclasses import dataclass

from growth.domain.shared import InternalId, SpaceId

__all__ = [
    "GoalCreated",
    "MilestoneCreated",
    "ProjectCreated",
    "ProjectCreatedEvent",
    "TaskCompleted",
    "TaskCreated",
    "WorkspaceCreated",
]


@dataclass(frozen=True, slots=True)
class WorkspaceCreated:
    """Published when a new Workspace is created."""

    workspace_id: InternalId
    space_id: SpaceId
    title: str

    @property
    def event_type(self) -> str:
        return "planning.workspace.created"


@dataclass(frozen=True, slots=True)
class ProjectCreatedEvent:
    """Published when a new Project is created within a Workspace."""

    project_id: InternalId
    workspace_id: InternalId
    space_id: SpaceId
    title: str

    @property
    def event_type(self) -> str:
        return "planning.project.created"


# Shorter alias for backward compat in future code
ProjectCreated = ProjectCreatedEvent


@dataclass(frozen=True, slots=True)
class GoalCreated:
    """Published when a new Goal is created within a Project."""

    goal_id: InternalId
    project_id: InternalId
    space_id: SpaceId
    title: str

    @property
    def event_type(self) -> str:
        return "planning.goal.created"


@dataclass(frozen=True, slots=True)
class MilestoneCreated:
    """Published when a new Milestone is created within a Goal."""

    milestone_id: InternalId
    goal_id: InternalId
    space_id: SpaceId
    title: str

    @property
    def event_type(self) -> str:
        return "planning.milestone.created"


@dataclass(frozen=True, slots=True)
class TaskCreated:
    """Published when a new Task is created."""

    task_id: InternalId
    space_id: SpaceId
    title: str
    parent_id: InternalId | None = None

    @property
    def event_type(self) -> str:
        return "planning.task.created"


@dataclass(frozen=True, slots=True)
class TaskCompleted:
    """Published when a Task is marked complete."""

    task_id: InternalId
    completed_at: str  # ISO-8601 UTC

    @property
    def event_type(self) -> str:
        return "planning.task.completed"
