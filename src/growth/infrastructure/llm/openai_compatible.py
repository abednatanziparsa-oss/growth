"""OpenAI-compatible chat backend — cloud LLMs behind the LLMChat port.

Talks to any ``POST {base_url}/chat/completions`` endpoint that speaks
the OpenAI wire format. Verified target for v0.6 (from Iran, free
tiers): GitHub Models at ``https://models.github.ai/inference`` with a
GitHub PAT as ``Authorization: Bearer``. OpenRouter (``:free`` models)
and any self-hosted gateway exposing the same shape work unchanged —
only ``GROWTH_LLM_BASE_URL``/``GROWTH_LLM_API_KEY`` change.

The system stays offline-first: nothing constructs this class unless
``GROWTH_AI_ENABLED=true`` AND a base URL AND an API key are set. Any
failure (timeout, HTTP error, malformed or empty payload) raises
``LLMUnavailableError`` so callers fall back to heuristics.

Uses ``httpx`` (already a hard dependency of todoist-api-python, so it
is always installed; also declared in the ``ai`` extra for honesty).
"""

from __future__ import annotations

import httpx

from growth.application.errors import LLMUnavailableError

__all__ = ["OpenAICompatibleChat"]

_CHAT_COMPLETIONS_PATH = "/chat/completions"


class OpenAICompatibleChat:
    """Chat completions client for OpenAI-compatible endpoints.

    Args:
        base_url: Server root WITHOUT the ``/chat/completions`` suffix,
            e.g. ``https://models.github.ai/inference``.
        model: Model identifier served by the endpoint (e.g. ``gpt-4o-mini``).
        api_key: Bearer token for ``Authorization`` (GitHub PAT for
            GitHub Models).
        timeout: Per-request timeout in seconds.
        client: Optional ``httpx.Client`` (tests inject a
            ``MockTransport``-backed client; production builds its own).
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        timeout: float = 60.0,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=timeout)

    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        """Return the assistant reply, or raise ``LLMUnavailableError``.

        Raises:
            LLMUnavailableError: For connection failures, non-2xx
                statuses, malformed JSON, or missing/empty content.
        """
        try:
            response = self._client.post(
                f"{self._base_url}{_CHAT_COMPLETIONS_PATH}",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temperature,
                    # Explicit non-streaming: some gateways (e.g. 9Router /
                    # Kiro) stream by default and return SSE chunks, which
                    # this adapter does not parse.
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise LLMUnavailableError(
                    "LLM returned empty content "
                    f"(model={self._model}, url={self._base_url})"
                )
        except LLMUnavailableError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMUnavailableError(
                f"LLM chat failed (model={self._model}, url={self._base_url}): {exc}"
            ) from exc
        return content
