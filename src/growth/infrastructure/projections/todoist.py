"""Todoist projection — maps canonical plans into Todoist-shaped snapshots.

Converts the canonical priority vocabulary to Todoist p1-p4 and
structures tasks with sections (for subjects) and parent/child nesting.
"""

from __future__ import annotations

from typing import Any

from growth.application.dtos import CanonicalPlan, ProviderSnapshot

__all__ = ["TodoistProjection"]

_PRIORITY_MAP: dict[str, int] = {
    "urgent": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


class TodoistProjection:
    """Project a CanonicalPlan into a Todoist-shaped ProviderSnapshot."""

    @property
    def provider(self) -> str:
        return "todoist"

    def project(self, plan: CanonicalPlan) -> ProviderSnapshot:
        payload: dict[str, Any] = {
            "project_name": getattr(plan, "_project_name", "Growth Plan"),
            "sections": [],
            "items": [],
        }

        raw: dict[str, Any] = getattr(plan, "_raw_payload", {})
        if raw:
            payload["sections"] = self._build_sections(raw)
            payload["items"] = self._build_items(raw)

        return ProviderSnapshot(
            provider="todoist",
            root_id=None,
            payload=payload,
        )

    @staticmethod
    def _build_sections(raw: dict[str, Any]) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        for subject in raw.get("subjects", []):
            if not isinstance(subject, dict):
                continue
            emoji = subject.get("emoji", "")
            name = subject.get("name", "")
            sections.append({"name": f"{emoji} {name}".strip()})
        for extra in raw.get("extra_sections", []):
            sections.append({"name": str(extra)})
        return sections

    @staticmethod
    def _build_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        subtask_templates = raw.get("standard_subtasks", [])
        for subject in raw.get("subjects", []):
            if not isinstance(subject, dict):
                continue
            section_name = str(subject.get("name", ""))
            priority = _PRIORITY_MAP.get(str(subject.get("priority", "")), 1)
            chapters = subject.get("chapters", [])
            if not isinstance(chapters, list):
                continue
            for chapter in chapters:
                if not isinstance(chapter, dict):
                    continue
                ch_priority = 4 if chapter.get("weak") else priority
                items.append(
                    {
                        "content": chapter.get("name", ""),
                        "section": section_name,
                        "priority": ch_priority,
                        "subtasks": list(subtask_templates)
                        if isinstance(subtask_templates, list)
                        else [],
                    }
                )
        return items
