"""Integration tests for `growth plan ai-apply`.

Uses Typer's CliRunner with an in-memory SQLite DB (same pattern as
test_cli.py). Two flavors:

- default settings: AI disabled → the interpreter falls back to
  heuristics; dry-run shows the artifact and persists nothing;
- a container with a fake LLM backend: the LLM path is exercised
  end-to-end without any network call.
"""

from __future__ import annotations

import json
import sqlite3

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
from growth.infrastructure.sync.engine import init_sync_state
from growth.kernel.bootstrap import App
from growth.kernel.container import Container
from growth.presentation.cli.app import app

runner = CliRunner()

LLM_PAYLOAD = {
    "project_name": "AI Project",
    "subjects": [
        {
            "name": "هندسه",
            "priority": "high",
            "chapters": [{"name": "فصل ۱", "weak": True}],
        }
    ],
    "standard_subtasks": ["مطالعه"],
    "extra_sections": [],
}


class _FakeLlm:
    def chat(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        return json.dumps(LLM_PAYLOAD)


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


def _plan_count(db: sqlite3.Connection) -> int:
    return db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]


class TestAiApplyHelp:
    def test_plan_help_lists_ai_apply(self) -> None:
        result = runner.invoke(app, ["plan", "--help"])
        assert result.exit_code == 0
        assert "ai-apply" in result.stdout


class TestAiDisabled:
    def test_dry_run_shows_heuristic_fallback(self, monkeypatch) -> None:
        monkeypatch.setattr("growth.presentation.cli.app.build_app", _Factory())
        result = runner.invoke(
            app, ["plan", "ai-apply", "برنامه‌ی تابستانی\nجزئیات بیشتر"]
        )
        assert result.exit_code == 0
        assert "heuristic (AI disabled/unavailable)" in result.stdout
        assert "برنامه‌ی تابستانی" in result.stdout
        assert "[DRY-RUN]" in result.stdout
        assert "fell back to heuristic" in result.stdout

    def test_dry_run_persists_nothing(self, monkeypatch) -> None:
        factory = _Factory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        runner.invoke(app, ["plan", "ai-apply", "برنامه"])
        db = factory._db
        assert db is not None
        assert _plan_count(db) == 0

    def test_apply_persists_plan(self, monkeypatch) -> None:
        factory = _Factory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        result = runner.invoke(app, ["plan", "ai-apply", "برنامه‌ی تابستانی", "--apply"])
        assert result.exit_code == 0
        assert "[OK] Applied" in result.stdout
        db = factory._db
        assert db is not None
        assert _plan_count(db) == 1

        shown = runner.invoke(app, ["plan", "show"])
        assert "برنامه‌ی تابستانی" in shown.stdout


class TestLlmPath:
    def test_dry_run_shows_artifact_and_nothing_persisted(self, monkeypatch) -> None:
        factory = _Factory(llm=_FakeLlm())
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        result = runner.invoke(app, ["plan", "ai-apply", "برنامه‌ی ریاضی"])
        assert result.exit_code == 0
        assert "AI Project" in result.stdout
        assert "Subjects:       1" in result.stdout
        assert "Chapters:       1" in result.stdout
        assert "[DRY-RUN]" in result.stdout
        db = factory._db
        assert db is not None
        assert _plan_count(db) == 0

    def test_apply_persists_llm_plan(self, monkeypatch) -> None:
        factory = _Factory(llm=_FakeLlm())
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        result = runner.invoke(app, ["plan", "ai-apply", "برنامه‌ی ریاضی", "--apply"])
        assert result.exit_code == 0
        assert "[OK] Applied" in result.stdout
        db = factory._db
        assert db is not None
        assert _plan_count(db) == 1

        shown = runner.invoke(app, ["plan", "show"])
        assert "AI Project" in shown.stdout
        assert "هندسه" in shown.stdout
