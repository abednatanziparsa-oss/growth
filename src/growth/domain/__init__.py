"""Domain layer — the canonical plan model and core value objects.

Pure: no I/O, no framework dependencies, no imports outside this package
(except the standard library). import-linter enforces this in CI.

Bootstrap scope: only the minimal primitives that ports reference
(``InternalId``, ``SpaceId``) plus the domain error hierarchy. Full
aggregate roots (Workspace, Project, Goal, Milestone, Task) land in
phase v0.1.
"""

from __future__ import annotations

from growth.domain.errors import DomainError
from growth.domain.shared import InternalId, SpaceId

__all__ = ["DomainError", "InternalId", "SpaceId"]
