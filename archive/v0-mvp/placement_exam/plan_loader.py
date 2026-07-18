"""Loading and validation of the YAML study plan.

The YAML schema (see ``config/placement_exam.yaml``)::

    project_name: "Growth - Placement Exam"
    subjects:
      - name: "Mathematics"
        emoji: "📘"
        priority: 4
        chapters:
          - name: "Sets"
            weak: true
    standard_subtasks: ["Study Concepts", ...]
    extra_sections: ["🔄 Mistake Fix", ...]
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import Chapter, StudyPlan, Subject


class PlanError(ValueError):
    """Raised when the study plan is missing required fields or invalid."""


# Valid Todoist priorities: 1 (Normal) .. 4 (Highest).
_VALID_PRIORITIES = {1, 2, 3, 4}


def load_plan(path: str | Path) -> StudyPlan:
    """Load a study plan from a YAML file and validate it.

    Args:
        path: Path to the YAML study plan file.

    Returns:
        A validated :class:`StudyPlan`.

    Raises:
        PlanError: If the file is missing, malformed, or fails validation.
    """

    file_path = Path(path)
    if not file_path.is_file():
        raise PlanError(f"Study plan file not found: {file_path}")

    try:
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PlanError(f"Invalid YAML in {file_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise PlanError("Top-level YAML must be a mapping (key/value object).")

    project_name = raw.get("project_name")
    if not isinstance(project_name, str) or not project_name.strip():
        raise PlanError("'project_name' is required and must be a non-empty string.")

    subjects = _parse_subjects(raw.get("subjects", []))
    if not subjects:
        raise PlanError("At least one subject is required in 'subjects'.")

    standard_subtasks = raw.get("standard_subtasks", [])
    if not isinstance(standard_subtasks, list) or not standard_subtasks:
        raise PlanError(
            "'standard_subtasks' is required and must be a non-empty list."
        )
    if not all(isinstance(s, str) and s.strip() for s in standard_subtasks):
        raise PlanError("Every item in 'standard_subtasks' must be a non-empty string.")

    extra_sections = raw.get("extra_sections", [])
    if not isinstance(extra_sections, list):
        raise PlanError("'extra_sections' must be a list if provided.")
    if not all(isinstance(s, str) and s.strip() for s in extra_sections):
        raise PlanError("Every item in 'extra_sections' must be a non-empty string.")

    return StudyPlan(
        project_name=project_name.strip(),
        subjects=subjects,
        standard_subtasks=[s.strip() for s in standard_subtasks],
        extra_sections=[s.strip() for s in extra_sections],
    )


def _parse_subjects(raw_subjects: object) -> list[Subject]:
    """Parse and validate the ``subjects`` list from raw YAML data."""

    if not isinstance(raw_subjects, list):
        raise PlanError("'subjects' must be a list.")

    subjects: list[Subject] = []
    for index, raw in enumerate(raw_subjects):
        if not isinstance(raw, dict):
            raise PlanError(f"Subject #{index + 1} must be a mapping.")

        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise PlanError(f"Subject #{index + 1} is missing a valid 'name'.")

        emoji = raw.get("emoji", "")
        if not isinstance(emoji, str):
            raise PlanError(f"Subject '{name}' has a non-string 'emoji'.")

        priority = raw.get("priority", 1)
        if not isinstance(priority, int) or priority not in _VALID_PRIORITIES:
            raise PlanError(
                f"Subject '{name}' has invalid priority {priority!r}; "
                f"expected one of {sorted(_VALID_PRIORITIES)}."
            )

        chapters = _parse_chapters(raw.get("chapters", []), subject_name=name)

        subjects.append(
            Subject(
                name=name.strip(),
                emoji=emoji.strip(),
                priority=priority,
                chapters=chapters,
            )
        )

    return subjects


def _parse_chapters(raw_chapters: object, subject_name: str) -> list[Chapter]:
    """Parse and validate the ``chapters`` list for a single subject."""

    if not isinstance(raw_chapters, list):
        raise PlanError(f"Subject '{subject_name}': 'chapters' must be a list.")

    chapters: list[Chapter] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_chapters):
        if isinstance(raw, str):
            name = raw
            weak = False
        elif isinstance(raw, dict):
            name = raw.get("name")
            weak = bool(raw.get("weak", False))
        else:
            raise PlanError(
                f"Subject '{subject_name}', chapter #{index + 1} must be a "
                "string or mapping."
            )

        if not isinstance(name, str) or not name.strip():
            raise PlanError(
                f"Subject '{subject_name}', chapter #{index + 1} is missing "
                "a valid 'name'."
            )

        clean = name.strip()
        if clean.lower() in seen:
            raise PlanError(
                f"Subject '{subject_name}' has a duplicate chapter: '{clean}'."
            )
        seen.add(clean.lower())

        chapters.append(Chapter(name=clean, weak=weak))

    return chapters
