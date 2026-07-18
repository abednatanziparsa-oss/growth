"""Domain models for the Placement Exam study plan.

These dataclasses are the single representation of a study plan used
throughout the tool. The YAML loader produces them, the Dry-Run printer
consumes them, and the Todoist client reads them to create tasks.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Chapter:
    """A single chapter (becomes one parent task in Todoist)."""

    name: str
    weak: bool = False


@dataclass(frozen=True)
class Subject:
    """A school subject (becomes one Todoist section)."""

    name: str
    emoji: str
    priority: int
    chapters: list[Chapter] = field(default_factory=list)

    @property
    def section_name(self) -> str:
        """The Todoist section name, with emoji prefix and a separator space."""

        return f"{self.emoji} {self.name}"


@dataclass(frozen=True)
class StudyPlan:
    """The full study plan loaded from YAML.

    Attributes:
        project_name: Name of the Todoist project to create.
        subjects: Ordered list of subjects (each becomes a section).
        standard_subtasks: Subtask names attached to every chapter.
        extra_sections: Additional empty sections (e.g. "Final Review").
    """

    project_name: str
    subjects: list[Subject]
    standard_subtasks: list[str]
    extra_sections: list[str] = field(default_factory=list)

    def count_chapters(self) -> int:
        """Total number of chapters across all subjects."""

        return sum(len(s.chapters) for s in self.subjects)

    def count_subtasks(self) -> int:
        """Total number of subtasks that will be created."""

        return self.count_chapters() * len(self.standard_subtasks)
