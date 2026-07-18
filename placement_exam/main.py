"""Command-line entry point for the Placement Exam Todoist synchronizer.

Usage::

    # Preview what would be created (no network calls):
    python -m placement_exam.main --dry-run

    # Push to Todoist for real:
    python -m placement_exam.main

    # Use a different study plan file:
    python -m placement_exam.main --config path/to/plan.yaml

    # Create only the project + sections (no tasks):
    python -m placement_exam.main --structure-only

The TODOIST_API_TOKEN environment variable (or a ``.env`` file) must be set
unless ``--dry-run`` is used.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is in requirements.txt
    load_dotenv = None  # type: ignore[assignment]

from .dry_run import DryRunClient
from .models import StudyPlan
from .plan_loader import PlanError, load_plan
from .todoist_client import TodoistClient, TodoistError

DEFAULT_CONFIG = "config/placement_exam.yaml"
DEFAULT_CSV_OUTPUT = "placement_exam_plan.csv"


def build_plan(client: object, plan: StudyPlan, structure_only: bool = False) -> None:
    """Drive the chosen client to materialize ``plan``.

    This function is client-agnostic: it works identically against the real
    :class:`TodoistClient` and the :class:`DryRunClient`, because both expose
    ``add_project`` / ``add_section`` / ``add_task``.

    Args:
        client: A real or dry-run client.
        plan: The validated study plan.
        structure_only: When True, only create the project and sections
            (skip chapters and subtasks).
    """

    project = client.add_project(plan.project_name)

    for subject in plan.subjects:
        section = client.add_section(subject.section_name, project.id)

        if structure_only:
            continue

        for chapter in subject.chapters:
            priority = 4 if chapter.weak else subject.priority
            parent = client.add_task(
                content=_chapter_label(chapter.name, chapter.weak),
                project_id=project.id,
                section_id=section.id,
                priority=priority,
            )
            for sub_name in plan.standard_subtasks:
                client.add_task(
                    content=sub_name,
                    project_id=project.id,
                    parent_id=parent.id,
                    priority=priority,
                )

    for extra_name in plan.extra_sections:
        client.add_section(extra_name, project.id)


def _chapter_label(name: str, weak: bool) -> str:
    """Add a small marker to weak chapters so they're visible in Todoist."""

    return f"⚠ {name}" if weak else name


# ---------------------------------------------------------------------------
# CSV backup export
# ---------------------------------------------------------------------------

def export_csv(plan: StudyPlan, output_path: str | Path) -> Path:
    """Write the plan as a Todoist-importable CSV template.

    The CSV uses Todoist's documented import columns (TYPE, CONTENT, PRIORITY,
    INDENT, AUTHOR, RESPONSIBLE, DATE, DATE_LANG, TIMEZONE). We set INDENT so
    chapters are level 1 and their subtasks are level 2. Sections are emitted
    as ``section`` rows.

    This is a fallback for when the API isn't available.
    """

    path = Path(output_path)
    headers = [
        "TYPE",
        "CONTENT",
        "DESCRIPTION",
        "PRIORITY",
        "INDENT",
        "AUTHOR",
        "RESPONSIBLE",
        "DATE",
        "DATE_LANG",
        "TIMEZONE",
        "LABELS",
    ]

    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)

        for subject in plan.subjects:
            writer.writerow(["section", subject.section_name, "", "", "", "", "", "", "", "", ""])
            for chapter in subject.chapters:
                priority = _csv_priority(4 if chapter.weak else subject.priority)
                writer.writerow(
                    ["task", _chapter_label(chapter.name, chapter.weak), "",
                     priority, 1, "", "", "", "", "", ""]
                )
                for sub_name in plan.standard_subtasks:
                    writer.writerow(
                        ["task", sub_name, "", priority, 2, "", "", "", "", "", ""]
                    )

        for extra_name in plan.extra_sections:
            writer.writerow(["section", extra_name, "", "", "", "", "", "", "", "", ""])

    return path


def _csv_priority(todoist_priority: int) -> int:
    """Todoist CSV import expects 1..4 the same way as the API."""

    return todoist_priority


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="placement_exam",
        description="Build the 'Growth - Placement Exam' project in Todoist "
                    "from a YAML study plan.",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help=f"Path to the study plan YAML (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without calling the Todoist API.",
    )
    parser.add_argument(
        "--structure-only",
        action="store_true",
        help="Create only the project and sections, no chapter tasks.",
    )
    parser.add_argument(
        "--csv",
        nargs="?",
        const=DEFAULT_CSV_OUTPUT,
        default=None,
        help="Also export a Todoist-importable CSV. Optionally pass a path "
             f"(default output: {DEFAULT_CSV_OUTPUT})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Program entry point. Returns a process exit code."""

    args = _parse_args(argv)

    try:
        plan = load_plan(args.config)
    except PlanError as exc:
        print(f"❌ Invalid study plan: {exc}", file=sys.stderr)
        return 2

    # Always emit the CSV backup if requested — it needs no token.
    if args.csv:
        path = export_csv(plan, args.csv)
        print(f"📄 CSV backup written: {path}")

    if args.dry_run:
        print("=== DRY RUN (no changes will be made to Todoist) ===\n")
        client: object = DryRunClient()
        build_plan(client, plan, structure_only=args.structure_only)
        _print_dry_run_summary(client, plan)  # type: ignore[arg-type]
        return 0

    # Real execution path
    if load_dotenv is not None:
        load_dotenv()
    token = os.environ.get("TODOIST_API_TOKEN", "")
    try:
        client = TodoistClient(token)
    except TodoistError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    print(f"=== Creating '{plan.project_name}' in Todoist ===\n")
    try:
        build_plan(client, plan, structure_only=args.structure_only)
    except TodoistError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        print(
            "   Tip: re-run with --dry-run to preview, or fix the issue and "
            "retry. Partially created items may need manual cleanup in Todoist.",
            file=sys.stderr,
        )
        return 1

    _print_success_summary(plan, structure_only=args.structure_only)
    return 0


def _print_dry_run_summary(client: DryRunClient, plan: StudyPlan) -> None:
    print("\n=== DRY RUN SUMMARY ===")
    print(f"  Project:      {client.projects}")
    print(f"  Sections:     {client.sections}")
    print(f"  Parent tasks: {client.parent_tasks}")
    print(f"  Subtasks:     {client.subtasks}")
    print(f"  Chapters in plan: {plan.count_chapters()}")
    weak = [c.name for s in plan.subjects for c in s.chapters if c.weak]
    if weak:
        print(f"  Weak chapters (P1): {len(weak)} -> {', '.join(weak)}")


def _print_success_summary(plan: StudyPlan, *, structure_only: bool) -> None:
    print("\n✅ Done.")
    if structure_only:
        print(f"   Project + {len(plan.subjects) + len(plan.extra_sections)} "
              "sections created (no tasks).")
    else:
        print(
            f"   {plan.count_chapters()} chapter tasks + "
            f"{plan.count_subtasks()} subtasks created across "
            f"{len(plan.subjects)} subject sections."
        )


if __name__ == "__main__":
    raise SystemExit(main())
