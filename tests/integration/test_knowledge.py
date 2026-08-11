"""Integration tests for the knowledge substrate — AttachmentRepository + KeywordSearch."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from growth.application.ports.repository import EntityNotFoundError
from growth.domain.knowledge import (
    Attachment,
    AttachmentKind,
    AttachmentTarget,
    content_hash,
)
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId
from growth.infrastructure.storage.knowledge_repos import (
    AttachmentRepository,
    KeywordSearch,
    init_knowledge_db,
)


def _new_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    init_knowledge_db(db)
    return db


def _attach(
    *,
    title: str = "notes.pdf",
    target_type: AttachmentTarget = AttachmentTarget.TASK,
    target_id: InternalId | None = None,
    source_ref: str | None = "/tmp/notes.pdf",
    content: bytes | None = b"growth os knowledge substrate",
) -> Attachment:
    now = datetime.now(UTC)
    return Attachment(
        space_id=DEFAULT_SPACE_ID,
        kind=AttachmentKind.FILE,
        target_type=target_type,
        target_id=target_id,
        title=title,
        content_hash=content_hash(content) if content else None,
        mime_type="application/pdf",
        source_ref=source_ref,
        size_bytes=len(content) if content else None,
        created_at=now,
        updated_at=now,
    )


class TestAttachmentRepository:
    def test_save_and_get(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        a = _attach()

        repo.save(a)
        got = repo.get(a.id)

        assert got.title == "notes.pdf"
        assert got.kind == AttachmentKind.FILE
        assert got.content_hash == a.content_hash

    def test_get_missing_raises(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)

        with pytest.raises(EntityNotFoundError):
            repo.get(InternalId())

    def test_delete(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        a = _attach()

        repo.save(a)
        repo.delete(a.id)

        with pytest.raises(EntityNotFoundError):
            repo.get(a.id)

    def test_delete_missing_raises(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)

        with pytest.raises(EntityNotFoundError):
            repo.delete(InternalId())

    def test_list_by_target(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        task_id = InternalId()

        repo.save(_attach(title="a.pdf", target_id=task_id, content=b"aaa"))
        repo.save(_attach(title="b.pdf", target_id=task_id, content=b"bbb"))
        repo.save(_attach(title="other.pdf"))

        hits = repo.list_by_target(AttachmentTarget.TASK, task_id)
        assert len(hits) == 2
        assert {h.title for h in hits} == {"a.pdf", "b.pdf"}

    def test_list_by_space(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)

        repo.save(_attach(title="a.pdf", content=b"aaa"))
        repo.save(_attach(title="b.pdf", content=b"bbb"))

        hits = repo.list_by_space(DEFAULT_SPACE_ID)
        assert len(hits) == 2

    def test_find_by_hash_dedup(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)

        data = b"identical bytes"
        a1 = _attach(title="one.pdf", content=data)
        a2 = _attach(title="two.pdf", content=data)

        repo.save(a1)
        found = repo.find_by_hash(content_hash(data))

        assert found is not None
        assert found.id.value == a1.id.value

        # Save a2 with same hash — find_by_hash still returns a1 (dedup)
        repo.save(a2)
        found2 = repo.find_by_hash(content_hash(data))
        assert found2 is not None
        assert found2.id.value == a1.id.value

    def test_find_by_hash_missing(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)

        assert repo.find_by_hash("nonexistent-hash") is None

    def test_update_title(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        a = _attach(title="old.pdf")

        repo.save(a)
        a.title = "new.pdf"
        repo.save(a)

        got = repo.get(a.id)
        assert got.title == "new.pdf"


class TestKeywordSearch:
    def test_search_by_title(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        search = KeywordSearch(db)

        repo.save(_attach(title="growth roadmap.pdf"))
        repo.save(_attach(title="todoist notes.pdf"))

        hits = search.search("growth")
        assert len(hits) == 1
        assert hits[0].attachment.title == "growth roadmap.pdf"

    def test_search_by_source_ref(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        search = KeywordSearch(db)

        repo.save(_attach(title="x.pdf", source_ref="/data/secret.pdf"))

        hits = search.search("secret")
        assert len(hits) == 1

    def test_search_case_insensitive(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        search = KeywordSearch(db)

        repo.save(_attach(title="Growth Plan.pdf"))

        hits = search.search("GROWTH")
        assert len(hits) == 1

    def test_search_multi_term_and(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        search = KeywordSearch(db)

        repo.save(_attach(title="growth os plan.pdf"))
        repo.save(_attach(title="growth notes.pdf"))

        hits = search.search("growth plan")
        assert len(hits) == 1
        assert hits[0].attachment.title == "growth os plan.pdf"

    def test_search_no_match(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        search = KeywordSearch(db)

        repo.save(_attach(title="a.pdf"))

        assert search.search("zzz") == []

    def test_search_empty_query(self) -> None:
        db = _new_db()
        search = KeywordSearch(db)

        assert search.search("   ") == []

    def test_search_respects_space(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        search = KeywordSearch(db)

        other_space_id = InternalId()
        now = datetime.now(UTC)
        repo.save(
            Attachment(
                space_id=other_space_id,  # type: ignore[arg-type]
                target_type=AttachmentTarget.TASK,
                title="growth secret.pdf",
                created_at=now,
                updated_at=now,
            )
        )
        repo.save(_attach(title="growth visible.pdf"))

        hits = search.search("growth", space_id=DEFAULT_SPACE_ID)
        assert len(hits) == 1
        assert hits[0].attachment.title == "growth visible.pdf"

    def test_title_scores_higher_than_ref(self) -> None:
        db = _new_db()
        repo = AttachmentRepository(db)
        search = KeywordSearch(db)

        # Only matches in source_ref -> 1.0
        repo.save(_attach(title="something", source_ref="/data/alpha.pdf", content=b"aaa"))
        # Only matches in title -> 2.0 (should rank first)
        repo.save(_attach(title="beta alpha", source_ref="/other", content=b"bbb"))

        hits = search.search("alpha")
        assert len(hits) == 2
        assert hits[0].attachment.title == "beta alpha"
        assert hits[0].score > hits[1].score
