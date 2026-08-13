"""Semantic (embedding-based) search over attachments.

Implements the ``KnowledgeSearch`` port using an injectable embedder.
The default is a local, offline embedder (hashed character n-grams), so
semantic search works with zero setup. A model-backed embedder (e.g.
``OllamaEmbedder``) can be injected; if it fails with
``EmbeddingUnavailableError`` (server down, timeout, bad payload), the
search falls back to the offline embedder so queries never break.

Exact keyword matches are boosted so precise title hits still rank
first; embedding similarity adds recall for typos and paraphrases.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import Any

from growth.application.errors import EmbeddingUnavailableError
from growth.domain.knowledge import Attachment
from growth.domain.shared import SpaceId
from growth.infrastructure.embeddings.local import (
    LocalNGramEmbedder,
    cosine_similarity,
)
from growth.infrastructure.storage.knowledge_repos import (
    KeywordSearchHit,
    _row_to_attachment,
)

__all__ = ["SemanticSearch"]

#: Embedding-only hits need at least this similarity score (sim * 100)
#: to be returned. Exact keyword matches (boost > 0) always qualify.
#: Filters out hash-collision noise from unrelated text.
MIN_SIM_SCORE = 10.0


class SemanticSearch:
    """Rank attachments by embedding similarity to the query."""

    def __init__(self, db: sqlite3.Connection, embedder: Any | None = None) -> None:
        self._db = db
        self._embedder = embedder or LocalNGramEmbedder()
        self._fallback = LocalNGramEmbedder()

    def _embed(self, text: str) -> Sequence[float]:
        """Embed with the configured model, falling back offline on failure."""
        try:
            return self._embedder.embed(text)
        except EmbeddingUnavailableError:
            return self._fallback.embed(text)

    def search(
        self,
        query: str,
        *,
        space_id: SpaceId | None = None,
        limit: int = 10,
    ) -> list[KeywordSearchHit]:
        """Return attachments ranked by similarity, best first.

        Score = embedding similarity (0..100) + keyword boost (exact
        term hits). Hits with a zero score are excluded, so unrelated
        text never appears.
        """
        query_vec = self._embed(query)
        if not any(query_vec):
            return []

        rows = self._all_attachments(space_id)
        terms = [t.lower() for t in query.split() if t.strip()]

        hits: list[KeywordSearchHit] = []
        for row in rows:
            attachment = _row_to_attachment(row)
            score = self._score(attachment, query_vec, terms)
            if score <= 0:
                continue
            hits.append(
                KeywordSearchHit(
                    attachment=attachment,
                    snippet=self._make_snippet(attachment, terms),
                    score=score,
                )
            )

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _all_attachments(self, space_id: SpaceId | None) -> list[sqlite3.Row]:
        if space_id is None:
            return self._db.execute(
                "SELECT * FROM attachments ORDER BY created_at DESC"
            ).fetchall()
        return self._db.execute(
            "SELECT * FROM attachments WHERE space_id = ? ORDER BY created_at DESC",
            (str(space_id.value),),
        ).fetchall()

    def _score(
        self,
        attachment: Attachment,
        query_vec: Sequence[float],
        terms: list[str],
    ) -> float:
        """Embedding similarity (0..100) plus exact-keyword boost."""
        text = f"{attachment.title} {attachment.source_ref or ''}"
        vec = self._embed(text)
        sim = cosine_similarity(query_vec, vec)

        boost = 0.0
        title = attachment.title.lower()
        ref = (attachment.source_ref or "").lower()
        for term in terms:
            if term in title:
                boost += 2.0
            if term in ref:
                boost += 1.0

        if boost == 0.0 and sim * 100.0 < MIN_SIM_SCORE:
            return 0.0
        return round(sim * 100.0, 3) + boost

    @staticmethod
    def _make_snippet(attachment: Attachment, terms: list[str]) -> str:
        """Pick the field that matched and return a short snippet."""
        title = attachment.title
        lower_title = title.lower()
        for term in terms:
            if term in lower_title:
                return title[:120]
        ref = attachment.source_ref or ""
        if ref:
            return ref[:120]
        return ""
