"""LLM chat port — text generation for AI-assisted features.

v0.6 introduces a single, narrow chat capability behind which every
cloud backend (GitHub Models, OpenRouter, Gemini later) can live. The
port is deliberately OpenAI-compatible in spirit: one ``chat`` call,
system + user messages, a temperature knob. Backends that speak other
protocols (e.g. Google's genai API) get a small adapter of their own —
callers never see the difference.

Convention: implementations raise ``LLMUnavailableError`` for any
failure (network, HTTP error, malformed response, empty content). The
system stays offline-first: callers treat this as a signal to fall
back to deterministic heuristics, never as a crash.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["LLMChat"]


@runtime_checkable
class LLMChat(Protocol):
    """Single-turn chat completion against an OpenAI-compatible backend.

    Implementations are stateless and idempotent for the same inputs
    (modulo backend nondeterminism). Non-streaming only — the system
    does not need token-by-token output at bootstrap.
    """

    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        """Return the assistant's reply to ``user`` given ``system``.

        Args:
            system: System prompt (instructions, output schema).
            user: The user's request text.
            temperature: Sampling temperature; lower is more
                deterministic. Defaults to ``0.2`` for structured output.

        Returns:
            The assistant message content as plain text.

        Raises:
            LLMUnavailableError: If the backend cannot be reached,
                returns a non-2xx status, or the payload is malformed
                (including empty content).
        """
        ...
