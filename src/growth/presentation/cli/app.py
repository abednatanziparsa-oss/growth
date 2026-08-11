"""Growth OS command-line interface.

Thin presentation layer: translates user intent into use-case calls.
No business logic here.

Commands:
- ``growth --version``   show version
- ``growth plan apply``  apply a YAML study plan to the database
- ``growth plan show``   show the current plan tree
- ``growth plan stats``  show task/milestone/goal counts
- ``growth sync``        synchronize plan with Todoist (dry-run by default)
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


sync_app = typer.Typer(help="Synchronization commands.")
app.add_typer(sync_app, name="sync")

export_app = typer.Typer(help="Export commands.")
app.add_typer(export_app, name="export")

knowledge_app = typer.Typer(help="Knowledge management commands.")
app.add_typer(knowledge_app, name="knowledge")


@sync_app.command(name="todoist")
def sync_todoist(
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview the ChangeSet without applying it to Todoist.",
        ),
    ] = False,
) -> None:
    """Synchronize the current plan with Todoist.

    Reads the last-applied plan from the database, projects it into
    a Todoist-shaped snapshot, diffs against the last-synced state,
    and applies the resulting ChangeSet.

    Requires GROWTH_TODOIST_API_TOKEN (or TODOIST_API_TOKEN) to be set.
    """
    from datetime import UTC, datetime

    from growth.application.dtos import CanonicalPlan

    app_ctx = build_app()
    settings = app_ctx.settings
    api_token = settings.todoist_api_token

    if not api_token:
        typer.echo(
            "[ERROR] GROWTH_TODOIST_API_TOKEN is not set. "
            "Set it in your .env file or environment.",
            err=True,
        )
        raise typer.Exit(code=1)

    # Load the latest project / plan from the DB
    workspaces = app_ctx.workspace_repo.list_all()
    if not workspaces:
        typer.echo(
            "[ERROR] No plan found. Run 'growth plan apply <file>' first.",
            err=True,
        )
        raise typer.Exit(code=1)

    ws = workspaces[0]
    projects = app_ctx.project_repo.list_by_workspace(ws.id)
    if not projects:
        typer.echo(
            "[ERROR] No project found. Run 'growth plan apply <file>' first.",
            err=True,
        )
        raise typer.Exit(code=1)

    project = projects[0]

    # Build a CanonicalPlan from the stored project
    now = datetime.now(UTC)
    plan = CanonicalPlan(
        space_id=ws.space_id,
        created_at=now,
        project_name=project.title,
        raw_payload={
            "project_name": project.title,
            "subjects": [],
            "standard_subtasks": [],
        },
    )

    # Build sync pipeline via kernel-provided engine
    engine = app_ctx.sync_engine
    if engine is None:
        typer.echo(
            "[ERROR] No sync engine available — missing provider token.",
            err=True,
        )
        raise typer.Exit(code=1)

    # Project + diff — use the projection to generate the desired snapshot.
    # Access engine internals for dry-run visibility; real sync uses engine.sync().
    base = engine._load_base("todoist")
    changeset = engine._differ.diff(
        engine._projection.project(plan), base
    )

    typer.echo("Provider:   todoist")
    typer.echo(f"Project:    {plan.project_name}")
    typer.echo(f"Changeset:  {len(changeset.operations)} operation(s)")
    typer.echo()

    for i, op in enumerate(changeset.operations):
        action = op["op"]
        detail = op.get("content") or op.get("name") or ""
        typer.echo(f"  [{i + 1}] {action}: {detail}")

    if dry_run:
        typer.echo()
        typer.echo("[DRY-RUN] No changes applied to Todoist.")
        return

    # Apply
    typer.echo()
    typer.echo("Applying changes to Todoist...")

    try:
        result = engine.sync(plan)
    except Exception as exc:
        typer.echo(f"[ERROR] Sync failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    ar = result.apply_result
    typer.echo(f"[OK] Applied: {ar.applied}, Failed: {ar.failed}")
    if ar.errors:
        for e in ar.errors:
            typer.echo(f"  ! {e}", err=True)
    if ar.provider_ids:
        typer.echo(f"  Provider ids: {len(ar.provider_ids)} new mapping(s)")


@export_app.command(name="markdown")
def export_markdown(
    output: Annotated[
        Path | None,
        typer.Option(
            "-o", "--output",
            help="Output file path. Prints to stdout if omitted.",
        ),
    ] = None,
) -> None:
    """Export the current plan as a Markdown document."""
    from datetime import UTC, datetime

    from growth.application.dtos import CanonicalPlan

    app_ctx = build_app()

    workspaces = app_ctx.workspace_repo.list_all()
    if not workspaces:
        typer.echo(
            "[ERROR] No plan found. Run 'growth plan apply <file>' first.",
            err=True,
        )
        raise typer.Exit(code=1)

    ws = workspaces[0]
    projects = app_ctx.project_repo.list_by_workspace(ws.id)
    if not projects:
        typer.echo(
            "[ERROR] No project found. Run 'growth plan apply <file>' first.",
            err=True,
        )
        raise typer.Exit(code=1)

    project = projects[0]

    # Reconstruct canonical plan from stored entities
    now = datetime.now(UTC)
    plan = CanonicalPlan(
        space_id=ws.space_id,
        created_at=now,
        project_name=project.title,
        raw_payload={
            "project_name": project.title,
            "subjects": [],
            "standard_subtasks": [],
        },
    )

    content = app_ctx.export_markdown(plan)

    if output:
        output.write_text(content, encoding="utf-8")
        typer.echo(f"[OK] Exported to {output}")
    else:
        typer.echo(content)


@knowledge_app.command(name="attach")
def knowledge_attach(
    file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Path to the file to attach.",
        ),
    ],
    target: Annotated[
        str | None,
        typer.Option(
            "--task", "-t",
            help="Task id to attach to (UUID).",
        ),
    ] = None,
) -> None:
    """Attach a file to a task (content-addressed, dedup)."""
    from datetime import UTC, datetime

    from growth.domain.knowledge import (
        Attachment,
        AttachmentKind,
        AttachmentTarget,
        content_hash,
    )
    from growth.domain.shared import DEFAULT_SPACE_ID, InternalId

    app_ctx = build_app()

    data = file.read_bytes()
    h = content_hash(data)

    existing = app_ctx.attachment_repo.find_by_hash(h)
    if existing is not None:
        typer.echo(f"[OK] Already attached: {existing.title} (id={existing.id})")
        return

    now = datetime.now(UTC)
    attachment = Attachment(
        space_id=DEFAULT_SPACE_ID,
        kind=AttachmentKind.FILE,
        target_type=AttachmentTarget.TASK,
        target_id=InternalId.from_string(target) if target else None,
        title=file.name,
        content_hash=h,
        mime_type=None,
        source_ref=str(file.resolve()),
        size_bytes=len(data),
        created_at=now,
        updated_at=now,
    )
    app_ctx.attachment_repo.save(attachment)
    typer.echo(f"[OK] Attached {file.name} (id={attachment.id}, hash={h[:12]}…)")


@knowledge_app.command(name="list")
def knowledge_list() -> None:
    """List all attachments in the current space."""
    from growth.domain.shared import DEFAULT_SPACE_ID

    app_ctx = build_app()
    attachments = app_ctx.attachment_repo.list_by_space(DEFAULT_SPACE_ID)

    if not attachments:
        typer.echo("No attachments yet. Run 'growth knowledge attach <file>'.")
        return

    for a in attachments:
        target = a.target_id.value if a.target_id else "(space)"
        typer.echo(f"  {a.id}  {a.title}  -> {a.target_type.value}:{target}  ({a.size_bytes or 0} B)")


@knowledge_app.command(name="search")
def knowledge_search(
    query: Annotated[
        str,
        typer.Argument(help="Free-text search query."),
    ],
) -> None:
    """Search attachments by keyword (title + source path)."""
    from growth.domain.shared import DEFAULT_SPACE_ID

    app_ctx = build_app()
    hits = app_ctx.knowledge_search.search(query, space_id=DEFAULT_SPACE_ID)

    if not hits:
        typer.echo(f"No results for {query!r}.")
        return

    for hit in hits:
        a = hit.attachment
        typer.echo(f"  [{hit.score:.1f}] {a.title}  ({a.id})")
        if hit.snippet:
            typer.echo(f"        {hit.snippet}")


def run() -> None:
    """Console-script entry point."""
    app(standalone_mode=False)
    sys.exit(0)
