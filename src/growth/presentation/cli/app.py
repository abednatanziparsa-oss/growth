"""Growth OS command-line interface.

Thin presentation layer: translates user intent into use-case calls.
No business logic here.

Commands:
- ``growth --version``   show version
- ``growth plan apply``  apply a YAML study plan to the database
- ``growth plan show``   show the current plan tree
- ``growth plan stats``  show task/milestone/goal counts
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from growth import __version__
from growth.domain.shared import DEFAULT_SPACE_ID
from growth.kernel.bootstrap import build_app

__all__ = ["app", "run", "version_callback"]


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"growth-os {__version__}")
        raise typer.Exit(code=0)


app = typer.Typer(
    name="growth",
    help="Growth OS — a personal growth operating system.",
    no_args_is_help=True,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

plan_app = typer.Typer(help="Plan management commands.")
app.add_typer(plan_app, name="plan")


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=version_callback,
            is_eager=True,
            help="Show the installed version and exit.",
        ),
    ] = False,
) -> None:
    """Growth OS — a personal growth operating system."""


@plan_app.command(name="apply")
def plan_apply(
    source: Annotated[
        Path,
        typer.Argument(
            help="Path to a YAML study plan file.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
) -> None:
    """Apply a YAML study plan — parse, interpret, store."""
    app_ctx = build_app()
    ws = app_ctx.plan_applier.apply(source)

    projects = app_ctx.project_repo.list_by_workspace(ws.id)
    total_goals = 0
    total_milestones = 0
    for p in projects:
        goals = app_ctx.goal_repo.list_by_project(p.id)
        total_goals += len(goals)
        for g in goals:
            total_milestones += len(app_ctx.milestone_repo.list_by_goal(g.id))

    tasks = app_ctx.task_repo.list_top_level(DEFAULT_SPACE_ID)

    typer.echo(f"[OK] Applied: {ws.title}")
    typer.echo(f"   Projects: {len(projects)}")
    typer.echo(f"   Goals: {total_goals}")
    typer.echo(f"   Milestones: {total_milestones}")
    typer.echo(f"   Tasks: {len(tasks)}")


@plan_app.command(name="show")
def plan_show() -> None:
    """Display the current plan tree."""
    app_ctx = build_app()

    workspaces = app_ctx.workspace_repo.list_all()
    if not workspaces:
        typer.echo("No workspaces found. Run 'growth plan apply <file>' first.")
        return

    for ws in workspaces:
        typer.echo(f"\n📁 {ws.title}")
        for p in app_ctx.project_repo.list_by_workspace(ws.id):
            typer.echo(f"  📦 {p.title}")
            for g in app_ctx.goal_repo.list_by_project(p.id):
                icon = "✅" if g.is_completed else "🎯"
                typer.echo(
                    f"    {icon} {g.title} ({g.priority.value if g.priority else 'no priority'})"
                )
                for m in app_ctx.milestone_repo.list_by_goal(g.id):
                    m_icon = "✅" if m.is_completed else "📌"
                    typer.echo(f"      {m_icon} {m.title}")

    tasks = app_ctx.task_repo.list_top_level(DEFAULT_SPACE_ID)
    if tasks:
        typer.echo(f"\n  📋 Tasks ({len(tasks)} top-level):")
        for t in tasks[:10]:
            icon = "✅" if t.is_completed else "⬜"
            typer.echo(f"    {icon} {t.title}")


@plan_app.command(name="stats")
def plan_stats() -> None:
    """Show aggregate statistics about the current plan."""
    app_ctx = build_app()

    tasks = app_ctx.task_repo.list_top_level(DEFAULT_SPACE_ID)
    completed = sum(1 for t in tasks if t.is_completed)
    workspaces = app_ctx.workspace_repo.list_all()
    project_count = 0
    goal_count = 0
    milestone_count = 0
    for ws in workspaces:
        for p in app_ctx.project_repo.list_by_workspace(ws.id):
            project_count += 1
            goals = app_ctx.goal_repo.list_by_project(p.id)
            goal_count += len(goals)
            for g in goals:
                milestone_count += len(app_ctx.milestone_repo.list_by_goal(g.id))

    typer.echo(f"Workspaces:  {len(workspaces)}")
    typer.echo(f"Projects:    {project_count}")
    typer.echo(f"Goals:       {goal_count}")
    typer.echo(f"Milestones:  {milestone_count}")
    typer.echo(f"Tasks:       {len(tasks)} ({completed} completed)")


def run() -> None:
    """Console-script entry point."""
    app(standalone_mode=False)
    sys.exit(0)
