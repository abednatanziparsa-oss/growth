"""AI-assisted plan interpretation — free text to CanonicalPlan.

v0.6 use case: a user pastes a natural-language plan (Persian, English,
anything) and the LLM lifts it into the canonical plan schema that
``PlanApplier`` already understands (project_name, subjects, chapters,
standard_subtasks, extra_sections).

Offline-first contract:

- The LLM is advisory. Nothing leaves the machine unless
  ``GROWTH_AI_ENABLED=true`` AND a backend is configured.
- Any ``LLMUnavailableError`` (disabled, unreachable, HTTP error,
  malformed reply) falls back to a deterministic heuristic that wraps
  the raw text in a minimal plan — queries never break.
- Every interpretation returns a ``DecisionArtifact`` recording model,
  prompt version, reasoning, and cost so the caller (CLI dry-run)
  can show what happened before persisting anything.

The fallback interpreter is injected (never imported from
infrastructure) so the application ring stays hexagonal.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from growth.application.dtos import CanonicalPlan, DecisionArtifact, RawPlan
from growth.application.errors import LLMUnavailableError
from growth.application.ports.interpreter import (
    InterpretationError,
    Interpreter,
)
from growth.application.ports.llm import LLMChat
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId, SpaceId

__all__ = ["AiInterpretation", "AiInterpreter", "parse_llm_json"]

_PROMPT_VERSION = "growth-plan-json-v1"

_SYSTEM_PROMPT = """\
You are a planning assistant inside Growth OS. You convert a user's \
free-text plan into a strict JSON object that the system can apply. \
Respond with ONLY the JSON object — no markdown fences, no prose, no \
comments.

The JSON must follow exactly this schema:

{
  "project_name": "short human-readable project name",
  "subjects": [
    {
      "name": "subject name",
      "priority": "urgent|high|medium|low",
      "chapters": [
        {"name": "chapter name", "weak": false}
      ]
    }
  ],
  "standard_subtasks": ["recurring subtask titles"],
  "extra_sections": ["sections without chapters"]
}

Rules:
- Keep every title in the user's original language.
- Preserve the user's ordering and grouping.
- When the user gives no explicit priority, use "medium".
- "weak": true marks chapters the user flagged as weak/needing review.
- If the user listed no standard subtasks, output an empty list.
- If the user listed no extra sections, output an empty list.
- Always include "project_name" as a non-empty string.
"""


@dataclass(frozen=True, slots=True)
class AiInterpretation:
    """Outcome of one AI-assisted interpretation.

    ``plan`` is the lifted CanonicalPlan; ``artifact`` records how the
    plan was produced (model, prompt version, reasoning) for audit and
    dry-run display. When the LLM was unavailable, ``artifact.model``
    is ``None`` and ``plan`` came from the heuristic fallback.
    """

    plan: CanonicalPlan
    artifact: DecisionArtifact


def parse_llm_json(content: str) -> dict[str, Any]:
    """Parse an LLM reply into a JSON object, tolerating common noise.

    Accepts raw JSON, JSON wrapped in ```json fences, and JSON buried
    in prose (first ``{...}`` block wins).

    Raises:
        ValueError: If no JSON object can be extracted.
    """
    text = content.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("no JSON object found in LLM output") from None
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("LLM output JSON root must be an object")
    return data


class AiInterpreter:
    """Lift free text into a CanonicalPlan with LLM assistance.

    Args:
        llm: The chat backend. May be a Noop that always raises
            ``LLMUnavailableError``.
        fallback: Deterministic interpreter used when the LLM is
            unavailable. Defaults to nothing — the composition root
            injects ``HeuristicInterpreter``.
        model: Model identifier recorded on successful artifacts
            (from ``Settings.llm_model``).
    """

    def __init__(
        self,
        llm: LLMChat,
        *,
        fallback: Interpreter,
        model: str | None = None,
    ) -> None:
        self._llm = llm
        self._fallback = fallback
        self._model = model

    def interpret(
        self,
        text: str,
        *,
        space_id: SpaceId | None = None,
        temperature: float = 0.2,
    ) -> AiInterpretation:
        """Interpret ``text`` into a plan, falling back on any LLM failure.

        Raises:
            InterpretationError: If the LLM answered but its output
                could not be lifted into a valid plan (unparseable or
                missing ``project_name``).
        """
        space = space_id or DEFAULT_SPACE_ID
        user_prompt = f"Plan text:\n{text}"

        try:
            content = self._llm.chat(
                _SYSTEM_PROMPT,
                user_prompt,
                temperature=temperature,
            )
        except LLMUnavailableError as exc:
            return self._fallback_interpret(text, space, reason=str(exc))

        try:
            payload = parse_llm_json(content)
        except ValueError as exc:
            raise InterpretationError(
                f"LLM returned unparseable output: {exc}"
            ) from exc

        project_name = payload.get("project_name")
        if not isinstance(project_name, str) or not project_name.strip():
            raise InterpretationError(
                "LLM output is missing a valid 'project_name' field"
            )

        plan = CanonicalPlan(
            space_id=space,
            created_at=datetime.now(UTC),
            project_name=project_name.strip(),
            raw_payload=payload,
        )
        artifact = DecisionArtifact(
            id=InternalId(),
            capability="plan_interpreter",
            recommendation={
                "project_name": plan.project_name,
                "subjects": len(payload.get("subjects", [])),
            },
            reasoning="CanonicalPlan lifted from free text via LLM.",
            model=self._model,
            prompt_version=_PROMPT_VERSION,
            cost_estimate=None,
            created_at=datetime.now(UTC),
        )
        return AiInterpretation(plan=plan, artifact=artifact)

    def _fallback_interpret(
        self,
        text: str,
        space: SpaceId,
        *,
        reason: str,
    ) -> AiInterpretation:
        """Deterministic fallback: wrap the text in a minimal plan.

        Uses the first non-empty line as the project name (or a fixed
        placeholder) and preserves the full text in ``raw_payload`` so
        nothing is silently dropped.
        """
        first_line = next(
            (line.strip() for line in text.splitlines() if line.strip()),
            None,
        )
        payload: dict[str, Any] = {
            "project_name": first_line or "Untitled Plan",
            "subjects": [],
            "standard_subtasks": [],
            "extra_sections": [],
            "source_text": text,
        }
        raw = RawPlan(source_format="text", payload=payload)
        plan = self._fallback.interpret(raw, space_id=space)
        artifact = DecisionArtifact(
            id=InternalId(),
            capability="plan_interpreter",
            recommendation={
                "project_name": plan.project_name,
                "subjects": 0,
            },
            reasoning=(
                f"LLM unavailable ({reason}); fell back to heuristic "
                "extraction. Apply to review the raw text as a plan."
            ),
            model=None,
            prompt_version=None,
            cost_estimate=0.0,
            created_at=datetime.now(UTC),
        )
        return AiInterpretation(plan=plan, artifact=artifact)
