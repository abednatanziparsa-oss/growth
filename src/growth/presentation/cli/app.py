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

import contextlib
import sys
from pathlib import Path
from typing import Annotated

import typer

from growth import __version__
from growth.application.dtos import CanonicalPlan
from growth.domain.shared import DEFAULT_SPACE_ID
from growth.kernel.bootstrap import App, build_app

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
        typer.echo(f"\n[Workspace] {ws.title}")
        for p in app_ctx.project_repo.list_by_workspace(ws.id):
            typer.echo(f"  [Project] {p.title}")
            for g in app_ctx.goal_repo.list_by_project(p.id):
                icon = "[done]" if g.is_completed else "[open]"
                typer.echo(
                    f"    {icon} {g.title} ({g.priority.value if g.priority else 'no priority'})"
                )
                for m in app_ctx.milestone_repo.list_by_goal(g.id):
                    m_icon = "[x]" if m.is_completed else "[ ]"
                    typer.echo(f"      {m_icon} {m.title}")

    tasks = app_ctx.task_repo.list_top_level(DEFAULT_SPACE_ID)
    if tasks:
        typer.echo(f"\n  [Tasks] ({len(tasks)} top-level):")
        for t in tasks[:10]:
            icon = "[x]" if t.is_completed else "[ ]"
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

reminder_app = typer.Typer(help="Reminder management commands.")
app.add_typer(reminder_app, name="reminder")

calendar_app = typer.Typer(help="Google Calendar commands.")
app.add_typer(calendar_app, name="calendar")


def _current_plan(app_ctx: App) -> CanonicalPlan | None:
    """Return the latest applied plan for the default space.

    Prefers the stored raw plan (faithful: subjects, emoji, weak flags,
    subtask templates). Falls back to reconstructing a minimal plan from
    the entity tree for databases created before the plan store existed.
    """
    from datetime import UTC, datetime

    store = getattr(app_ctx, "plan_store", None)
    if store is not None:
        stored = store.latest(DEFAULT_SPACE_ID)
        if stored is not None:
            return CanonicalPlan(
                space_id=stored.space_id,
                created_at=stored.created_at,
                project_name=stored.project_name,
                raw_payload=stored.raw_payload,
            )

    workspaces = app_ctx.workspace_repo.list_all()
    if not workspaces:
        return None
    ws = workspaces[0]
    projects = app_ctx.project_repo.list_by_workspace(ws.id)
    if not projects:
        return None
    project = projects[0]
    return CanonicalPlan(
        space_id=ws.space_id,
        created_at=datetime.now(UTC),
        project_name=project.title,
        raw_payload={
            "project_name": project.title,
            "subjects": [],
            "standard_subtasks": [],
        },
    )


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

    # Load the latest plan (stored raw plan, or legacy reconstruction)
    plan = _current_plan(app_ctx)
    if plan is None:
        typer.echo(
            "[ERROR] No plan found. Run 'growth plan apply <file>' first.",
            err=True,
        )
        raise typer.Exit(code=1)

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
    changeset = engine._differ.diff(engine._projection.project(plan), base)

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
            "-o",
            "--output",
            help="Output file path. Prints to stdout if omitted.",
        ),
    ] = None,
) -> None:
    """Export the current plan as a Markdown document."""
    app_ctx = build_app()

    plan = _current_plan(app_ctx)
    if plan is None:
        typer.echo(
            "[ERROR] No plan found. Run 'growth plan apply <file>' first.",
            err=True,
        )
        raise typer.Exit(code=1)

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
            "--task",
            "-t",
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
        typer.echo(
            f"  {a.id}  {a.title}  -> {a.target_type.value}:{target}  ({a.size_bytes or 0} B)"
        )


@knowledge_app.command(name="search")
def knowledge_search(
    query: Annotated[
        str,
        typer.Argument(help="Free-text search query."),
    ],
    semantic: Annotated[
        bool,
        typer.Option(
            "--semantic",
            help="Use embedding-based semantic search (typo-tolerant, ranked by similarity).",
        ),
    ] = False,
) -> None:
    """Search attachments by keyword or embedding similarity."""
    from growth.domain.shared import DEFAULT_SPACE_ID

    app_ctx = build_app()

    if semantic:
        engine = getattr(app_ctx, "semantic_search", None)
        if engine is None:
            typer.echo("[ERROR] Semantic search is not available.", err=True)
            raise typer.Exit(code=1)
    else:
        engine = app_ctx.knowledge_search

    hits = engine.search(query, space_id=DEFAULT_SPACE_ID)

    if not hits:
        typer.echo(f"No results for {query!r}.")
        return

    for hit in hits:
        a = hit.attachment
        typer.echo(f"  [{hit.score:.1f}] {a.title}  ({a.id})")
        if hit.snippet:
            typer.echo(f"        {hit.snippet}")


@reminder_app.command(name="add")
def reminder_add(
    title: Annotated[
        str,
        typer.Argument(help="Reminder title."),
    ],
    at: Annotated[
        str,
        typer.Option(
            "--at",
            help="Due time (ISO-8601, e.g. 2026-08-13 09:00). Naive times are UTC.",
        ),
    ],
    task: Annotated[
        str | None,
        typer.Option(
            "--task",
            help="Task id (UUID) this reminder is attached to.",
        ),
    ] = None,
    repeat: Annotated[
        str | None,
        typer.Option(
            "--repeat",
            help="Repeat this reminder: daily, weekly, or monthly.",
        ),
    ] = None,
    interval: Annotated[
        int,
        typer.Option(
            "--interval",
            help="Repeat every N units (with --repeat).",
        ),
    ] = 1,
    until: Annotated[
        str | None,
        typer.Option(
            "--until",
            help="Repeat until this time (ISO-8601).",
        ),
    ] = None,
    count: Annotated[
        int | None,
        typer.Option(
            "--count",
            help="Repeat at most N times total.",
        ),
    ] = None,
) -> None:
    """Create a reminder (optionally recurring)."""
    from datetime import UTC, datetime

    from growth.domain.reminders import (
        RecurrenceFrequency,
        RecurrenceRule,
        Reminder,
        ReminderTarget,
    )
    from growth.domain.shared import DEFAULT_SPACE_ID, InternalId

    try:
        due_at = datetime.fromisoformat(at)
    except ValueError:
        typer.echo(
            f"[ERROR] Invalid --at value {at!r}. Use ISO-8601, e.g. 2026-08-13 09:00.",
            err=True,
        )
        raise typer.Exit(code=1) from None
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)

    recurrence: RecurrenceRule | None = None
    if repeat is not None:
        try:
            freq = RecurrenceFrequency(repeat)
        except ValueError:
            typer.echo(
                f"[ERROR] Invalid --repeat {repeat!r}. Use daily, weekly, or monthly.",
                err=True,
            )
            raise typer.Exit(code=1) from None

        until_dt: datetime | None = None
        if until is not None:
            try:
                until_dt = datetime.fromisoformat(until)
            except ValueError:
                typer.echo(
                    f"[ERROR] Invalid --until value {until!r}. Use ISO-8601.",
                    err=True,
                )
                raise typer.Exit(code=1) from None
            if until_dt.tzinfo is None:
                until_dt = until_dt.replace(tzinfo=UTC)

        try:
            recurrence = RecurrenceRule(
                freq=freq, interval=interval, until=until_dt, count=count
            )
        except ValueError as exc:
            typer.echo(f"[ERROR] {exc}", err=True)
            raise typer.Exit(code=1) from exc
    elif interval != 1 or until is not None or count is not None:
        typer.echo(
            "[ERROR] --interval/--until/--count require --repeat.",
            err=True,
        )
        raise typer.Exit(code=1)

    app_ctx = build_app()
    repo = app_ctx.reminder_repo
    if repo is None:
        typer.echo("[ERROR] Reminders are not available.", err=True)
        raise typer.Exit(code=1)

    now = datetime.now(UTC)
    target_id = InternalId.from_string(task) if task else None
    reminder = Reminder(
        id=InternalId(),
        space_id=DEFAULT_SPACE_ID,
        title=title,
        due_at=due_at,
        target_type=ReminderTarget.TASK if target_id else ReminderTarget.SPACE,
        target_id=target_id,
        recurrence=recurrence,
        created_at=now,
        updated_at=now,
    )
    repo.save(reminder)
    label = f" (repeats {repeat} every {interval})" if recurrence else ""
    typer.echo(
        f"[OK] Reminder created (id={reminder.id}, due={due_at.isoformat()}{label})"
    )


@reminder_app.command(name="list")
def reminder_list() -> None:
    """List all reminders in the current space."""
    from growth.domain.shared import DEFAULT_SPACE_ID

    app_ctx = build_app()
    repo = app_ctx.reminder_repo
    if repo is None:
        typer.echo("[ERROR] Reminders are not available.", err=True)
        raise typer.Exit(code=1)

    reminders = repo.list_by_space(DEFAULT_SPACE_ID)
    if not reminders:
        typer.echo("No reminders yet. Run 'growth reminder add <title> --at <time>'.")
        return

    for r in reminders:
        target = r.target_id.value if r.target_id else "(space)"
        icon = {
            "pending": "[.]",
            "fired": "[x]",
            "dismissed": "[-]",
            "cancelled": "[!]",
        }[r.status.value]
        typer.echo(
            f"  {icon} {r.id}  {r.title}  @ {r.due_at.isoformat()}  "
            f"-> {r.target_type.value}:{target}  ({r.status.value})"
        )


@reminder_app.command(name="due")
def reminder_due() -> None:
    """List pending reminders whose due time has passed."""
    from datetime import UTC, datetime

    from growth.domain.shared import DEFAULT_SPACE_ID

    app_ctx = build_app()
    repo = app_ctx.reminder_repo
    if repo is None:
        typer.echo("[ERROR] Reminders are not available.", err=True)
        raise typer.Exit(code=1)

    due = repo.list_due(DEFAULT_SPACE_ID, datetime.now(UTC))
    if not due:
        typer.echo("No due reminders.")
        return

    for r in due:
        typer.echo(f"  [due] {r.id}  {r.title}  (due {r.due_at.isoformat()})")
    typer.echo(
        f"\n{len(due)} reminder(s) due — 'growth reminder fire <id>' to mark fired."
    )


@reminder_app.command(name="fire")
def reminder_fire(
    reminder_id: Annotated[
        str,
        typer.Argument(help="Reminder id (UUID)."),
    ],
) -> None:
    """Mark a reminder as fired."""
    from datetime import UTC, datetime

    from growth.application.ports.repository import EntityNotFoundError
    from growth.domain.reminders import ReminderStatus
    from growth.domain.shared import InternalId

    app_ctx = build_app()
    repo = app_ctx.reminder_repo
    if repo is None:
        typer.echo("[ERROR] Reminders are not available.", err=True)
        raise typer.Exit(code=1)

    try:
        reminder = repo.get(InternalId.from_string(reminder_id))
    except (ValueError, EntityNotFoundError) as exc:
        typer.echo(f"[ERROR] {exc}", err=True)
        raise typer.Exit(code=1) from exc

    reminder.status = ReminderStatus.FIRED
    reminder.updated_at = datetime.now(UTC)
    repo.save(reminder)
    typer.echo(f"[OK] Reminder fired: {reminder.title}")


@reminder_app.command(name="sweep")
def reminder_sweep() -> None:
    """Fire all due reminders (and re-arm recurring ones)."""
    from growth.domain.shared import DEFAULT_SPACE_ID

    app_ctx = build_app()
    scheduler = app_ctx.scheduler
    if scheduler is None:
        typer.echo("[ERROR] Scheduling is not available.", err=True)
        raise typer.Exit(code=1)

    result = scheduler.sweep(DEFAULT_SPACE_ID)
    if result.total == 0:
        typer.echo("No due reminders.")
        return

    for r in result.rescheduled:
        typer.echo(f"  [repeat] {r.title}  -> next {r.due_at.isoformat()}")
    for r in result.fired:
        typer.echo(f"  [fired] {r.title}")
    if result.errors:
        typer.echo(f"  [error] {result.errors} reminder(s) failed", err=True)
    typer.echo(
        f"[OK] Sweep done: {len(result.fired)} fired, "
        f"{len(result.rescheduled)} rescheduled"
    )


@calendar_app.command(name="auth")
def calendar_auth() -> None:
    """Authorize Google Calendar (OAuth) and store the token."""
    app_ctx = build_app()
    credentials = app_ctx.settings.google_credentials_path
    token = app_ctx.settings.google_token_path
    if credentials is None:
        typer.echo(
            "[ERROR] GROWTH_GOOGLE_CREDENTIALS_PATH is not set "
            "(point it at your credentials.json).",
            err=True,
        )
        raise typer.Exit(code=1)
    if token is None:
        typer.echo(
            "[ERROR] GROWTH_GOOGLE_TOKEN_PATH is not set "
            "(where should token.json be saved?).",
            err=True,
        )
        raise typer.Exit(code=1)
    typer.echo("Opening browser for Google authorization...")
    app_ctx.authorize_calendar()
    typer.echo(f"[OK] Token saved to {token}")


@calendar_app.command(name="push")
def calendar_push() -> None:
    """Push pending reminders to Google Calendar (idempotent)."""
    from growth.domain.shared import DEFAULT_SPACE_ID

    app_ctx = build_app()
    sync = app_ctx.calendar_sync
    if sync is None:
        typer.echo(
            "[ERROR] Google Calendar is not configured. "
            "Run `growth calendar auth` first.",
            err=True,
        )
        raise typer.Exit(code=1)

    result = sync.push(DEFAULT_SPACE_ID)
    for title in result.created:
        typer.echo(f"  [created] {title}")
    for title in result.updated:
        typer.echo(f"  [updated] {title}")
    if result.errors:
        typer.echo(f"  [error] {result.errors} reminder(s) failed", err=True)
    typer.echo(
        f"[OK] Push done: {len(result.created)} created, "
        f"{len(result.updated)} updated, {len(result.skipped)} skipped"
    )


@calendar_app.command(name="list")
def calendar_list(
    limit: int = typer.Option(10, "--limit", "-n", help="Max events to show."),
) -> None:
    """List upcoming events from Google Calendar (next 30 days)."""
    from datetime import UTC, datetime, timedelta

    app_ctx = build_app()
    adapter = app_ctx.calendar_adapter
    if adapter is None:
        typer.echo(
            "[ERROR] Google Calendar is not configured. "
            "Run `growth calendar auth` first.",
            err=True,
        )
        raise typer.Exit(code=1)

    now = datetime.now(UTC)
    events = adapter.list_events(
        time_min=now.isoformat(),
        time_max=(now + timedelta(days=30)).isoformat(),
    )
    if not events:
        typer.echo("No upcoming events.")
        return
    for event in events[:limit]:
        start = event.get("start", {})
        when = start.get("dateTime") or start.get("date") or "?"
        typer.echo(f"  {when}  {event.get('summary', '(no title)')}")


def _make_console_encoding_safe() -> None:
    """Degrade gracefully on legacy consoles (e.g. Windows cp1252).

    Plan titles and reminder text may legitimately contain emoji; a
    cp1252 console raises ``UnicodeEncodeError`` when printing them.
    Reconfiguring the streams with ``errors="replace"`` turns
    unencodable characters into ``?`` instead of crashing.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with contextlib.suppress(ValueError, OSError):
                reconfigure(errors="replace")


def run() -> None:
    """Console-script entry point."""
    _make_console_encoding_safe()
    app(standalone_mode=False)
    sys.exit(0)
