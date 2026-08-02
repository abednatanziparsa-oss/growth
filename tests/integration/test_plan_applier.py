"""Integration tests for PlanApplier — the core YAML → tree pipeline.

These tests use real SQLite (in-memory) and exercise the full pipeline:
YAML → PlanApplier → Workspace → Project → Goals → Milestones → Tasks.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from growth.application.errors import ValidationError
from growth.application.plan_applier import PlanApplier
from growth.domain.shared import DEFAULT_SPACE_ID
from growth.infrastructure.storage.planning_repos import (
    GoalRepository,
    MilestoneRepository,
    ProjectRepository,
    TaskRepository,
    WorkspaceRepository,
    new_in_memory_db,
)


@pytest.fixture
def repos():
    """Return a fresh set of in-memory repositories wired to a clean SQLite DB."""
    db = new_in_memory_db()
    return {
        "workspace": WorkspaceRepository(db),
        "project": ProjectRepository(db),
        "goal": GoalRepository(db),
        "milestone": MilestoneRepository(db),
        "task": TaskRepository(db),
    }


@pytest.fixture
def plan_applier(repos):
    """Return a PlanApplier wired to fresh in-memory repos."""
    return PlanApplier(
        workspace_repo=repos["workspace"],
        project_repo=repos["project"],
        goal_repo=repos["goal"],
        milestone_repo=repos["milestone"],
        task_repo=repos["task"],
    )


def _write_yaml(content: str) -> Path:
    """Write YAML content to a temp file and return its Path."""
    with NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        return Path(f.name)


class TestPlanApplier:
    def test_apply_minimal_plan(self, plan_applier, repos) -> None:
        """A plan with project_name only should create Workspace + Project + default tasks."""
        yaml_path = _write_yaml("project_name: Minimal\nsubjects: []\n")
        workspace = plan_applier.apply(yaml_path)

        assert workspace.title == "Minimal Workspace"

        # Verify workspace persisted
        ws = repos["workspace"].get(workspace.id)
        assert ws.title == "Minimal Workspace"

        # Verify project created
        projects = repos["project"].list_by_workspace(workspace.id)
        assert len(projects) == 1
        assert projects[0].title == "Minimal"

    def test_apply_single_subject_creates_goal(self, plan_applier, repos) -> None:
        """One subject → one Goal."""
        yaml_path = _write_yaml(
            textwrap.dedent("""\
                project_name: "Test"
                subjects:
                  - name: "Python"
                    priority: high
                    emoji: "🐍"
                    chapters: []
                standard_subtasks: []
            """)
        )
        workspace = plan_applier.apply(yaml_path)
        projects = repos["project"].list_by_workspace(workspace.id)
        goals = repos["goal"].list_by_project(projects[0].id)
        assert len(goals) == 1
        assert goals[0].title == "🐍 Python"

    def test_apply_subject_chapter_creates_milestone(self, plan_applier, repos) -> None:
        """One chapter → one Milestone."""
        yaml_path = _write_yaml(
            textwrap.dedent("""\
                project_name: "Test"
                subjects:
                  - name: "Math"
                    chapters:
                      - name: "Algebra"
                standard_subtasks: []
            """)
        )
        workspace = plan_applier.apply(yaml_path)
        projects = repos["project"].list_by_workspace(workspace.id)
        goals = repos["goal"].list_by_project(projects[0].id)
        assert len(goals) == 1
        milestones = repos["milestone"].list_by_goal(goals[0].id)
        assert len(milestones) == 1
        assert milestones[0].title == "Algebra"

    def test_apply_chapter_creates_parent_task_plus_subtasks(
        self, plan_applier, repos
    ) -> None:
        """Each chapter → 1 parent task + N subtasks (from standard_subtasks)."""
        yaml_path = _write_yaml(
            textwrap.dedent("""\
                project_name: "Test"
                subjects:
                  - name: "Physics"
                    chapters:
                      - name: "Mechanics"
                standard_subtasks:
                  - "Read"
                  - "Practice"
                  - "Review"
            """)
        )
        plan_applier.apply(yaml_path)

        tasks = repos["task"].list_top_level(DEFAULT_SPACE_ID)
        parent_tasks = [t for t in tasks if t.is_root]
        assert len(parent_tasks) == 1
        assert parent_tasks[0].title == "Mechanics"

        children = repos["task"].list_by_parent(parent_tasks[0].id)
        assert len(children) == 3
        assert {c.title for c in children} == {"Read", "Practice", "Review"}

    def test_apply_multiple_subjects(self, plan_applier, repos) -> None:
        """N subjects → N goals, each with its own milestones and tasks."""
        yaml_path = _write_yaml(
            textwrap.dedent("""\
                project_name: "Multi"
                subjects:
                  - name: "A"
                    chapters:
                      - name: "A1"
                  - name: "B"
                    chapters:
                      - name: "B1"
                      - name: "B2"
                standard_subtasks:
                  - "Study"
            """)
        )
        workspace = plan_applier.apply(yaml_path)
        projects = repos["project"].list_by_workspace(workspace.id)
        goals = repos["goal"].list_by_project(projects[0].id)

        assert len(goals) == 2
        goal_titles = {g.title for g in goals}
        assert goal_titles == {"A", "B"}

        # Subject B has 2 chapters
        b_goal = next(g for g in goals if g.title == "B")
        milestones = repos["milestone"].list_by_goal(b_goal.id)
        assert len(milestones) == 2

    def test_apply_extra_sections(self, plan_applier, repos) -> None:
        """Extra sections → additional goals without milestones/tasks."""
        yaml_path = _write_yaml(
            textwrap.dedent("""\
                project_name: "With Extras"
                subjects: []
                standard_subtasks: []
                extra_sections:
                  - "Review"
                  - "Archive"
            """)
        )
        workspace = plan_applier.apply(yaml_path)
        projects = repos["project"].list_by_workspace(workspace.id)
        goals = repos["goal"].list_by_project(projects[0].id)

        # Only extra sections, no subjects
        assert len(goals) == 2
        assert {g.title for g in goals} == {"Review", "Archive"}

    def test_apply_weak_chapter_gets_high_priority(self, plan_applier, repos) -> None:
        """Weak chapters → milestone with HIGH priority annotation."""
        yaml_path = _write_yaml(
            textwrap.dedent("""\
                project_name: "Priority Test"
                subjects:
                  - name: "Math"
                    priority: low
                    chapters:
                      - name: "Easy"
                      - name: "Hard"
                        weak: true
                standard_subtasks: []
            """)
        )
        workspace = plan_applier.apply(yaml_path)
        projects = repos["project"].list_by_workspace(workspace.id)
        goals = repos["goal"].list_by_project(projects[0].id)

        milestones = repos["milestone"].list_by_goal(goals[0].id)
        assert len(milestones) == 2

        weak_ms = next(m for m in milestones if m.title == "Hard")
        assert "(weak area)" in (weak_ms.raw_description or "")
        assert "high" in (weak_ms.raw_description or "")

    def test_apply_with_standard_subtask_count(self, plan_applier, repos) -> None:
        """Default subtasks are used when standard_subtasks is missing."""
        yaml_path = _write_yaml(
            textwrap.dedent("""\
                project_name: "Defaults"
                subjects:
                  - name: "Science"
                    chapters:
                      - name: "Biology"
            """)
        )
        plan_applier.apply(yaml_path)

        tasks = repos["task"].list_top_level(DEFAULT_SPACE_ID)
        parent_tasks = [t for t in tasks if t.is_root]
        assert len(parent_tasks) == 1
        children = repos["task"].list_by_parent(parent_tasks[0].id)
        # Default subtasks: Study Concepts, Textbook Exercises, Sample Questions,
        #                     Mistakes Analysis, Review
        assert len(children) == 5

    def test_apply_missing_project_name_defaults(self, plan_applier, repos) -> None:
        """Missing project_name → defaults to 'Growth Plan'."""
        yaml_path = _write_yaml("subjects: []\n")
        workspace = plan_applier.apply(yaml_path)
        assert workspace.title == "Growth Plan Workspace"

        projects = repos["project"].list_by_workspace(workspace.id)
        assert projects[0].title == "Growth Plan"

    def test_apply_invalid_yaml_raises_error(self, plan_applier) -> None:
        """Malformed YAML → ValidationError."""
        yaml_path = _write_yaml("{this: [is: broken}")
        with pytest.raises(ValidationError, match="Invalid YAML"):
            plan_applier.apply(yaml_path)

    def test_apply_non_mapping_yaml_raises_error(self, plan_applier) -> None:
        """YAML list at root → ValidationError."""
        yaml_path = _write_yaml("- item1\n- item2\n")
        with pytest.raises(ValidationError, match="YAML root must be a mapping"):
            plan_applier.apply(yaml_path)
