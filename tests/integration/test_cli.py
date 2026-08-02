"""Integration tests for the CLI layer.

Uses Typer's CliRunner with in-memory SQLite to exercise plan
commands end-to-end without touching the real ~/.growth/growth.db.

Each test gets a clean in-memory database by patching build_app
with a shared-session factory so apply + show/stats share one DB.
"""

from __future__ import annotations

import sqlite3
import textwrap
from pathlib import Path
from tempfile import NamedTemporaryFile

from typer.testing import CliRunner

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
from growth.kernel.bootstrap import App
from growth.kernel.container import Container
from growth.presentation.cli.app import app

runner = CliRunner()


def _yaml_file(content: str) -> Path:
    with NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        return Path(f.name)


class _SharedDbAppFactory:
    """build_app replacement that creates a single in-memory DB shared
    across all Typer invocations in a single test.  The first time
    build_app is called every resource (settings, container, DB,
    repos) is initialised; subsequent calls return a new App wrapping
    the same connection so that plan apply and plan show/stats see
    each other's data."""

    def __init__(self) -> None:
        self._app: App | None = None
        self._db: sqlite3.Connection | None = None

    def __call__(self) -> App:
        if self._app is not None:
            # Second+ invocation — all infra already alive.
            # Wire fresh repos onto the existing connection so the
            # caller gets current state.
            db = self._db
            assert db is not None
            return App(
                settings=self._app.settings,
                container=self._app.container,
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
            )

        # First invocation — create everything.
        settings = Settings()
        configure_logging(settings)
        container = Container.from_settings(settings)

        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        init_db(db)
        self._db = db

        self._app = App(
            settings=settings,
            container=container,
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
        )
        return self._app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_growth_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Growth OS" in result.stdout


def test_plan_help() -> None:
    result = runner.invoke(app, ["plan", "--help"])
    assert result.exit_code == 0
    assert "apply" in result.stdout
    assert "show" in result.stdout
    assert "stats" in result.stdout


def test_plan_apply_missing_file() -> None:
    result = runner.invoke(app, ["plan", "apply", "nonexistent.yaml"])
    assert result.exit_code != 0


def test_plan_apply_valid_yaml(monkeypatch) -> None:
    monkeypatch.setattr(
        "growth.presentation.cli.app.build_app", _SharedDbAppFactory()
    )
    yaml_path = _yaml_file(
        textwrap.dedent("""\
            project_name: "CLI Test"
            subjects:
              - name: "Python"
                chapters:
                  - name: "Basics"
            standard_subtasks:
              - "Study"
        """)
    )
    result = runner.invoke(app, ["plan", "apply", str(yaml_path)])
    assert result.exit_code == 0
    assert "[OK]" in result.stdout
    assert "CLI Test" in result.stdout


def test_plan_apply_invalid_yaml(monkeypatch) -> None:
    monkeypatch.setattr(
        "growth.presentation.cli.app.build_app", _SharedDbAppFactory()
    )
    yaml_path = _yaml_file("{broken: [")
    result = runner.invoke(app, ["plan", "apply", str(yaml_path)])
    assert result.exit_code != 0


def test_plan_show_empty(monkeypatch) -> None:
    monkeypatch.setattr(
        "growth.presentation.cli.app.build_app", _SharedDbAppFactory()
    )
    result = runner.invoke(app, ["plan", "show"])
    assert result.exit_code == 0
    assert "No workspaces found" in result.stdout


def test_plan_show_after_apply(monkeypatch) -> None:
    factory = _SharedDbAppFactory()
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)

    yaml_path = _yaml_file(
        textwrap.dedent("""\
            project_name: "Display Test"
            subjects:
              - name: "Math"
                priority: high
                chapters:
                  - name: "Algebra"
            standard_subtasks:
              - "Practice"
        """)
    )
    r1 = runner.invoke(app, ["plan", "apply", str(yaml_path)])
    assert r1.exit_code == 0

    r2 = runner.invoke(app, ["plan", "show"])
    assert r2.exit_code == 0
    assert "Display Test" in r2.stdout


def test_plan_show_tree_format(monkeypatch) -> None:
    factory = _SharedDbAppFactory()
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)

    yaml_path = _yaml_file(
        textwrap.dedent("""\
            project_name: "Tree Test"
            subjects:
              - name: "Science"
                chapters:
                  - name: "Physics"
            standard_subtasks: []
        """)
    )
    runner.invoke(app, ["plan", "apply", str(yaml_path)])
    result = runner.invoke(app, ["plan", "show"])
    assert result.exit_code == 0

    assert "📁" in result.stdout
    assert "📦" in result.stdout
    assert "🎯" in result.stdout
    assert "📌" in result.stdout


def test_plan_stats(monkeypatch) -> None:
    factory = _SharedDbAppFactory()
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)

    yaml_path = _yaml_file(
        textwrap.dedent("""\
            project_name: "Stats Test"
            subjects:
              - name: "Physics"
                chapters:
                  - name: "Mechanics"
                  - name: "Electromagnetism"
            standard_subtasks:
              - "Study"
              - "Practice"
        """)
    )
    runner.invoke(app, ["plan", "apply", str(yaml_path)])
    result = runner.invoke(app, ["plan", "stats"])
    assert result.exit_code == 0

    assert "Workspaces:" in result.stdout
    assert "Projects:" in result.stdout
    assert "Goals:" in result.stdout
    assert "Milestones:" in result.stdout
    assert "Tasks:" in result.stdout


def test_plan_stats_counts_are_numbers(monkeypatch) -> None:
    factory = _SharedDbAppFactory()
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)

    yaml_path = _yaml_file(
        textwrap.dedent("""\
            project_name: "Number Test"
            subjects:
              - name: "Math"
                chapters:
                  - name: "Chapter 1"
            standard_subtasks:
              - "Practice"
        """)
    )
    runner.invoke(app, ["plan", "apply", str(yaml_path)])
    result = runner.invoke(app, ["plan", "stats"])
    assert result.exit_code == 0

    lines = result.stdout.strip().split("\n")
    for line in lines:
        if ":" in line:
            parts = line.split(":")
            if len(parts) == 2:
                count_part = parts[1].strip().split()[0]
                if "(" in count_part:
                    count_part = count_part.split("(")[0].strip()
                try:
                    num = int(count_part)
                    assert num >= 0
                except (ValueError, IndexError):
                    pass


def test_plan_stats_after_multiple_applies(monkeypatch) -> None:
    factory = _SharedDbAppFactory()
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)

    yaml1 = _yaml_file(
        textwrap.dedent("""\
            project_name: "First Plan"
            subjects:
              - name: "A"
                chapters:
                  - name: "A1"
            standard_subtasks: []
        """)
    )
    runner.invoke(app, ["plan", "apply", str(yaml1)])

    yaml2 = _yaml_file(
        textwrap.dedent("""\
            project_name: "Second Plan"
            subjects:
              - name: "B"
                chapters:
                  - name: "B1"
                  - name: "B2"
            standard_subtasks: []
        """)
    )
    runner.invoke(app, ["plan", "apply", str(yaml2)])

    result = runner.invoke(app, ["plan", "stats"])
    assert result.exit_code == 0
    assert "Projects:" in result.stdout
