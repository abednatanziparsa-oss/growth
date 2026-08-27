"""Unit tests for the LLM-assisted Decision Engine wrapper (v0.8)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from growth.application.dtos import DecisionArtifact
from growth.application.errors import LLMUnavailableError
from growth.application.llm_decisions import LlmDecisionEngine
from growth.application.ports.decision import DecisionEngine
from growth.domain.shared import InternalId

ADVICE = "Start with Algebra: it unblocks the rest of Math."


def _artifact(
    recommendation: Any,
    reasoning: str | None = "engine reason",
) -> DecisionArtifact:
    return DecisionArtifact(
        id=InternalId(),
        capability="decision:test",
        recommendation=recommendation,
        reasoning=reasoning,
        model=None,
        prompt_version=None,
        cost_estimate=0.0,
        created_at=datetime(2026, 8, 27, 12, 0, tzinfo=UTC),
    )


@dataclass
class FakeEngine:
    """DecisionEngine double returning a canned artifact."""

    artifact: DecisionArtifact
    calls: list[dict[str, Any]] = field(default_factory=list)

    def recommend(
        self,
        query: str,
        *,
        space_id: Any = None,
        context: dict[str, object] | None = None,
    ) -> DecisionArtifact:
        self.calls.append({"query": query, "space_id": space_id, "context": context})
        return self.artifact


@dataclass
class FakeLlm:
    """LLMChat double returning a canned reply."""

    reply: str = ADVICE
    calls: list[dict[str, Any]] = field(default_factory=list)

    def chat(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        self.calls.append({"system": system, "user": user, "temperature": temperature})
        return self.reply


@dataclass
class DeadLlm:
    """LLMChat double that always reports the backend as unavailable."""

    def chat(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        raise LLMUnavailableError("offline")


def _engine(
    artifact: DecisionArtifact,
    llm: Any,
    *,
    model: str | None = "fake/model",
) -> tuple[LlmDecisionEngine, FakeEngine]:
    inner = FakeEngine(artifact)
    return LlmDecisionEngine(inner, llm, model=model), inner


# -- enrichment --------------------------------------------------------------


def test_enriches_reasoning_and_metadata() -> None:
    llm = FakeLlm()
    engine, _ = _engine(_artifact({"title": "Algebra"}), llm)

    result = engine.recommend("next_action")

    assert result.recommendation == {"title": "Algebra"}
    assert "engine reason" in (result.reasoning or "")
    assert ADVICE in (result.reasoning or "")
    assert result.model == "fake/model"
    assert result.prompt_version == "growth-decision-advice-v1"
    assert result.cost_estimate is None
    assert len(llm.calls) == 1


def test_preserves_capability_and_id() -> None:
    base = _artifact({"title": "Algebra"})
    engine, _ = _engine(base, FakeLlm())

    result = engine.recommend("next_action")

    assert result.capability == base.capability
    assert result.id == base.id
    assert result.created_at == base.created_at


def test_llm_receives_query_and_recommendation_json() -> None:
    llm = FakeLlm()
    engine, _ = _engine(_artifact({"title": "Algebra"}), llm)

    engine.recommend("next_action")

    user = llm.calls[0]["user"]
    assert "Query: next_action" in user
    assert json.dumps({"title": "Algebra"}, ensure_ascii=False) in user
    assert "Engine reasoning: engine reason" in user
    assert llm.calls[0]["system"]
    assert llm.calls[0]["temperature"] == 0.3


def test_context_forwarded_to_inner_and_prompt() -> None:
    llm = FakeLlm()
    engine, inner = _engine(_artifact({"title": "Algebra"}), llm)

    engine.recommend("next_action", context={"time_available": "morning"})

    assert inner.calls[0]["context"] == {"time_available": "morning"}
    assert "time_available" in llm.calls[0]["user"]


def test_space_id_forwarded_to_inner() -> None:
    engine, inner = _engine(_artifact({"title": "x"}), FakeLlm())

    engine.recommend("next_action")

    assert inner.calls[0]["space_id"] is None
    assert inner.calls[0]["query"] == "next_action"


def test_long_advice_truncated() -> None:
    engine, _ = _engine(_artifact({"title": "x"}), FakeLlm(reply="x" * 5000))

    result = engine.recommend("next_action")

    assert result.reasoning is not None
    assert len(result.reasoning) < 5000


def test_null_reasoning_base_still_enriches() -> None:
    engine, _ = _engine(_artifact({"title": "x"}, reasoning=None), FakeLlm())

    result = engine.recommend("next_action")

    assert (result.reasoning or "").startswith("| AI advice:")
    assert ADVICE in (result.reasoning or "")


# -- offline-first fallbacks ---------------------------------------------------


def test_no_recommendation_skips_llm() -> None:
    llm = FakeLlm()
    base = _artifact(None, reasoning="No actionable incomplete tasks.")
    engine, _ = _engine(base, llm)

    result = engine.recommend("next_action")

    assert llm.calls == []
    assert result is base


def test_empty_recommendation_skips_llm() -> None:
    llm = FakeLlm()
    base = _artifact([], reasoning="No overdue tasks.")
    engine, _ = _engine(base, llm)

    result = engine.recommend("blockers")

    assert llm.calls == []
    assert result is base


def test_llm_unavailable_returns_base_unchanged() -> None:
    base = _artifact({"title": "Algebra"})
    engine, _ = _engine(base, DeadLlm())

    result = engine.recommend("next_action")

    assert result is base
    assert result.reasoning == "engine reason"
    assert result.model is None
    assert result.prompt_version is None
    assert result.cost_estimate == 0.0


def test_empty_reply_returns_base() -> None:
    base = _artifact({"title": "Algebra"})
    engine, _ = _engine(base, FakeLlm(reply="   "))

    result = engine.recommend("next_action")

    assert result is base
    assert result.model is None


# -- port conformance ----------------------------------------------------------


def test_satisfies_decision_engine_port() -> None:
    engine = LlmDecisionEngine(FakeEngine(_artifact(None)), FakeLlm())
    assert isinstance(engine, DecisionEngine)
