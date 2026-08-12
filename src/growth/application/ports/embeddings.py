"""Embeddings port — vector representation of text for semantic search.

v0.4 ships a local, dependency-free embedder (hashed character n-grams)
so semantic search works offline. v0.6 adds model-backed embedders
(Ollama / OpenAI / Anthropic) behind this same boundary.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

__all__ = ["Embeddings"]


@runtime_checkable
class Embeddings(Protocol):
    """Produces dense vector representations of text.

    Implementations are conventionally L2-normalized so cosine
    similarity between two vectors is a dot product.
    """

    def embed(self, text: str) -> Sequence[float]:
        """Return the embedding vector for ``text``."""
        ...
