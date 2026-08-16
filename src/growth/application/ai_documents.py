"""AI-assisted document summarization (v0.6).

Companion to the PDF parser: once a document's text is extracted,
``AiDocumentSummarizer`` produces a short Markdown summary through the
``LLMChat`` port. This is what makes document parsing "AI-assisted" —
the raw text stays offline and searchable either way; the summary is a
bonus for fast scanning and planning reference.

Offline-first contract (mirrors ``AiInterpreter``):

- The LLM is advisory. Nothing leaves the machine unless
  ``GROWTH_AI_ENABLED=true`` AND a backend is configured.
- Any ``LLMUnavailableError`` (disabled, unreachable, HTTP error,
  malformed reply) yields ``summary=None`` — callers show a skip
  message and continue; nothing crashes.
- Every attempt records a ``DecisionArtifact`` (model, prompt version,
  reasoning, cost) for auditability and dry-run display.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from growth.application.dtos import DecisionArtifact
from growth.application.errors import LLMUnavailableError
from growth.application.ports.llm import LLMChat
from growth.domain.shared import InternalId

__all__ = ["AiDocumentSummarizer", "AiDocumentSummary"]

_PROMPT_VERSION = "growth-doc-summary-v1"

#: Input cap for a single summarization call. Bounds token usage for
#: large documents; callers summarize page ranges if more is needed.
_MAX_INPUT_CHARS = 6000

_SYSTEM_PROMPT = """\
You are a document analyst inside Growth OS. You summarize documents \
for a personal knowledge base. Respond with ONLY a concise Markdown \
summary — no preamble, no closing notes.

Rules:
- Write in the document's original language (detect it from the text).
- 3-8 bullets or short paragraphs; keep it under 200 words.
- Preserve key facts, numbers, names, and decisions.
- If the text is empty or unreadable, reply with exactly: (no content)
"""


@dataclass(frozen=True, slots=True)
class AiDocumentSummary:
    """One AI-assisted document summary plus its audit artifact.

    ``summary`` is ``None`` when the LLM was unavailable (offline
    default) or when there was nothing to summarize; ``artifact``
    records how the attempt went (model ``None`` = no AI involved).
    """

    summary: str | None
    artifact: DecisionArtifact


class AiDocumentSummarizer:
    """Summarize extracted document text with LLM assistance."""

    def __init__(self, llm: LLMChat, *, model: str | None = None) -> None:
        self._llm = llm
        self._model = model

    def summarize(self, text: str, *, title: str | None = None) -> AiDocumentSummary:
        """Summarize ``text``, or return ``summary=None`` on any failure.

        Args:
            text: Extracted document text (may be long; truncated).
            title: Optional document title, included for context.
        """
        body = text.strip()
        if not body:
            return AiDocumentSummary(
                summary=None,
                artifact=DecisionArtifact(
                    id=InternalId(),
                    capability="document_summarizer",
                    recommendation=None,
                    reasoning="No text to summarize; skipped.",
                    model=None,
                    prompt_version=None,
                    cost_estimate=0.0,
                    created_at=datetime.now(UTC),
                ),
            )

        user_prompt = (
            f"Document: {title or '(untitled)'}\n\nText:\n{body[:_MAX_INPUT_CHARS]}"
        )
        try:
            summary = self._llm.chat(
                _SYSTEM_PROMPT,
                user_prompt,
                temperature=0.2,
            )
        except LLMUnavailableError as exc:
            return AiDocumentSummary(
                summary=None,
                artifact=DecisionArtifact(
                    id=InternalId(),
                    capability="document_summarizer",
                    recommendation=None,
                    reasoning=f"LLM unavailable ({exc}); summary skipped.",
                    model=None,
                    prompt_version=None,
                    cost_estimate=0.0,
                    created_at=datetime.now(UTC),
                ),
            )

        return AiDocumentSummary(
            summary=summary,
            artifact=DecisionArtifact(
                id=InternalId(),
                capability="document_summarizer",
                recommendation=summary,
                reasoning="Extracted document text summarized via LLM.",
                model=self._model,
                prompt_version=_PROMPT_VERSION,
                cost_estimate=None,
                created_at=datetime.now(UTC),
            ),
        )
