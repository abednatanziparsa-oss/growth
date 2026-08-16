"""Integration tests: PDF parsing in the knowledge substrate (v0.6).

Covers the full loop: ``knowledge attach <pdf>`` extracts text into
``content_text`` (searchable via keyword AND semantic search), the
``knowledge extract`` command reports page/char stats and optionally
summarizes via a fake LLM, and the schema migration upgrades legacy
databases that predate the PDF parser.
"""

from __future__ import annotations

import sqlite3

import pytest
from typer.testing import CliRunner

from growth.application.plan_applier import PlanApplier
from growth.infrastructure.config.settings import Settings
from growth.infrastructure.events.sync_dispatcher import SyncEventDispatcher
from growth.infrastructure.logging.setup import configure_logging
from growth.infrastructure.noop.ai import NoopAiServices
from growth.infrastructure.noop.clock import SystemClock
from growth.infrastructure.noop.decision import NoopDecisionEngine
from growth.infrastructure.noop.workflow import NoopWorkflowEngine
from growth.infrastructure.storage.identity_map import (
    IdentityMap,
    init_identity_map,
)
from growth.infrastructure.storage.knowledge_repos import (
    AttachmentRepository,
    KeywordSearch,
    init_knowledge_db,
)
from growth.infrastructure.storage.planning_repos import (
    GoalRepository,
    MilestoneRepository,
    ProjectRepository,
    TaskRepository,
    WorkspaceRepository,
    init_db,
)
from growth.infrastructure.storage.semantic_search import SemanticSearch
from growth.infrastructure.sync.engine import init_sync_state
from growth.kernel.bootstrap import App
from growth.kernel.container import Container
from growth.presentation.cli.app import app

runner = CliRunner()


def _build_pdf(pages: list[str]) -> bytes:
    """Minimal valid PDF with one text line per page (see unit tests)."""
    n = len(pages)
    pages_num = 3 * n + 1
    body = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = [0]

    def emit(num: int, obj: bytes) -> None:
        offsets.append(len(body))
        body.extend(f"{num} 0 obj\n".encode() + obj + b"\nendobj\n")

    for i, text in enumerate(pages):
        content_num = 3 * i + 1
        font_num = 3 * i + 2
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
        emit(
            content_num,
            b"<< /Length "
            + str(len(stream)).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream",
        )
        emit(font_num, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        emit(
            3 * i + 3,
            (
                f"<< /Type /Page /Parent {pages_num} 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_num} 0 R "
                f"/Resources << /Font << /F1 {font_num} 0 R >> >> >>"
            ).encode(),
        )

    kids = " ".join(f"{3 * i + 3} 0 R" for i in range(n))
    emit(pages_num, f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    emit(3 * n + 2, f"<< /Type /Catalog /Pages {pages_num} 0 R >>".encode())

    xref_pos = len(body)
    body.extend(f"xref\n0 {3 * n + 3}\n".encode())
    body.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        body.extend(f"{off:010d} 00000 n \n".encode())
    body.extend(
        f"trailer\n<< /Size {3 * n + 3} /Root {3 * n + 2} 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(body)


class _FakeLlm:
    def chat(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        return "- Summarized point one\n- Summarized point two"


def _make_app(settings: Settings, container: Container, db: sqlite3.Connection) -> App:
    return App(
        settings=settings,
        container=container,
        db=db,
        workspace_repo=WorkspaceRepository(db),
        project_repo=ProjectRepository(db),
        goal_repo=GoalRepository(db),
        milestone_repo=MilestoneRepository(db),
        task_repo=TaskRepository(db),
        plan_applier=PlanApplier(
            WorkspaceRepository(db),
            ProjectRepository(db),
            GoalRepository(db),
            MilestoneRepository(db),
            TaskRepository(db),
        ),
        identity_map=IdentityMap(db),
        attachment_repo=AttachmentRepository(db),
        knowledge_search=KeywordSearch(db),
        semantic_search=SemanticSearch(db),
    )


class _Factory:
    """build_app replacement over one in-memory DB, with a pluggable LLM."""

    def __init__(self, *, llm: object | None = None) -> None:
        self._app: App | None = None
        self._db: sqlite3.Connection | None = None
        self._llm = llm

    def __call__(self) -> App:
        if self._app is not None:
            db = self._db
            assert db is not None
            return _make_app(self._app.settings, self._app.container, db)

        settings = Settings()
        configure_logging(settings)
        if self._llm is not None:
            container = Container(
                settings=settings,
                clock=SystemClock(),
                event_dispatcher=SyncEventDispatcher(),
                ai_services=NoopAiServices(),
                decision_engine=NoopDecisionEngine(),
                workflow_engine=NoopWorkflowEngine(),
                llm_chat=self._llm,  # type: ignore[arg-type]
            )
        else:
            container = Container.from_settings(settings)

        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        init_db(db)
        init_identity_map(db)
        init_sync_state(db)
        init_knowledge_db(db)
        self._db = db

        self._app = _make_app(settings, container, db)
        return self._app


@pytest.fixture
def pdf_path(tmp_path) -> object:
    path = tmp_path / "report.pdf"
    path.write_bytes(_build_pdf(["Roadmap alpha release planning"]))
    return path


class TestAttachExtractsPdf:
    def test_attach_stores_searchable_content_text(self, pdf_path, monkeypatch) -> None:
        factory = _Factory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        result = runner.invoke(app, ["knowledge", "attach", str(pdf_path)])
        assert result.exit_code == 0, result.stdout
        assert "1 page(s)" in result.stdout
        assert "char(s)" in result.stdout

        db = factory._db
        row = db.execute("SELECT content_text, mime_type FROM attachments").fetchone()
        assert row is not None
        assert "Roadmap alpha release planning" in row["content_text"]
        assert row["mime_type"] == "application/pdf"

    def test_keyword_search_finds_pdf_content(self, pdf_path, monkeypatch) -> None:
        factory = _Factory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        runner.invoke(app, ["knowledge", "attach", str(pdf_path)])

        result = runner.invoke(app, ["knowledge", "search", "alpha"])
        assert result.exit_code == 0
        assert "report.pdf" in result.stdout
        assert "Roadmap" in result.stdout  # snippet comes from content_text

    def test_semantic_search_finds_pdf_content(self, pdf_path, monkeypatch) -> None:
        factory = _Factory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        runner.invoke(app, ["knowledge", "attach", str(pdf_path)])

        result = runner.invoke(
            app, ["knowledge", "search", "alpha release", "--semantic"]
        )
        assert result.exit_code == 0
        assert "report.pdf" in result.stdout

    def test_attach_non_pdf_stores_no_content(self, tmp_path, monkeypatch) -> None:
        factory = _Factory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        txt = tmp_path / "notes.txt"
        txt.write_text("plain text", encoding="utf-8")

        result = runner.invoke(app, ["knowledge", "attach", str(txt)])
        assert result.exit_code == 0
        assert "page(s)" not in result.stdout

        db = factory._db
        row = db.execute("SELECT content_text, mime_type FROM attachments").fetchone()
        assert row is not None
        assert row["content_text"] is None
        assert row["mime_type"] is None

    def test_attach_corrupt_pdf_warns_but_attaches(self, tmp_path, monkeypatch) -> None:
        factory = _Factory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        bad = tmp_path / "broken.pdf"
        bad.write_bytes(b"not a pdf")

        result = runner.invoke(app, ["knowledge", "attach", str(bad)])
        assert result.exit_code == 0
        assert "[WARN]" in result.stderr

        db = factory._db
        row = db.execute("SELECT content_text FROM attachments").fetchone()
        assert row is not None
        assert row["content_text"] is None


class TestExtractCommand:
    def test_extract_reports_stats_and_preview(self, pdf_path, monkeypatch) -> None:
        factory = _Factory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        result = runner.invoke(app, ["knowledge", "extract", str(pdf_path)])
        assert result.exit_code == 0
        assert "report.pdf" in result.stdout
        assert "1 page(s)" in result.stdout
        assert "format=pdf" in result.stdout
        assert "Roadmap alpha release planning" in result.stdout

    def test_extract_fails_on_unreadable(self, tmp_path, monkeypatch) -> None:
        factory = _Factory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        bad = tmp_path / "junk.pdf"
        bad.write_bytes(b"junk")
        result = runner.invoke(app, ["knowledge", "extract", str(bad)])
        assert result.exit_code == 1
        assert "[ERROR]" in result.stderr

    def test_extract_empty_pdf_prints_no_preview(self, tmp_path, monkeypatch) -> None:
        factory = _Factory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        blank = tmp_path / "blank.pdf"
        blank.write_bytes(_build_pdf([]))

        result = runner.invoke(app, ["knowledge", "extract", str(blank)])
        assert result.exit_code == 0
        assert "0 page(s)" in result.stdout
        assert "0 char(s)" in result.stdout
        # No text preview for an empty document.
        assert "more chars" not in result.stdout

    def test_extract_long_pdf_notes_truncation(self, tmp_path, monkeypatch) -> None:
        factory = _Factory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        long_pdf = tmp_path / "long.pdf"
        long_pdf.write_bytes(_build_pdf(["A" * 2500]))

        result = runner.invoke(app, ["knowledge", "extract", str(long_pdf)])
        assert result.exit_code == 0
        assert "more chars" in result.stdout

    def test_extract_summarize_with_ai_disabled(self, pdf_path, monkeypatch) -> None:
        factory = _Factory()  # NoopLlmChat -> LLMUnavailableError
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        result = runner.invoke(
            app, ["knowledge", "extract", str(pdf_path), "--summarize"]
        )
        assert result.exit_code == 0
        assert "[SKIP]" in result.stdout

    def test_extract_summarize_with_fake_llm(self, pdf_path, monkeypatch) -> None:
        factory = _Factory(llm=_FakeLlm())
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        result = runner.invoke(
            app, ["knowledge", "extract", str(pdf_path), "--summarize"]
        )
        assert result.exit_code == 0
        assert "[AI:" in result.stdout
        assert "Summarized point one" in result.stdout


class TestSchemaMigration:
    def test_legacy_db_gets_new_columns(self) -> None:
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.execute(
            """
            CREATE TABLE attachments (
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
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            "CREATE UNIQUE INDEX idx_attachments_hash "
            "ON attachments (content_hash) WHERE content_hash IS NOT NULL"
        )

        init_knowledge_db(db)

        columns = {row["name"] for row in db.execute("PRAGMA table_info(attachments)")}
        assert "content_text" in columns
        assert "summary" in columns

    def test_migration_is_idempotent(self) -> None:
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        init_knowledge_db(db)
        init_knowledge_db(db)  # second run must not raise

        columns = {row["name"] for row in db.execute("PRAGMA table_info(attachments)")}
        assert "content_text" in columns
        assert "summary" in columns
