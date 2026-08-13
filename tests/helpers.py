"""Test helpers shared across integration tests."""

from __future__ import annotations

import sqlite3
import textwrap
from pathlib import Path
from tempfile import NamedTemporaryFile

from typer.testing import CliRunner

from growth.application.plan_applier import PlanApplier
from growth.application.scheduler import Scheduler
from growth.infrastructure.config.settings import Settings
from growth.infrastructure.embeddings.ollama import OllamaEmbedder
from growth.infrastructure.logging.setup import configure_logging
from growth.infrastructure.storage.identity_map import (
    IdentityMap,
    init_identity_map,
)
from growth.infrastructure.storage.knowledge_repos import (
    AttachmentRepository,
    KeywordSearch,
    init_knowledge_db,
)
from growth.infrastructure.storage.plan_store import PlanStore, init_plan_store
from growth.infrastructure.storage.planning_repos import (
    GoalRepository,
    MilestoneRepository,
    ProjectRepository,
    TaskRepository,
    WorkspaceRepository,
    init_db,
)
from growth.infrastructure.storage.reminder_repos import (
    ReminderRepository,
    init_reminder_db,
)
from growth.infrastructure.storage.semantic_search import SemanticSearch
from growth.infrastructure.sync.engine import init_sync_state
from growth.kernel.bootstrap import App
from growth.kernel.container import Container
from growth.presentation.cli.app import app

runner = CliRunner()


def yaml_file(content: str) -> Path:
    """Write YAML content to a temp file and return its path."""
    with NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(textwrap.dedent(content))
        return Path(f.name)


class SharedDbAppFactory:
    """build_app replacement sharing one in-memory DB across invocations."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings
        self._app: App | None = None
        self._db: sqlite3.Connection | None = None

    def __call__(self) -> App:
        if self._app is not None:
            db = self._db
            assert db is not None
            return App(
                settings=self._app.settings,
                container=self._app.container,
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
                plan_store=self._app.plan_store,
                reminder_repo=self._app.reminder_repo,
                event_dispatcher=self._app.container.event_dispatcher,
                scheduler=Scheduler(
                    self._app.reminder_repo,  # type: ignore[arg-type]
                    self._app.container.event_dispatcher,
                ),
                ollama_embedder=self._app.ollama_embedder,
            )

        settings = self._settings or Settings()
        configure_logging(settings)
        container = Container.from_settings(settings)

        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        init_db(db)
        init_identity_map(db)
        init_sync_state(db)
        init_knowledge_db(db)
        init_plan_store(db)
        init_reminder_db(db)
        self._db = db

        plan_store = PlanStore(db)
        reminder_repo = ReminderRepository(db)
        ollama_embedder = (
            OllamaEmbedder(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
            )
            if settings.ollama_base_url
            else None
        )

        self._app = App(
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
                plan_store=plan_store,
            ),
            identity_map=IdentityMap(db),
            attachment_repo=AttachmentRepository(db),
            knowledge_search=KeywordSearch(db),
            semantic_search=SemanticSearch(db),
            plan_store=plan_store,
            reminder_repo=reminder_repo,
            event_dispatcher=container.event_dispatcher,
            scheduler=Scheduler(reminder_repo, container.event_dispatcher),
            ollama_embedder=ollama_embedder,
        )
        return self._app


def apply_plan(monkeypatch, factory: SharedDbAppFactory, yaml: str) -> None:
    """Apply a YAML plan through the CLI against a shared factory."""
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    runner.invoke(app, ["plan", "apply", str(yaml_file(yaml))])
