"""Local, offline embedding provider — deterministic character n-gram hashing.

v0.4 ships a zero-dependency embedder so semantic search works offline
with no model, no network, and no cost. v0.6 will add model-backed
embedders behind the same ``Embeddings`` port.

Mechanism: lowercase text is split into character n-grams (2-4), each
n-gram is hashed into a fixed-size vector with a sign bit, and the
result is L2-normalized. Similar texts share n-grams, so their vectors
are close under cosine similarity — enough to tolerate typos and
word-order differences that plain LIKE search misses.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence

__all__ = ["LocalNGramEmbedder", "cosine_similarity"]

_DIM = 256
_MIN_GRAM = 2
_MAX_GRAM = 4


def _digest(ngram: str) -> bytes:
    return hashlib.md5(ngram.encode("utf-8")).digest()


def _feature_index(ngram: str) -> int:
    return int.from_bytes(_digest(ngram)[:4], "big") % _DIM


def _feature_sign(ngram: str) -> float:
    return 1.0 if _digest(ngram)[4] % 2 == 0 else -1.0


def _ngrams(text: str) -> list[str]:
    lowered = text.lower()
    result: list[str] = []
    for n in range(_MIN_GRAM, _MAX_GRAM + 1):
        for i in range(len(lowered) - n + 1):
            result.append(lowered[i : i + n])
    return result


class LocalNGramEmbedder:
    """Hash character n-grams into a fixed-size, L2-normalized vector.

    Deterministic: the same input always produces the same vector, so
    embeddings can be compared across runs (no random state).
    """

    def embed(self, text: str) -> Sequence[float]:
        vec = [0.0] * _DIM
        for ngram in _ngrams(text):
            vec[_feature_index(ngram)] += _feature_sign(ngram)
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return vec
        return [v / norm for v in vec]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity between two vectors (0.0 when either is zero).

    Raises:
        ValueError: If the vectors have different lengths.
    """
    if len(a) != len(b):
        raise ValueError("vectors must have equal length")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
