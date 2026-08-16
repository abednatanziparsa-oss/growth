"""Noop LLM backend — the offline-first default.

Raises ``LLMUnavailableError`` on every call so AI-assisted use cases
fall back to their deterministic heuristic path. This is the honest
Noop: AI is *disabled*, so no model call is attempted and no data
leaves the machine. Wired by the composition root whenever
``GROWTH_AI_ENABLED`` is false (the default).
"""

from __future__ import annotations

from growth.application.errors import LLMUnavailableError

__all__ = ["NoopLlmChat"]


class NoopLlmChat:
    """``LLMChat`` that always reports the backend as unavailable."""

    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        """Raise ``LLMUnavailableError`` (AI disabled)."""

        raise LLMUnavailableError(
            "AI is disabled (GROWTH_AI_ENABLED=false); no LLM configured."
        )
