"""Noop Decision Engine — produces "no recommendation" artifacts.

The Decision Engine is advisory-only (see port docstring). The Noop
variant returns artifacts whose ``recommendation`` is ``None`` and
whose reasoning explains that decision support is disabled. Wired
by the composition root until real heuristics land in v0.7.
"""

from __future__ import annotations

from growth.application.dtos import DecisionArtifact
from growth.application.ports.decision import DecisionQuery
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId, SpaceId
from growth.infrastructure.noop.clock import SystemClock

__all__ = ["NoopDecisionEngine"]


class NoopDecisionEngine:
    """Decision Engine that declines to recommend."""

    def recommend(
        self,
        query: DecisionQuery,
        *,
        space_id: SpaceId | None = None,
        context: dict[str, object] | None = None,
    ) -> DecisionArtifact:
        """Return a no-recommendation artifact for ``query``."""

        return DecisionArtifact(
            id=InternalId(),
            capability=f"decision:{query}",
            recommendation=None,
            reasoning="Decision engine disabled; no recommendation produced.",
            model=None,
            prompt_version=None,
            cost_estimate=0.0,
            created_at=SystemClock().now_utc(),
        )


def _default_space(space_id: SpaceId | None) -> SpaceId:
    """Resolve a SpaceId to its default when None."""

    return space_id if space_id is not None else DEFAULT_SPACE_ID
