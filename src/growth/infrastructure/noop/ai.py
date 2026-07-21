"""Noop AI services — safe defaults for every AI capability.

Returns ``DecisionArtifact`` records describing that no AI assistance
was applied. This lets the system run fully offline at bootstrap and
remains the default until ``GROWTH_AI_ENABLED=true`` selects real
backends in v0.6.
"""

from __future__ import annotations

from growth.application.dtos import DecisionArtifact
from growth.application.ports.ai_services import (
    DifficultyEstimator,
    TaskGenerator,
)
from growth.domain.shared import InternalId, SpaceId
from growth.infrastructure.noop.clock import SystemClock

__all__ = ["NoopAiServices", "NoopDifficultyEstimator", "NoopTaskGenerator"]


class NoopTaskGenerator:
    """``TaskGenerator`` that produces no suggestions."""

    def generate(
        self,
        parent_title: str,
        *,
        space_id: SpaceId | None = None,
        context: dict[str, object] | None = None,
    ) -> DecisionArtifact:
        """Return an artifact with an empty recommendation list."""

        return DecisionArtifact(
            id=InternalId(),
            capability="task_generator",
            recommendation=[],
            reasoning="AI disabled; no subtasks suggested.",
            model=None,
            prompt_version=None,
            cost_estimate=0.0,
            created_at=SystemClock().now_utc(),
        )


class NoopDifficultyEstimator:
    """``DifficultyEstimator`` that returns ``"unknown"`` for every task."""

    def estimate(self, task_id: InternalId) -> DecisionArtifact:
        """Return an artifact whose recommendation is ``"unknown"``."""

        return DecisionArtifact(
            id=InternalId(),
            capability="difficulty_estimator",
            recommendation="unknown",
            reasoning="AI disabled; difficulty not estimated.",
            model=None,
            prompt_version=None,
            cost_estimate=0.0,
            created_at=SystemClock().now_utc(),
        )


class NoopAiServices:
    """Aggregate AI facade whose every capability is a Noop.

    Wired by the composition root when ``Settings.ai_enabled`` is False
    (the default).
    """

    def __init__(self) -> None:
        self._task_generator: TaskGenerator = NoopTaskGenerator()
        self._difficulty_estimator: DifficultyEstimator = NoopDifficultyEstimator()

    @property
    def task_generator(self) -> TaskGenerator:
        return self._task_generator

    @property
    def difficulty_estimator(self) -> DifficultyEstimator:
        return self._difficulty_estimator
