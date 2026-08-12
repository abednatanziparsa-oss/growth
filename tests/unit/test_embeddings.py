"""Unit tests for the local n-gram embedder and cosine similarity."""

from __future__ import annotations

import math

import pytest

from growth.application.ports.embeddings import Embeddings
from growth.infrastructure.embeddings.local import (
    LocalNGramEmbedder,
    cosine_similarity,
)


class TestLocalNGramEmbedder:
    def test_implements_embeddings_port(self) -> None:
        assert isinstance(LocalNGramEmbedder(), Embeddings)

    def test_deterministic(self) -> None:
        embedder = LocalNGramEmbedder()
        assert embedder.embed("growth roadmap") == embedder.embed("growth roadmap")

    def test_vector_is_l2_normalized(self) -> None:
        vec = LocalNGramEmbedder().embed("growth os knowledge substrate")
        norm = math.sqrt(sum(v * v for v in vec))
        assert norm == pytest.approx(1.0)

    def test_empty_text_zero_vector(self) -> None:
        vec = LocalNGramEmbedder().embed("")
        assert all(v == 0.0 for v in vec)

    def test_similar_texts_closer_than_dissimilar(self) -> None:
        embedder = LocalNGramEmbedder()
        base = embedder.embed("growth roadmap plan")
        similar = embedder.embed("growth roadmap plan v2")
        unrelated = embedder.embed("quantum physics notes")

        assert cosine_similarity(base, similar) > cosine_similarity(base, unrelated)

    def test_typo_tolerance(self) -> None:
        embedder = LocalNGramEmbedder()
        exact = embedder.embed("roadmap")
        typo = embedder.embed("roadmapp")
        unrelated = embedder.embed("banana")

        assert cosine_similarity(exact, typo) > cosine_similarity(exact, unrelated)


class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_symmetric(self) -> None:
        a = [0.3, 0.9, 0.2]
        b = [0.8, 0.1, 0.5]
        assert cosine_similarity(a, b) == pytest.approx(cosine_similarity(b, a))

    def test_zero_vector(self) -> None:
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
        assert cosine_similarity([1.0, 2.0], [0.0, 0.0]) == 0.0

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="equal length"):
            cosine_similarity([1.0], [1.0, 2.0])
