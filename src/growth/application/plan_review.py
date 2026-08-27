"""Plan review + improvement use cases for declarative workflows (v0.8).

Completes the review loop promised in v0.7: ``PlanReviewer`` aggregates
the deterministic Decision Engine queries (next_action, blockers,
priority_sort) into a single review artifact — offline, reproducible,
zero AI. ``PlanImprover`` takes that review and asks the LLM for
concrete improvement suggestions (re-prioritization, splitting,
rescheduling, gaps).

Advisory-only and offline-first (mirrors ``AiInterpreter``):

- The LLM never mutates plan state; it produces suggestions wrapped in
  a ``DecisionArtifact`` that a human (or a later accept step) applies.
- Any ``LLMUnavailableError`` (AI disabled, unreachable, HTTP error)
  yields a fallback artifact noting the skip — workflow steps never
  fail just because the model is offline.
- Successful improvements record ``model``/``prompt_version`` on the
  artifact; the fallback records ``cost_estimate=0.0`` and ``model=None``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from growth.application.dtos import DecisionArtifact
from growth.application.errors import LLMUnavailableError
from growth.application.ports.decision import DecisionEngine
from growth.application.ports.llm import LLMChat
from growth.domain.shared import InternalId, SpaceId

__all__ = ["PlanImprover", "PlanReviewer"]

_IMPROVE_PROMPT_VERSION = "growth-plan-improve-v1"

#: The stable Decision Engine queries a review aggregates.
_REVIEW_QUERIES: tuple[str, ...] = ("next_action", "blockers", "priority_sort")

#: Cap for the serialized review embedded in the improvement prompt.
_MAX_REVIEW_CHARS = 6000

#: Cap for the LLM suggestions stored in the artifact recommendation.
_MAX_SUGGESTION_CHARS = 2000

_IMPROVE_SYSTEM_PROMPT = """\
You are a planning coach inside Growth OS. You receive a deterministic \
review of the user's current plan (next action, overdue blockers, \
priority-sorted tasks) as JSON. Produce concrete, actionable improvement \
suggestions. Write in the same language as the task titles. Rules:
- 2-5 short bullets; each one is a single concrete action (re-prioritize, \
split, reschedule, delegate, or flag a gap).
- Do not invent tasks that were not in the review.
- If the plan looks healthy, say so briefly instead of nitpicking.
- No preamble, no markdown fences.
"""


class PlanReviewer:
    """Aggregate the deterministic Decision Engine queries into one artifact.

    Args:
        engine: The deterministic engine (typically
            ``HeuristicDecisionEngine``). Deliberately NOT the
            LLM-wrapped engine — a review must stay reproducible and
            free; the LLM joins later, in ``PlanImprover``.
    """

    def __init__(self, engine: DecisionEngine) -> None:
        self._engine = engine

    def review(self, *, space_id: SpaceId | None = None) -> DecisionArtifact:
        """Produce a combined next_action/blockers/priority_sort artifact."""
        sections: dict[str, Any] = {
            query: self._engine.recommend(query, space_id=space_id).recommendation
            for query in _REVIEW_QUERIES
        }
        return DecisionArtifact(
            id=InternalId(),
            capability="plan_review",
            recommendation=sections,
            reasoning=(
                "Deterministic review: next_action + blockers + priority_sort "
                "from the heuristic Decision Engine."
            ),
            model=None,
            prompt_version=None,
            cost_estimate=0.0,
            created_at=datetime.now(UTC),
        )


class PlanImprover:
    """Ask the LLM for improvement suggestions over a deterministic review."""

    def __init__(self, llm: LLMChat, *, model: str | None = None) -> None:
        self._llm = llm
        self._model = model

    def improve(self, review: DecisionArtifact) -> DecisionArtifact:
        """Suggest improvements for ``review``, falling back offline.

        Args:
            review: A review artifact (typically from ``PlanReviewer``).
                Its ``recommendation`` is serialized into the prompt.
        """
        try:
            raw = self._llm.chat(
                _IMPROVE_SYSTEM_PROMPT,
                _improve_user_prompt(review),
                temperature=0.3,
            )
        except LLMUnavailableError as exc:
            return self._fallback(review, reason=str(exc))

        suggestions = raw.strip()[:_MAX_SUGGESTION_CHARS]
        if not suggestions:
            return self._fallback(review, reason="LLM returned empty suggestions")

        return DecisionArtifact(
            id=InternalId(),
            capability="plan_improvement",
            recommendation=suggestions,
            reasoning=(
                "Plan improvement suggestions generated via LLM "
                "from the deterministic review."
            ),
            model=self._model,
            prompt_version=_IMPROVE_PROMPT_VERSION,
            cost_estimate=None,
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def _fallback(review: DecisionArtifact, *, reason: str) -> DecisionArtifact:
        """Deterministic fallback artifact when the LLM is unavailable."""
        return DecisionArtifact(
            id=InternalId(),
            capability="plan_improvement",
            recommendation=review.recommendation,
            reasoning=(
                f"LLM unavailable ({reason}); improvement skipped — "
                "returning the deterministic review unchanged."
            ),
            model=None,
            prompt_version=None,
            cost_estimate=0.0,
            created_at=datetime.now(UTC),
        )


def _improve_user_prompt(review: DecisionArtifact) -> str:
    """Serialize a review artifact into the improvement prompt."""
    body = json.dumps(review.recommendation, ensure_ascii=False, default=str)
    return f"Plan review:\n{body[:_MAX_REVIEW_CHARS]}"
