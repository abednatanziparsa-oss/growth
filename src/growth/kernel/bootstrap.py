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
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from growth.application.calendar_sync import CalendarSync
from growth.application.dtos import CanonicalPlan
from growth.application.plan_applier import PlanApplier
from growth.application.ports.event_dispatcher import EventDispatcher
from growth.application.scheduler import Scheduler
from growth.domain.shared import DEFAULT_SPACE_ID
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
    from growth.application.ai_documents import AiDocumentSummarizer
    from growth.application.ai_interpreter import AiInterpreter
    from growth.application.llm_decisions import LlmDecisionEngine
    from growth.application.ports.document_parser import DocumentParser
    from growth.application.ports.workflow import WorkflowEngine
    from growth.infrastructure.adapters.calendar import GoogleCalendarAdapter
    from growth.infrastructure.decision.heuristic import HeuristicDecisionEngine

__all__ = [
    "App",
    "build_app",
    "load_workflows_dir",
    "persist_workflow_yaml",
    "register_workflow_yaml",
]


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

    @property
    def ai_interpreter(self) -> AiInterpreter:
        """Build the AI plan interpreter on-demand (always available).

        Uses the container's LLM backend — a real cloud client when
        AI is enabled and configured, otherwise a Noop that always
        raises, which makes the interpreter fall back to heuristics.
        """
        from growth.application.ai_interpreter import AiInterpreter
        from growth.infrastructure.interpreters.heuristic import (
            HeuristicInterpreter,
        )

        return AiInterpreter(
            self.container.llm_chat,
            fallback=HeuristicInterpreter(),
            model=self.settings.llm_model if self.settings.ai_enabled else None,
        )

    @property
    def document_parser(self) -> DocumentParser:
        """Parse local documents (PDFs today) for the knowledge substrate."""
        from growth.infrastructure.parsers.pdf import PypdfParser

        return PypdfParser()

    @property
    def ai_document_summarizer(self) -> AiDocumentSummarizer:
        """Summarize extracted document text (LLM-assisted, offline-safe)."""
        from growth.application.ai_documents import AiDocumentSummarizer

        return AiDocumentSummarizer(
            self.container.llm_chat,
            model=self.settings.llm_model if self.settings.ai_enabled else None,
        )

    @property
    def heuristic_decision_engine(self) -> HeuristicDecisionEngine:
        """Deterministic heuristic Decision Engine (advisory, no AI).

        Reads the task tree and returns recommendations; never mutates
        state. Always available — no AI/network required. This is the
        reproducible core; ``decision_engine`` wraps it with LLM advice.
        """
        from growth.infrastructure.decision.heuristic import HeuristicDecisionEngine

        return HeuristicDecisionEngine(self.task_repo)

    @property
    def decision_engine(self) -> LlmDecisionEngine:
        """LLM-assisted Decision Engine — heuristic core + AI rationale.

        The deterministic engine produces the recommendation payload;
        the LLM (when enabled and configured) appends human-readable
        advice to the artifact reasoning. With AI disabled (the default)
        the Noop LLM raises immediately, so recommendations are exactly
        the deterministic heuristic ones — queries never break.
        """
        from growth.application.llm_decisions import LlmDecisionEngine

        return LlmDecisionEngine(
            self.heuristic_decision_engine,
            self.container.llm_chat,
            model=self.settings.llm_model if self.settings.ai_enabled else None,
        )

    @property
    def workflow_engine(self) -> WorkflowEngine:
        """Declarative workflow engine (container-wired, in-memory)."""
        return self.container.workflow_engine

    def export_markdown(self, plan: CanonicalPlan) -> str:
        """Export a CanonicalPlan as a Markdown string."""
        from growth.infrastructure.projections.markdown import (
            MarkdownProjection,
        )

        projection = MarkdownProjection()
        snapshot = projection.project(plan)
        return str(snapshot.payload.get("content", ""))

    def export_calendar_ics(self) -> tuple[str, int]:
        """Render pending reminders as an iCalendar string.

        Returns:
            A ``(ics_text, event_count)`` pair. Past-due reminders are
            excluded; recurring reminders render their current occurrence.
        """
        from datetime import UTC, datetime

        from growth.domain.shared import DEFAULT_SPACE_ID
        from growth.infrastructure.projections.calendar import (
            CalendarProjection,
        )
        from growth.infrastructure.projections.ics import IcsProjection

        if self.reminder_repo is None:
            return "", 0
        now = datetime.now(UTC)
        reminders = [
            r
            for r in self.reminder_repo.list_pending(DEFAULT_SPACE_ID)
            if r.due_at >= now
        ]
        payloads = [CalendarProjection().project(r) for r in reminders]
        return IcsProjection().render(payloads), len(payloads)


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


def builtin_workflow_steps(
    app: App,
) -> dict[str, Callable[[dict[str, Any]], Any]]:
    """Built-in workflow steps wrapping real use cases (advisory).

    The decision steps route through ``app.decision_engine`` (heuristic
    core; LLM-enriched only when ``GROWTH_AI_ENABLED`` is on).
    ``plan-review`` aggregates the deterministic queries into one
    artifact; ``plan-improve`` asks the LLM for improvement suggestions
    over that review (offline-safe fallback).
    """
    from growth.application.plan_review import PlanImprover, PlanReviewer

    reviewer = PlanReviewer(app.heuristic_decision_engine)
    improver = PlanImprover(
        app.container.llm_chat,
        model=app.settings.llm_model if app.settings.ai_enabled else None,
    )
    return {
        "next-action": lambda _: app.decision_engine.recommend("next_action"),
        "blockers": lambda _: app.decision_engine.recommend("blockers"),
        "priority-sort": lambda _: app.decision_engine.recommend("priority_sort"),
        "plan-review": lambda _: reviewer.review(),
        "plan-improve": lambda _: improver.improve(reviewer.review()),
        "reminder-sweep": lambda _: (
            app.scheduler.sweep(DEFAULT_SPACE_ID) if app.scheduler is not None else None
        ),
        "export-ics": lambda _: app.export_calendar_ics(),
    }


def register_workflow_yaml(app: App, text: str) -> str:
    """Parse a workflow YAML document and register it on ``app``.

    Steps are resolved against the built-in step registry. Returns the
    registered workflow name. Registration is in-memory (per-process).
    """
    from growth.infrastructure.workflow.loader import parse_workflow_yaml

    workflow = parse_workflow_yaml(text, builtin_workflow_steps(app))
    app.workflow_engine.register(workflow)
    return workflow.name


def persist_workflow_yaml(app: App, text: str) -> str:
    """Validate, persist, and register a workflow YAML document.

    The document is written to ``app.settings.workflows_dir`` as
    ``<name>.yaml`` (replacing any previous file with the same name)
    and registered on the in-memory engine. Returns the workflow name.
    """
    from growth.infrastructure.workflow.loader import parse_workflow_yaml

    workflow = parse_workflow_yaml(text, builtin_workflow_steps(app))
    directory = app.settings.workflows_dir
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{workflow.name}.yaml"
    target.write_text(text, encoding="utf-8")
    app.workflow_engine.register(workflow)
    return workflow.name


def load_workflows_dir(app: App, directory: Path | None = None) -> int:
    """Load and register every ``*.yaml`` workflow from a directory.

    Returns the number of workflows registered. Raises
    ``WorkflowParseError`` on the first invalid file — explicit failure
    beats silently skipping a broken workflow.
    """
    from growth.infrastructure.workflow.loader import parse_workflow_yaml

    directory = directory or app.settings.workflows_dir
    if not directory.is_dir():
        return 0
    count = 0
    for path in sorted(directory.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        workflow = parse_workflow_yaml(text, builtin_workflow_steps(app))
        app.workflow_engine.register(workflow)
        count += 1
    return count
