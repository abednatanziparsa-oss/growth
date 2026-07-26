"""Composition root — build a runnable ``App`` from settings.

``build_app`` is what presentation-layer code (CLI today, desktop later)
calls to obtain a fully-wired application object. It:

1. Loads ``Settings`` from environment / .env.
2. Configures logging (structlog + file handler).
3. Constructs the DI ``Container``.
4. Wraps the container + planning repositories + use cases in an ``App``.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from growth.application.plan_applier import PlanApplier
from growth.infrastructure.config.settings import Settings
from growth.infrastructure.logging.setup import configure_logging
from growth.infrastructure.storage.planning_repos import (
    GoalRepository,
    MilestoneRepository,
    ProjectRepository,
    TaskRepository,
    WorkspaceRepository,
    init_db,
)
from growth.kernel.container import Container

__all__ = ["App", "build_app"]


@dataclass(slots=True)
class App:
    """Runnable application facade: settings + wired container + repositories."""

    settings: Settings
    container: Container
    workspace_repo: WorkspaceRepository
    project_repo: ProjectRepository
    goal_repo: GoalRepository
    milestone_repo: MilestoneRepository
    task_repo: TaskRepository
    plan_applier: PlanApplier


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
    workspace_repo = WorkspaceRepository(db)
    project_repo = ProjectRepository(db)
    goal_repo = GoalRepository(db)
    milestone_repo = MilestoneRepository(db)
    task_repo = TaskRepository(db)

    plan_applier = PlanApplier(
        workspace_repo, project_repo, goal_repo, milestone_repo, task_repo
    )

    return App(
        settings=settings,
        container=container,
        workspace_repo=workspace_repo,
        project_repo=project_repo,
        goal_repo=goal_repo,
        milestone_repo=milestone_repo,
        task_repo=task_repo,
        plan_applier=plan_applier,
    )
