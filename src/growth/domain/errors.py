"""Domain error hierarchy.

Domain errors signal violations of invariants inside aggregate roots.
They are raised by domain code and caught at the application boundary
(use cases) where they are translated into user-facing outcomes.

Hierarchy:

    GrowthError                  (project root — see application.errors)
        └── DomainError          (domain invariant violations)
              ├── InvalidPriorityError
              ├── InvalidTaskTreeError
              └── ... (added per bounded context)

Bootstrap ships only the root and two example subclasses so the
shape is established. New domain errors are added as their contexts
land (v0.1 onwards).
"""

from __future__ import annotations

__all__ = [
    "DomainError",
    "InvalidPriorityError",
    "InvalidTaskTreeError",
]


class DomainError(Exception):
    """Base class for all domain-layer errors.

    Subclass this (rather than raising ``Exception`` or ``ValueError``
    directly) so callers can catch domain failures by category.
    """


class InvalidPriorityError(DomainError):
    """Raised when a priority value violates the domain's priority rules.

    Example: assigning a Todoist-style 1..4 integer to the canonical
    ``Priority`` value object, which uses ``low/medium/high/urgent``.
    """


class InvalidTaskTreeError(DomainError):
    """Raised when a task tree violates structural invariants.

    Example: a cycle in parent/child relationships, or a task whose
    depth exceeds the configured maximum.
    """
