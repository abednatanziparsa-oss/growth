"""SQLite-backed attachment repository + keyword search.

The knowledge substrate (v0.4) persists Attachment aggregates in a
``attachments`` table and provides a keyword (LIKE-based) search that
works offline with zero external dependencies. Embedding-based search
lands with the AI substrate (v0.6) behind the same ``KnowledgeSearch``
port.

Design notes:
- Content-addressed dedup: ``find_by_hash`` lets callers reuse an
  existing attachment instead of duplicating rows for identical bytes.
- Search is a simple case-insensitive LIKE over title and source_ref;
  sufficient for v0.4's offline file-referencing use case.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from growth.application.ports.repository import EntityNotFoundError
from growth.domain.knowledge import Attachment, AttachmentKind, AttachmentTarget
from growth.domain.shared import InternalId, SpaceId

__all__ = [
    "AttachmentRepository",
    "KeywordSearch",
    "KeywordSearchHit",
    "init_knowledge_db",
]


def init_knowledge_db(db: sqlite3.Connection) -> None:
    """Create the knowledge schema (attachments table) if missing."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS attachments (
            id TEXT PRIMARY KEY,
            space_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT,
            title TEXT NOT NULL,
            content_hash TEXT,
            mime_type TEXT,
            source_ref TEXT,
            size_bytes INTEGER,
            content_text TEXT,
            summary TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_attachments_target "
        "ON attachments (target_type, target_id)"
    )
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_attachments_hash "
        "ON attachments (content_hash)"
        " WHERE content_hash IS NOT NULL"
    )
    # v0.6 migration: add searchable content columns to databases
    # created before the PDF parser existed. Idempotent — no-op when
    # the columns are already present.
    _ensure_column(db, "attachments", "content_text", "TEXT")
    _ensure_column(db, "attachments", "summary", "TEXT")
    db.commit()


def _ensure_column(db: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    """Add ``column`` to ``table`` when missing.

    SQLite has no ``ADD COLUMN IF NOT EXISTS``; a PRAGMA check keeps
    this idempotent across re-runs and upgrades.
    """
    columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def _row_to_attachment(row: sqlite3.Row) -> Attachment:
    return Attachment(
        id=InternalId(UUID(row["id"])),
        space_id=SpaceId(UUID(row["space_id"])),
        kind=AttachmentKind(row["kind"]),
        target_type=AttachmentTarget(row["target_type"]),
        target_id=InternalId(UUID(row["target_id"])) if row["target_id"] else None,
        title=row["title"],
        content_hash=row["content_hash"],
        mime_type=row["mime_type"],
        source_ref=row["source_ref"],
        size_bytes=row["size_bytes"],
        content_text=row["content_text"],
        summary=row["summary"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


class AttachmentRepository:
    """SQLite persistence for Attachment aggregates."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def get(self, id: InternalId) -> Attachment:
        row = self._db.execute(
            "SELECT * FROM attachments WHERE id = ?", (str(id.value),)
        ).fetchone()
        if row is None:
            raise EntityNotFoundError(f"Attachment {id} not found")
        return _row_to_attachment(row)

    def save(self, attachment: Attachment) -> None:
        # Content-addressed dedup: if the same bytes were already stored
        # under a different id, this save is a no-op (the caller should
        # have looked up find_by_hash first).
        if attachment.content_hash is not None:
            existing = self._db.execute(
                "SELECT id FROM attachments WHERE content_hash = ? AND id != ?",
                (attachment.content_hash, str(attachment.id.value)),
            ).fetchone()
            if existing is not None:
                return

        row = self._db.execute(
            "SELECT id FROM attachments WHERE id = ?", (str(attachment.id.value),)
        ).fetchone()
        if row is None:
            self._db.execute(
                """
                INSERT INTO attachments (
                    id, space_id, kind, target_type, target_id, title,
                    content_hash, mime_type, source_ref, size_bytes,
                    content_text, summary, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(attachment.id.value),
                    str(attachment.space_id.value),
                    attachment.kind.value,
                    attachment.target_type.value,
                    str(attachment.target_id.value) if attachment.target_id else None,
                    attachment.title,
                    attachment.content_hash,
                    attachment.mime_type,
                    attachment.source_ref,
                    attachment.size_bytes,
                    attachment.content_text,
                    attachment.summary,
                    attachment.created_at.isoformat(),
                    attachment.updated_at.isoformat(),
                ),
            )
        else:
            self._db.execute(
                """
                UPDATE attachments SET title=?, mime_type=?, source_ref=?,
                   size_bytes=?, content_text=?, summary=?, updated_at=?
                WHERE id=?
                """,
                (
                    attachment.title,
                    attachment.mime_type,
                    attachment.source_ref,
                    attachment.size_bytes,
                    attachment.content_text,
                    attachment.summary,
                    attachment.updated_at.isoformat(),
                    str(attachment.id.value),
                ),
            )
        self._db.commit()

    def delete(self, id: InternalId) -> None:
        cur = self._db.execute("DELETE FROM attachments WHERE id = ?", (str(id.value),))
        if cur.rowcount == 0:
            raise EntityNotFoundError(f"Attachment {id} not found")
        self._db.commit()

    def list_by_target(
        self, target_type: AttachmentTarget, target_id: InternalId
    ) -> list[Attachment]:
        rows = self._db.execute(
            "SELECT * FROM attachments WHERE target_type = ? AND target_id = ? "
            "ORDER BY created_at DESC",
            (target_type.value, str(target_id.value)),
        ).fetchall()
        return [_row_to_attachment(r) for r in rows]

    def list_by_space(self, space_id: SpaceId) -> list[Attachment]:
        rows = self._db.execute(
            "SELECT * FROM attachments WHERE space_id = ? ORDER BY created_at DESC",
            (str(space_id.value),),
        ).fetchall()
        return [_row_to_attachment(r) for r in rows]

    def find_by_hash(self, content_hash: str) -> Attachment | None:
        row = self._db.execute(
            "SELECT * FROM attachments WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_attachment(row)


@dataclass(frozen=True, slots=True)
class KeywordSearchHit:
    """A LIKE-search hit: the attachment plus a matched-snippet."""

    attachment: Attachment
    snippet: str
    score: float


class KeywordSearch:
    """Offline keyword search over attachments (title + source_ref).

    Implements the ``KnowledgeSearch`` port. Zero external dependencies:
    case-insensitive LIKE with basic relevance scoring (title matches
    score higher than source_ref matches).
    """

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def search(
        self,
        query: str,
        *,
        space_id: SpaceId | None = None,
        limit: int = 10,
    ) -> list[KeywordSearchHit]:
        terms = [t.strip() for t in query.split() if t.strip()]
        if not terms:
            return []

        # Build the SQL with one LIKE per term against the title,
        # source reference, and (v0.6) extracted content text.
        conditions: list[str] = []
        params: list[object] = []
        for term in terms:
            pattern = f"%{term}%"
            conditions.append(
                "(title LIKE ? OR source_ref LIKE ? OR content_text LIKE ?)"
            )
            params.extend([pattern, pattern, pattern])

        where = " AND ".join(conditions)
        if space_id is not None:
            where += " AND space_id = ?"
            params.append(str(space_id.value))

        params.append(limit)
        rows = self._db.execute(
            f"SELECT * FROM attachments WHERE {where} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()

        hits: list[KeywordSearchHit] = []
        for row in rows:
            attachment = _row_to_attachment(row)
            snippet = self._make_snippet(attachment, terms)
            score = self._score(attachment, terms)
            hits.append(
                KeywordSearchHit(attachment=attachment, snippet=snippet, score=score)
            )

        # Stable sort by score desc
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score(attachment: Attachment, terms: list[str]) -> float:
        """Simple relevance: title hits weight more than ref/content hits."""
        score = 0.0
        title = attachment.title.lower()
        ref = (attachment.source_ref or "").lower()
        content = (attachment.content_text or "").lower()
        for term in terms:
            t = term.lower()
            if t in title:
                score += 2.0
            if t in ref:
                score += 1.0
            if t in content:
                score += 1.0
        return score

    @staticmethod
    def _make_snippet(attachment: Attachment, terms: list[str]) -> str:
        """Return a snippet from the first field that matches a term."""
        title = attachment.title
        lower_title = title.lower()
        content = attachment.content_text or ""
        ref = attachment.source_ref or ""
        for term in terms:
            t = term.lower()
            if t in lower_title:
                return title[:120]
            if t in content.lower():
                idx = content.lower().find(t)
                start = max(0, idx - 60)
                end = min(len(content), idx + 120)
                prefix = "..." if start > 0 else ""
                return f"{prefix}{content[start:end].strip()}"
            if t in ref.lower():
                return ref[:120]
        return ""
