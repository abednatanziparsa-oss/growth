"""Ollama-backed embedding provider — model vectors behind the Embeddings port.

v0.6 groundwork: this adapter calls Ollama's ``POST /api/embed`` endpoint
(current since Ollama 0.4.4) and L2-normalizes the result, so vectors are
directly comparable with ``LocalNGramEmbedder`` under cosine similarity.

The system stays offline-first: nothing constructs this class unless
``GROWTH_OLLAMA_BASE_URL`` is set. When the server is unreachable or
returns garbage, ``embed`` raises ``EmbeddingUnavailableError`` so
callers can fall back to the offline embedder.

Uses ``httpx`` (already a hard dependency of todoist-api-python, so it
is always installed; also declared in the ``ai`` extra for honesty).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import httpx

from growth.application.errors import EmbeddingUnavailableError

__all__ = ["OllamaEmbedder"]

_DEFAULT_BASE_URL = "http://127.0.0.1:11434"


def _l2_normalize(vector: Sequence[float]) -> list[float]:
    """Normalize a vector to unit length (zero vector stays zero)."""
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        return list(vector)
    return [v / norm for v in vector]


class OllamaEmbedder:
    """Fetch embeddings from a local Ollama server.

    Args:
        base_url: Ollama server base URL (without the ``/api/embed`` path).
        model: Embedding model name served by Ollama (default ``bge-m3``
            is multilingual and handles Persian/English mixes well).
        timeout: Per-request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        model: str = "bge-m3",
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def embed(self, text: str) -> Sequence[float]:
        """Return the L2-normalized embedding vector for ``text``.

        Raises:
            EmbeddingUnavailableError: If the server cannot be reached,
                returns a non-2xx status, or the payload is malformed.
        """
        try:
            response = httpx.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model, "input": [text]},
                timeout=self._timeout,
            )
            response.raise_for_status()
            vectors = response.json()["embeddings"]
            vector = _l2_normalize(vectors[0])
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise EmbeddingUnavailableError(
                f"Ollama embed failed (model={self._model}, url={self._base_url}): {exc}"
            ) from exc
        return vector
