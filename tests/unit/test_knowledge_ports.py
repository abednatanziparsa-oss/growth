"""Unit tests for the knowledge ports — adapter conforms to the port contracts."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from growth.application.ports.knowledge import (
    AttachmentRepository as AttachmentRepositoryPort,
    AttachmentSearchResult,
    KnowledgeSearch,
    KnowledgeSearchError,
)
from growth.domain.knowledge import Attachment, AttachmentTarget
from growth.domain.shared import DEFAULT_SPACE_ID
from growth.infrastructure.storage.knowledge_repos import (
    AttachmentRepository,
    KeywordSearch,
    init_knowledge_db,
)


def test_adapter_implements_repository_port() -> None:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    init_knowledge_db(db)

    repo = AttachmentRepository(db)

    assert isinstance(repo, AttachmentRepositoryPort)


def test_search_implements_knowledge_search_port() -> None:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    init_knowledge_db(db)

    search = KeywordSearch(db)

    assert isinstance(search, KnowledgeSearch)


def test_search_result_implements_port() -> None:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    init_knowledge_db(db)
    repo = AttachmentRepository(db)

    now = datetime.now(UTC)
    repo.save(
        Attachment(
            space_id=DEFAULT_SPACE_ID,
            target_type=AttachmentTarget.TASK,
            title="growth notes.pdf",
            created_at=now,
            updated_at=now,
        )
    )

    hits = KeywordSearch(db).search("growth")

    assert len(hits) == 1
    assert isinstance(hits[0], AttachmentSearchResult)


def test_port_error_is_exception() -> None:
    assert issubclass(KnowledgeSearchError, Exception)
