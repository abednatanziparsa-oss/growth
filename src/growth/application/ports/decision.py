"""Decision Engine port — advisory recommendation engine.

CRITICAL architectural rule (see docs/adr/0002-knowledge-centric-architecture.md):
the Decision Engine is **advisory only**. It never mutates domain state.
It produces ``DecisionArtifact`` records (recommendations with
reasoning) that a human or the Workflow Engine accepts and forwards to
the proper use case.

This boundary is what prevents the Decision Engine from becoming a
god object: it cannot create/update/delete tasks directly; it can only
suggest. An import-linter rule will eventually enforce that Decision
implementations import no write-capable repository.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from growth.application.dtos import DecisionArtifact
from growth.domain.shared import SpaceId

__all__ = ["DecisionEngine", "DecisionQuery"]


#: Stable identifiers for the queries the Decision Engine answers.
#: Adding a new capability = adding a new literal here + an interpreter
#: for it. Bootstrap ships none; the first (``"next_action"``) lands in v0.7.
DecisionQuery = str


@runtime_checkable
class DecisionEngine(Protocol):
    """Answer "what should I do?"-style queries, advisorially.

    The engine reads from every relevant context (planning, execution,
    knowledge) and returns a ``DecisionArtifact`` describing its
    recommendation plus its reasoning. Acceptance is the caller's job.

    Bootstrap provides a ``NoopDecisionEngine`` (returns "no
    recommendation"). Real implementations land in v0.7.
    """

    def recommend(
        self,
        query: DecisionQuery,
        *,
        space_id: SpaceId | None = None,
        context: dict[str, object] | None = None,
    ) -> DecisionArtifact:
        """Produce a recommendation for ``query``.

        Args:
            query: Stable query id (e.g. ``"next_action"``, ``"blockers"``).
            space_id: Scope the recommendation to a Space.
            context: Optional extra context (e.g. available time today).

        Returns:
            A ``DecisionArtifact`` describing the recommendation. Even
            no-op responses wrap themselves in an artifact for auditability.
        """
        ...
