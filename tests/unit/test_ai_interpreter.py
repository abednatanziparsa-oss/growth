"""Unit tests for the AI-assisted plan interpreter.

Covers the happy path (LLM returns JSON), the tolerant JSON parser,
the offline-first fallback when the LLM is unavailable, and the
error contract when the LLM answers garbage.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from growth.application.ai_interpreter import (
    AiInterpretation,
    AiInterpreter,
    parse_llm_json,
)
from growth.application.dtos import CanonicalPlan, RawPlan
from growth.application.errors import LLMUnavailableError
from growth.application.ports.interpreter import InterpretationError
from growth.application.ports.llm import LLMChat
from growth.domain.shared import DEFAULT_SPACE_ID
from growth.infrastructure.interpreters.heuristic import HeuristicInterpreter
from growth.infrastructure.noop.llm import NoopLlmChat

GOOD_PAYLOAD = {
    "project_name": "ریاضی کنکور",
    "subjects": [
        {
            "name": "هندسه",
            "priority": "high",
            "chapters": [{"name": "فصل ۱", "weak": True}],
        }
    ],
    "standard_subtasks": ["مطالعه", "تمرین"],
    "extra_sections": ["مرور کلی"],
}


class _FakeLlm:
    """Configurable stand-in for the LLMChat port."""

    def __init__(
        self, *, reply: str | None = None, error: Exception | None = None
    ) -> None:
        self.reply = reply
        self.error = error
        self.calls: list[tuple[str, str, float]] = []

    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        self.calls.append((system, user, temperature))
        if self.error is not None:
            raise self.error
        assert self.reply is not None
        return self.reply


class TestParseLlmJson:
    def test_plain_json(self) -> None:
        assert parse_llm_json(json.dumps(GOOD_PAYLOAD)) == GOOD_PAYLOAD

    def test_json_fenced(self) -> None:
        text = f"```json\n{json.dumps(GOOD_PAYLOAD)}\n```"
        assert parse_llm_json(text) == GOOD_PAYLOAD

    def test_json_fenced_no_label(self) -> None:
        text = f"```\n{json.dumps(GOOD_PAYLOAD)}\n```"
        assert parse_llm_json(text) == GOOD_PAYLOAD

    def test_json_buried_in_prose(self) -> None:
        text = f"Sure! Here is your plan: {json.dumps(GOOD_PAYLOAD)} Hope it helps."
        assert parse_llm_json(text) == GOOD_PAYLOAD

    def test_non_object_root_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_llm_json("[1, 2, 3]")

    def test_no_json_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_llm_json("the model refused to answer")


class TestHappyPath:
    def test_plan_lifted_from_llm(self) -> None:
        llm = _FakeLlm(reply=json.dumps(GOOD_PAYLOAD))
        interpreter = AiInterpreter(llm, fallback=HeuristicInterpreter(), model="gpt-x")

        result = interpreter.interpret("برنامه‌ی ریاضی")

        assert isinstance(result, AiInterpretation)
        assert result.plan.project_name == "ریاضی کنکور"
        assert result.plan.raw_payload == GOOD_PAYLOAD
        assert result.plan.space_id == DEFAULT_SPACE_ID
        assert result.artifact.model == "gpt-x"
        assert result.artifact.prompt_version == "growth-plan-json-v1"
        assert result.artifact.capability == "plan_interpreter"
        assert result.artifact.recommendation == {
            "project_name": "ریاضی کنکور",
            "subjects": 1,
        }
        assert result.artifact.cost_estimate is None

    def test_prompt_sent_to_llm(self) -> None:
        llm = _FakeLlm(reply=json.dumps(GOOD_PAYLOAD))
        interpreter = AiInterpreter(llm, fallback=HeuristicInterpreter())

        interpreter.interpret("متن برنامه", temperature=0.0)

        system, user, temperature = llm.calls[0]
        assert "project_name" in system
        assert user == "Plan text:\nمتن برنامه"
        assert temperature == 0.0

    def test_whitespace_project_name_stripped(self) -> None:
        payload = dict(GOOD_PAYLOAD, project_name="  ریاضی  ")
        llm = _FakeLlm(reply=json.dumps(payload))
        interpreter = AiInterpreter(llm, fallback=HeuristicInterpreter())

        result = interpreter.interpret("x")

        assert result.plan.project_name == "ریاضی"


class TestFallback:
    def test_noop_llm_falls_back(self) -> None:
        interpreter = AiInterpreter(
            NoopLlmChat(),
            fallback=HeuristicInterpreter(),
        )

        result = interpreter.interpret("برنامه‌ی اول\nجزئیات بیشتر")

        assert result.plan.project_name == "برنامه‌ی اول"
        assert result.plan.raw_payload["subjects"] == []
        assert result.plan.raw_payload["source_text"] == "برنامه‌ی اول\nجزئیات بیشتر"
        assert result.artifact.model is None
        assert result.artifact.prompt_version is None
        assert result.artifact.cost_estimate == 0.0
        assert "fell back to heuristic" in (result.artifact.reasoning or "")

    def test_llm_error_falls_back(self) -> None:
        interpreter = AiInterpreter(
            _FakeLlm(error=LLMUnavailableError("backend down")),
            fallback=HeuristicInterpreter(),
        )

        result = interpreter.interpret("   \nبرنامه\n  ")

        assert result.plan.project_name == "برنامه"
        assert "backend down" in (result.artifact.reasoning or "")

    def test_empty_text_falls_back_to_placeholder(self) -> None:
        interpreter = AiInterpreter(
            NoopLlmChat(),
            fallback=HeuristicInterpreter(),
        )

        result = interpreter.interpret("   \n  ")

        assert result.plan.project_name == "Untitled Plan"

    def test_fallback_interpreter_is_used(self) -> None:
        seen: list[RawPlan] = []

        class SpyFallback:
            def interpret(
                self,
                raw: RawPlan,
                *,
                space_id=None,
            ) -> CanonicalPlan:
                seen.append(raw)
                return CanonicalPlan(
                    space_id=space_id or DEFAULT_SPACE_ID,
                    created_at=datetime.now(UTC),
                    project_name=raw.payload["project_name"],
                    raw_payload=raw.payload,
                )

        interpreter = AiInterpreter(NoopLlmChat(), fallback=SpyFallback())  # type: ignore[arg-type]

        result = interpreter.interpret("برنامه")

        assert seen[0].payload["project_name"] == "برنامه"
        assert result.plan.project_name == "برنامه"


class TestLlmGarbage:
    def test_unparseable_output_raises(self) -> None:
        interpreter = AiInterpreter(
            _FakeLlm(reply="I refuse to answer in JSON."),
            fallback=HeuristicInterpreter(),
        )
        with pytest.raises(InterpretationError):
            interpreter.interpret("برنامه")

    def test_missing_project_name_raises(self) -> None:
        interpreter = AiInterpreter(
            _FakeLlm(reply=json.dumps({"subjects": []})),
            fallback=HeuristicInterpreter(),
        )
        with pytest.raises(InterpretationError):
            interpreter.interpret("برنامه")

    def test_non_string_project_name_raises(self) -> None:
        interpreter = AiInterpreter(
            _FakeLlm(reply=json.dumps({"project_name": 42})),
            fallback=HeuristicInterpreter(),
        )
        with pytest.raises(InterpretationError):
            interpreter.interpret("برنامه")


class TestProtocolConformance:
    def test_noop_is_llm_chat_protocol(self) -> None:
        assert isinstance(NoopLlmChat(), LLMChat)

    def test_noop_raises_unavailable(self) -> None:
        with pytest.raises(LLMUnavailableError):
            NoopLlmChat().chat("s", "u")
