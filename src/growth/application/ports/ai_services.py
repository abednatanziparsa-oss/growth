"""AI service ports — opt-in capabilities, each with a Noop default.

Per the architecture review, AI is **isolated services, not core
dependencies**. Every capability defined here has a ``Noop*``
implementation that lets the system run fully offline. Concrete
backends (Ollama, OpenAI, Anthropic) implement these ports and are
wired in only when ``GROWTH_AI_ENABLED=true``.

Bootstrap scope: a small representative set of ports (TaskGenerator,
DifficultyEstimator). The full set (PrioritySuggester,
ScheduleOptimizer, KnowledgeExtractor, ResourceAnalyzer) is added as
each phase needs it.

Convention: every AI output is wrapped in a ``DecisionArtifact`` for
auditability (inputs, prompt version, model, cost). Acceptance is the
caller's responsibility — AI never mutates state directly.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from growth.application.dtos import DecisionArtifact
from growth.domain.shared import InternalId, SpaceId

__all__ = [
    "AiServices",
    "DifficultyEstimator",
    "TaskGenerator",
]


@runtime_checkable
class TaskGenerator(Protocol):
    """Generate subtasks for a parent task (advisory).

    Returns a ``DecisionArtifact`` whose ``recommendation`` is a list of
    suggested subtask titles. The caller decides whether to materialize
    them.
    """

    def generate(
        self,
        parent_title: str,
        *,
        space_id: SpaceId | None = None,
        context: dict[str, object] | None = None,
    ) -> DecisionArtifact:
        """Suggest subtasks for ``parent_title``."""
        ...


@runtime_checkable
class DifficultyEstimator(Protocol):
    """Estimate difficulty of a task (advisory).

    Returns a ``DecisionArtifact`` whose ``recommendation`` is a difficulty
    label from a fixed vocabulary (e.g. ``"easy"`` / ``"medium"`` /
    ``"hard"``). The Noop implementation returns ``"unknown"``.
    """

    def estimate(self, task_id: InternalId) -> DecisionArtifact:
        """Estimate difficulty for the given task."""
        ...


@runtime_checkable
class AiServices(Protocol):
    """Aggregate facade over all AI capabilities.

    The composition root exposes this single object so callers don't
    depend on individual capability ports. When ``GROWTH_AI_ENABLED``
    is ``false``, the implementation is ``NoopAiServices`` which returns
    safe defaults for every capability.
    """

    @property
    def task_generator(self) -> TaskGenerator:
        """The task-generation capability."""
        ...

    @property
    def difficulty_estimator(self) -> DifficultyEstimator:
        """The difficulty-estimation capability."""
        ...
