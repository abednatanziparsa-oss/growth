"""Unit tests for SemanticSearch — embedding-ranked knowledge search."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from growth.application.errors import EmbeddingUnavailableError
from growth.application.ports.knowledge import KnowledgeSearch
from growth.domain.knowledge import Attachment, AttachmentTarget, content_hash
from growth.domain.shared import DEFAULT_SPACE_ID, SpaceId
from growth.infrastructure.embeddings.local import LocalNGramEmbedder
from growth.infrastructure.storage.knowledge_repos import (
    AttachmentRepository,
    init_knowledge_db,
)
from growth.infrastructure.storage.semantic_search import SemanticSearch


def _new_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    init_knowledge_db(db)
    return db


def _attach(
    repo: AttachmentRepository,
    *,
    title: str,
    source_ref: str | None = None,
    space_id: SpaceId = DEFAULT_SPACE_ID,
) -> None:
    now = datetime.now(UTC)
    repo.save(
        Attachment(
            space_id=space_id,
            target_type=AttachmentTarget.TASK,
            title=title,
            content_hash=content_hash(title.encode()),
            source_ref=source_ref,
            created_at=now,
            updated_at=now,
        )
    )


class TestSemanticSearch:
    def test_implements_knowledge_search_port(self) -> None:
        db = _new_db()
        assert isinstance(SemanticSearch(db), KnowledgeSearch)

    def test_typo_tolerant_match(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        _attach(repo, title="growth roadmap.pdf")

        hits = SemanticSearch(db).search("roadmapp")

        assert len(hits) == 1
        assert hits[0].attachment.title == "growth roadmap.pdf"
        assert hits[0].score > 0

    def test_exact_title_ranks_above_similar_only(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        _attach(repo, title="growth roadmap.pdf")
        _attach(repo, title="roadmap thinking notes.pdf")

        hits = SemanticSearch(db).search("growth roadmap")

        assert len(hits) == 2
        assert hits[0].attachment.title == "growth roadmap.pdf"

    def test_unrelated_query_returns_empty(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        _attach(repo, title="growth roadmap.pdf")

        assert SemanticSearch(db).search("zzzzqqqq") == []

    def test_empty_query_returns_empty(self) -> None:
        db = _new_db()
        assert SemanticSearch(db).search("   ") == []

    def test_respects_space(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        other_space = SpaceId()
        _attach(repo, title="growth visible.pdf")
        _attach(repo, title="growth secret.pdf", space_id=other_space)

        hits = SemanticSearch(db).search("growth", space_id=DEFAULT_SPACE_ID)

        assert len(hits) == 1
        assert hits[0].attachment.title == "growth visible.pdf"

    def test_limit(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        for i in range(5):
            _attach(repo, title=f"growth plan {i}.pdf")

        hits = SemanticSearch(db).search("growth plan", limit=2)

        assert len(hits) == 2

    def test_snippet_prefers_title(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        _attach(repo, title="growth roadmap.pdf", source_ref="/data/notes.pdf")

        hits = SemanticSearch(db).search("growth")

        assert hits[0].snippet == "growth roadmap.pdf"

    def test_keyword_boost_beats_pure_similarity(self) -> None:
        """Exact keyword hits rank above merely-similar text."""
        db = _new_db()
        repo = AttachmentRepository(db)
        _attach(repo, title="physics quantum entanglement.pdf")
        _attach(repo, title="growth notes.pdf")

        hits = SemanticSearch(db).search("growth")

        assert hits[0].attachment.title == "growth notes.pdf"


class _RecordingEmbedder:
    """Deterministic fake embedder that records what it embedded."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [1.0, 0.0]  # identical vector -> max cosine for all texts


class _RaisingEmbedder:
    """Fake embedder that always fails (simulates Ollama being down)."""

    def embed(self, text: str) -> list[float]:
        raise EmbeddingUnavailableError("server unreachable")


class TestInjectedEmbedder:
    def test_uses_injected_embedder(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        _attach(repo, title="growth roadmap.pdf")
        embedder = _RecordingEmbedder()

        hits = SemanticSearch(db, embedder=embedder).search("growth")

        assert len(hits) == 1
        assert embedder.calls[0] == "growth"  # query embedded first
        assert any("growth roadmap.pdf" in c for c in embedder.calls)

    def test_embedder_defaults_to_local(self) -> None:
        db = _new_db()
        engine = SemanticSearch(db)

        assert isinstance(engine._embedder, LocalNGramEmbedder)

    def test_falls_back_offline_when_embedder_unavailable(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        _attach(repo, title="growth roadmap.pdf")

        hits = SemanticSearch(db, embedder=_RaisingEmbedder()).search("roadmapp")

        # No exception: the offline embedder takes over and still finds
        # the typo-tolerant match.
        assert len(hits) == 1
        assert hits[0].attachment.title == "growth roadmap.pdf"
