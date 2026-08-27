"""LLM-assisted Decision Engine — heuristic core + AI rationale (v0.8).

Wraps the deterministic ``DecisionEngine`` (the v0.7 heuristic core)
with an ``LLMChat`` enrichment pass: the deterministic engine produces
the recommendation (a stable, reproducible payload) and the LLM adds a
short human rationale on top. The recommendation payload itself is
NEVER altered by the model — the AI only annotates.

Offline-first contract (mirrors ``AiInterpreter``/``AiDocumentSummarizer``):

- The LLM is advisory. Any ``LLMUnavailableError`` (disabled,
  unreachable, HTTP error, malformed reply) returns the deterministic
  artifact unchanged — queries never break.
- When there is nothing to advise on (``recommendation`` is falsy —
  e.g. no actionable tasks, no overdue blockers, unknown query) the
  LLM is not called at all.
- Successful enrichment is recorded on the artifact (``model``,
  ``prompt_version``) for auditability; ``cost_estimate`` becomes
  ``None`` because an LLM was involved.
"""

from __future__ import annotations

import json
from dataclasses import replace

from growth.application.dtos import DecisionArtifact
from growth.application.errors import LLMUnavailableError
from growth.application.ports.decision import DecisionEngine, DecisionQuery
from growth.application.ports.llm import LLMChat
from growth.domain.shared import SpaceId

__all__ = ["LlmDecisionEngine"]

_PROMPT_VERSION = "growth-decision-advice-v1"

#: Cap for the serialized recommendation embedded in the user prompt
#: (bounds token usage for large priority sorts).
_MAX_RECOMMENDATION_CHARS = 6000

#: Cap for the LLM advice stored in the artifact reasoning.
_MAX_ADVICE_CHARS = 1200

_SYSTEM_PROMPT = """\
You are an advisor inside Growth OS, a personal productivity system. A \
deterministic engine has already computed a recommendation (as JSON). \
Your job is to add a short human rationale — NOT to change the \
recommendation. Respond with 1-3 short, practical sentences. Write in \
the same language as the task titles. No preamble, no markdown fences, \
no lists."""


class LlmDecisionEngine:
    """Decision Engine that enriches a deterministic core with LLM advice.

    Args:
        inner: The deterministic engine producing the recommendation
            payload (typically ``HeuristicDecisionEngine``).
        llm: The chat backend. May be a Noop that always raises
            ``LLMUnavailableError`` (the offline default) — every
            query then returns the inner artifact unchanged.
        model: Model identifier recorded on enriched artifacts
            (from ``Settings.llm_model``).
    """

    def __init__(
        self,
        inner: DecisionEngine,
        llm: LLMChat,
        *,
        model: str | None = None,
    ) -> None:
        self._inner = inner
        self._llm = llm
        self._model = model

    def recommend(
        self,
        query: DecisionQuery,
        *,
        space_id: SpaceId | None = None,
        context: dict[str, object] | None = None,
    ) -> DecisionArtifact:
        """Produce the deterministic recommendation, then attach AI advice.

        The recommendation payload is exactly the inner engine's; only
        ``reasoning`` (advice appended), ``model``, ``prompt_version``,
        and ``cost_estimate`` may differ from the base artifact.
        """
        base = self._inner.recommend(query, space_id=space_id, context=context)
        if not base.recommendation:
            return base

        try:
            advice = self._llm.chat(
                _SYSTEM_PROMPT,
                self._user_prompt(query, base, context),
                temperature=0.3,
            )
        except LLMUnavailableError:
            return base

        advice = advice.strip()[:_MAX_ADVICE_CHARS]
        if not advice:
            return base

        return replace(
            base,
            reasoning=f"{base.reasoning or ''} | AI advice: {advice}".strip(),
            model=self._model,
            prompt_version=_PROMPT_VERSION,
            cost_estimate=None,
        )

    @staticmethod
    def _user_prompt(
        query: DecisionQuery,
        base: DecisionArtifact,
        context: dict[str, object] | None,
    ) -> str:
        """Build the enrichment prompt from the deterministic artifact."""
        recommendation = json.dumps(
            base.recommendation, ensure_ascii=False, default=str
        )
        parts = [
            f"Query: {query}",
            f"Recommendation: {recommendation[:_MAX_RECOMMENDATION_CHARS]}",
        ]
        if base.reasoning:
            parts.append(f"Engine reasoning: {base.reasoning}")
        if context:
            parts.append(
                "Context: " + json.dumps(context, ensure_ascii=False, default=str)
            )
        return "\n".join(parts)
