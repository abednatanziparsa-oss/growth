"""Unit tests for the AI document summarizer (v0.6)."""

from __future__ import annotations

from growth.application.ai_documents import (
    _MAX_INPUT_CHARS,
    _PROMPT_VERSION,
    AiDocumentSummarizer,
)
from growth.application.errors import LLMUnavailableError


class _FakeLlm:
    """Records calls; returns a canned reply or raises on demand."""

    def __init__(self, reply: str | None = None, exc: Exception | None = None) -> None:
        self.reply = reply
        self.exc = exc
        self.calls: list[tuple[str, str, float]] = []

    def chat(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        self.calls.append((system, user, temperature))
        if self.exc is not None:
            raise self.exc
        assert self.reply is not None
        return self.reply


class TestAiDocumentSummarizer:
    def test_happy_path_records_artifact(self) -> None:
        llm = _FakeLlm(reply="- Key fact one\n- Key fact two")
        result = AiDocumentSummarizer(llm, model="gh/gpt-4o-mini").summarize(
            "long text", title="report.pdf"
        )

        assert result.summary == "- Key fact one\n- Key fact two"
        artifact = result.artifact
        assert artifact.capability == "document_summarizer"
        assert artifact.model == "gh/gpt-4o-mini"
        assert artifact.prompt_version == _PROMPT_VERSION
        assert artifact.recommendation == result.summary
        assert artifact.id.value is not None

        system, user, temperature = llm.calls[0]
        assert "report.pdf" in user
        assert "long text" in user
        assert temperature == 0.2
        assert "summarize" in system.lower()

    def test_llm_unavailable_returns_none_summary(self) -> None:
        llm = _FakeLlm(exc=LLMUnavailableError("backend down"))
        result = AiDocumentSummarizer(llm).summarize("some text")

        assert result.summary is None
        assert result.artifact.model is None
        assert result.artifact.prompt_version is None
        assert result.artifact.cost_estimate == 0.0
        assert "unavailable" in (result.artifact.reasoning or "")

    def test_empty_text_skips_llm(self) -> None:
        llm = _FakeLlm(reply="- nope")
        result = AiDocumentSummarizer(llm).summarize("   \n  ")

        assert result.summary is None
        assert llm.calls == []
        assert "No text" in (result.artifact.reasoning or "")

    def test_long_text_is_truncated(self) -> None:
        llm = _FakeLlm(reply="ok")
        body = "x" * (_MAX_INPUT_CHARS + 500) + "TAIL_MARKER"
        result = AiDocumentSummarizer(llm).summarize(body)

        assert result.summary == "ok"
        user = llm.calls[0][1]
        assert "TAIL_MARKER" not in user
        assert len(user) < _MAX_INPUT_CHARS + 200

    def test_default_model_is_none(self) -> None:
        llm = _FakeLlm(reply="ok")
        result = AiDocumentSummarizer(llm).summarize("text")
        assert result.artifact.model is None
