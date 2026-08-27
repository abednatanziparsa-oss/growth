"""Unit tests for PlanReviewer and PlanImprover (v0.8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from growth.application.dtos import DecisionArtifact
from growth.application.errors import LLMUnavailableError
from growth.application.plan_review import PlanImprover, PlanReviewer
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId

SUGGESTIONS = "- Split chapter 3 into two tasks.\n- Reschedule the overdue quiz."


def _artifact(
    recommendation: Any, reasoning: str | None = "reason"
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
    """DecisionEngine double with per-query canned recommendations."""

    per_query: dict[str, Any]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def recommend(
        self,
        query: str,
        *,
        space_id: Any = None,
        context: dict[str, object] | None = None,
    ) -> DecisionArtifact:
        self.calls.append({"query": query, "space_id": space_id})
        return _artifact(self.per_query.get(query))


@dataclass
class FakeLlm:
    reply: str = SUGGESTIONS
    calls: list[dict[str, Any]] = field(default_factory=list)

    def chat(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        self.calls.append({"system": system, "user": user, "temperature": temperature})
        return self.reply


@dataclass
class DeadLlm:
    def chat(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        raise LLMUnavailableError("offline")


# -- PlanReviewer --------------------------------------------------------------


def test_review_aggregates_all_queries() -> None:
    engine = FakeEngine(
        {
            "next_action": {"title": "Algebra"},
            "blockers": [{"title": "quiz"}],
            "priority_sort": ["a", "b"],
        }
    )

    review = PlanReviewer(engine).review()

    assert review.capability == "plan_review"
    assert review.recommendation == {
        "next_action": {"title": "Algebra"},
        "blockers": [{"title": "quiz"}],
        "priority_sort": ["a", "b"],
    }
    assert review.model is None
    assert review.prompt_version is None
    assert review.cost_estimate == 0.0
    assert review.created_at is not None


def test_review_queries_each_engine_once() -> None:
    engine = FakeEngine({})

    PlanReviewer(engine).review()

    assert [c["query"] for c in engine.calls] == [
        "next_action",
        "blockers",
        "priority_sort",
    ]


def test_review_passes_space_id() -> None:
    engine = FakeEngine({})

    PlanReviewer(engine).review(space_id=DEFAULT_SPACE_ID)

    assert all(c["space_id"] == DEFAULT_SPACE_ID for c in engine.calls)


def test_review_handles_missing_queries_as_none() -> None:
    engine = FakeEngine({})  # unknown queries → None recommendations

    review = PlanReviewer(engine).review()

    assert review.recommendation == {
        "next_action": None,
        "blockers": None,
        "priority_sort": None,
    }


# -- PlanImprover --------------------------------------------------------------


def _review() -> DecisionArtifact:
    return _artifact(
        {
            "next_action": {"title": "Algebra"},
            "blockers": [{"title": "quiz"}],
            "priority_sort": ["a"],
        },
        reasoning="Deterministic review.",
    )


def test_improve_success_records_metadata() -> None:
    llm = FakeLlm()

    result = PlanImprover(llm, model="fake/model").improve(_review())

    assert result.capability == "plan_improvement"
    assert result.recommendation == SUGGESTIONS
    assert result.model == "fake/model"
    assert result.prompt_version == "growth-plan-improve-v1"
    assert result.cost_estimate is None
    # The review payload reaches the prompt.
    assert "quiz" in llm.calls[0]["user"]
    assert llm.calls[0]["system"]
    assert llm.calls[0]["temperature"] == 0.3


def test_improve_strips_whitespace() -> None:
    result = PlanImprover(FakeLlm(reply=f"  {SUGGESTIONS}  ")).improve(_review())

    assert result.recommendation == SUGGESTIONS


def test_improve_truncates_long_suggestions() -> None:
    result = PlanImprover(FakeLlm(reply="x" * 5000)).improve(_review())

    assert isinstance(result.recommendation, str)
    assert len(result.recommendation) <= 2000


def test_improve_llm_unavailable_falls_back() -> None:
    review = _review()

    result = PlanImprover(DeadLlm()).improve(review)

    assert result.capability == "plan_improvement"
    assert result.recommendation == review.recommendation
    assert "LLM unavailable (offline)" in (result.reasoning or "")
    assert result.model is None
    assert result.prompt_version is None
    assert result.cost_estimate == 0.0


def test_improve_empty_reply_falls_back() -> None:
    review = _review()

    result = PlanImprover(FakeLlm(reply="   ")).improve(review)

    assert result.recommendation == review.recommendation
    assert "empty suggestions" in (result.reasoning or "")
    assert result.model is None
