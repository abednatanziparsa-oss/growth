"""Composition root — build a runnable ``App`` from settings.

``build_app`` is what presentation-layer code (CLI today, desktop later)
calls to obtain a fully-wired application object. It:

1. Loads ``Settings`` from environment / .env.
2. Configures logging (structlog + file handler).
3. Constructs the DI ``Container``.
4. Initializes storage, identity map, sync state, and repositories.
5. Wraps everything in an ``App``.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from growth.application.calendar_sync import CalendarSync
from growth.application.dtos import CanonicalPlan
from growth.application.plan_applier import PlanApplier
from growth.application.ports.event_dispatcher import EventDispatcher
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
from growth.infrastructure.sync.engine import SyncEngine, init_sync_state
from growth.kernel.container import Container

if TYPE_CHECKING:
    from growth.infrastructure.adapters.calendar import GoogleCalendarAdapter

__all__ = ["App", "build_app"]


@dataclass(slots=True)
class App:
    """Runnable application facade: settings + wired container + repositories."""

    settings: Settings
    container: Container
    db: sqlite3.Connection = field(repr=False)
    workspace_repo: WorkspaceRepository = field(repr=False)
    project_repo: ProjectRepository = field(repr=False)
    goal_repo: GoalRepository = field(repr=False)
    milestone_repo: MilestoneRepository = field(repr=False)
    task_repo: TaskRepository = field(repr=False)
    plan_applier: PlanApplier = field(repr=False)
    identity_map: IdentityMap = field(repr=False)
    attachment_repo: AttachmentRepository = field(repr=False)
    knowledge_search: KeywordSearch = field(repr=False)
    semantic_search: SemanticSearch | None = field(default=None, repr=False)
    plan_store: PlanStore | None = field(default=None, repr=False)
    reminder_repo: ReminderRepository | None = field(default=None, repr=False)
    event_dispatcher: EventDispatcher | None = field(default=None, repr=False)
    scheduler: Scheduler | None = field(default=None, repr=False)
    ollama_embedder: OllamaEmbedder | None = field(default=None, repr=False)

    @property
    def calendar_adapter(self) -> GoogleCalendarAdapter | None:
        """Build the Google Calendar adapter on-demand (needs OAuth files).

        Returns None when the OAuth credentials/token are not configured.
        """
        credentials = self.settings.google_credentials_path
        token = self.settings.google_token_path
        if not credentials or not token:
            return None
        from growth.infrastructure.adapters.calendar import (
            GoogleCalendarAdapter,
            build_calendar_service,
        )

        service = build_calendar_service(token)
        return GoogleCalendarAdapter(service)

    @property
    def calendar_sync(self) -> CalendarSync | None:
        """Build the calendar push use case on-demand (needs OAuth files)."""
        if self.settings.google_credentials_path is None:
            return None
        if self.settings.google_token_path is None:
            return None
        if self.reminder_repo is None:
            return None
        adapter = self.calendar_adapter
        if adapter is None:
            return None
        from growth.infrastructure.projections.calendar import CalendarProjection

        return CalendarSync(
            self.reminder_repo,
            self.identity_map,  # type: ignore[arg-type]  # IdentityMapEntry ⊇ ProviderMapping
            CalendarProjection(),
            adapter,
        )

    def authorize_calendar(self) -> bool:
        """Run the Google OAuth flow; returns ``True`` on success."""
        credentials = self.settings.google_credentials_path
        token = self.settings.google_token_path
        if credentials is None or token is None:
            return False
        from growth.infrastructure.adapters.calendar import run_oauth_flow

        run_oauth_flow(credentials, token)
        return True

    @property
    def sync_engine(self) -> SyncEngine | None:
        """Build a sync engine on-demand (needs token from settings).

        Returns None when no provider token is configured.
        """
        token = self.settings.todoist_api_token
        if not token:
            return None
        from growth.infrastructure.adapters.todoist import TodoistAdapter
        from growth.infrastructure.projections.todoist import TodoistProjection

        projection = TodoistProjection()
        adapter = TodoistAdapter(token)
        return SyncEngine(projection, adapter, self.identity_map, self.db)

    def export_markdown(self, plan: CanonicalPlan) -> str:
        """Export a CanonicalPlan as a Markdown string."""
        from growth.infrastructure.projections.markdown import (
            MarkdownProjection,
        )

        projection = MarkdownProjection()
        snapshot = projection.project(plan)
        return str(snapshot.payload.get("content", ""))


def build_app(settings: Settings | None = None) -> App:
    """Build a runnable ``App``.

    Args:
        settings: Explicit settings, or ``None`` to load from environment.
    """
    if settings is None:
        settings = Settings()

    configure_logging(settings)
    container = Container.from_settings(settings)

    db_path = settings.data_dir / "growth.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    init_db(db)
    init_identity_map(db)
    init_sync_state(db)
    init_knowledge_db(db)
    init_plan_store(db)
    init_reminder_db(db)

    workspace_repo = WorkspaceRepository(db)
    project_repo = ProjectRepository(db)
    goal_repo = GoalRepository(db)
    milestone_repo = MilestoneRepository(db)
    task_repo = TaskRepository(db)
    identity_map = IdentityMap(db)
    attachment_repo = AttachmentRepository(db)
    knowledge_search = KeywordSearch(db)
    ollama_embedder = (
        OllamaEmbedder(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
        if settings.ollama_base_url
        else None
    )
    semantic_search = SemanticSearch(db, embedder=ollama_embedder)
    plan_store = PlanStore(db)
    reminder_repo = ReminderRepository(db)
    scheduler = Scheduler(reminder_repo, container.event_dispatcher)

    plan_applier = PlanApplier(
        workspace_repo,
        project_repo,
        goal_repo,
        milestone_repo,
        task_repo,
        plan_store=plan_store,
    )

    return App(
        settings=settings,
        container=container,
        db=db,
        workspace_repo=workspace_repo,
        project_repo=project_repo,
        goal_repo=goal_repo,
        milestone_repo=milestone_repo,
        task_repo=task_repo,
        plan_applier=plan_applier,
        identity_map=identity_map,
        attachment_repo=attachment_repo,
        knowledge_search=knowledge_search,
        semantic_search=semantic_search,
        plan_store=plan_store,
        reminder_repo=reminder_repo,
        event_dispatcher=container.event_dispatcher,
        scheduler=scheduler,
        ollama_embedder=ollama_embedder,
    )
