"""Plan application use case — creates a full plan tree in storage.

Reads a YAML file, parses it, then creates Workspace, Project,
Goals (per subject), Milestones (per chapter), and Tasks.

PlanApplier receives repositories as dependency injection (they implement
the Repository[T] port). It never imports infrastructure types — the
composition root wires concrete implementations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from growth.application.errors import ValidationError
from growth.domain.planning import (
    Goal,
    Milestone,
    Priority,
    Project,
    Task,
    Workspace,
)
from growth.domain.shared import DEFAULT_SPACE_ID, SpaceId

__all__ = ["PlanApplier"]

_YAML_PRIORITY: dict[str, Priority] = {
    "urgent": Priority.URGENT,
    "high": Priority.HIGH,
    "medium": Priority.MEDIUM,
    "low": Priority.LOW,
}


class PlanApplier:
    """Orchestrate creating a full plan tree from YAML input.

    All dependencies are injected by the composition root. PlanApplier
    depends only on domain types — never on infrastructure.
    """

    def __init__(
        self,
        workspace_repo: Any,
        project_repo: Any,
        goal_repo: Any,
        milestone_repo: Any,
        task_repo: Any,
        plan_store: Any | None = None,
    ) -> None:
        self._workspace_repo = workspace_repo
        self._project_repo = project_repo
        self._goal_repo = goal_repo
        self._milestone_repo = milestone_repo
        self._task_repo = task_repo
        self._plan_store = plan_store

    def apply(self, source_path: Path, space_id: SpaceId | None = None) -> Workspace:
        space = space_id or DEFAULT_SPACE_ID
        now = datetime.now(UTC)

        raw_text = source_path.read_text(encoding="utf-8")
        try:
            payload = yaml.safe_load(raw_text)
        except yaml.YAMLError as exc:
            raise ValidationError(f"Invalid YAML: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValidationError("YAML root must be a mapping")

        ws_name = payload.get("project_name", "Growth Plan")
        workspace = Workspace(
            title=f"{ws_name} Workspace",
            space_id=space,
            created_at=now,
            updated_at=now,
        )
        self._workspace_repo.save(workspace)

        project = Project(
            title=ws_name,
            workspace_id=workspace.id,
            space_id=space,
            created_at=now,
            updated_at=now,
        )
        self._project_repo.save(project)

        subtask_templates = payload.get(
            "standard_subtasks",
            [
                "Study Concepts",
                "Textbook Exercises",
                "Sample Questions",
                "Mistakes Analysis",
                "Review",
            ],
        )

        for subject in payload.get("subjects", []):
            subj_name = subject.get("name", "Unnamed")
            subj_priority = _YAML_PRIORITY.get(
                subject.get("priority", ""), Priority.MEDIUM
            )

            goal = Goal(
                title=f"{subject.get('emoji', '')} {subj_name}".strip(),
                project_id=project.id,
                space_id=space,
                description=f"Complete all chapters in {subj_name}",
                priority=subj_priority,
                created_at=now,
                updated_at=now,
            )
            self._goal_repo.save(goal)

            for i, chapter in enumerate(subject.get("chapters", [])):
                ch_name = chapter.get("name", f"Chapter {i + 1}")
                ch_priority = Priority.HIGH if chapter.get("weak") else subj_priority

                milestone = Milestone(
                    title=ch_name,
                    goal_id=goal.id,
                    space_id=space,
                    order=i,
                    raw_description=f"Priority: {ch_priority.value}"
                    + (" (weak area)" if chapter.get("weak") else ""),
                    created_at=now,
                    updated_at=now,
                )
                self._milestone_repo.save(milestone)

                parent_task = Task(
                    title=ch_name,
                    space_id=space,
                    priority=ch_priority,
                    source_ref=str(source_path),
                    created_at=now,
                    updated_at=now,
                )
                self._task_repo.save(parent_task)

                for sub_name in subtask_templates:
                    subtask = Task(
                        title=sub_name,
                        space_id=space,
                        parent_id=parent_task.id,
                        source_ref=str(source_path),
                        created_at=now,
                        updated_at=now,
                    )
                    self._task_repo.save(subtask)

        for extra in payload.get("extra_sections", []):
            goal = Goal(
                title=extra,
                project_id=project.id,
                space_id=space,
                created_at=now,
                updated_at=now,
            )
            self._goal_repo.save(goal)

        # Persist the raw plan so export/sync can reconstruct the
        # CanonicalPlan faithfully (entities lose emoji/weak/templates).
        if self._plan_store is not None:
            self._plan_store.save(space, ws_name, payload, now)

        return workspace
