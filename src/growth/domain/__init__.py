"""Domain layer — the canonical plan model and core value objects.

Pure: no I/O, no framework dependencies, no imports outside this package
(except the standard library). import-linter enforces this in CI.

v0.1 adds the full planning aggregate tree:
Workspace, Project, Goal, Milestone, Task.
"""

from __future__ import annotations

from growth.domain.errors import DomainError
from growth.domain.planning import (
    Goal,
    Milestone,
    Priority,
    Project,
    Task,
    Workspace,
)
from growth.domain.shared import InternalId, SpaceId

__all__ = [
    "DomainError",
    "Goal",
    "InternalId",
    "Milestone",
    "Priority",
    "Project",
    "SpaceId",
    "Task",
    "Workspace",
]
