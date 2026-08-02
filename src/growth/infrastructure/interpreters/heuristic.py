"""Heuristic interpreter — lifts a RawPlan into a CanonicalPlan.

Rules-based, deterministic, offline. Supports the MVP YAML schema
(subjects → chapters → subtasks) but expressed in canonical domain terms.
"""

from __future__ import annotations

from datetime import UTC, datetime

from growth.application.dtos import CanonicalPlan, RawPlan
from growth.application.ports.interpreter import InterpretationError
from growth.domain.shared import DEFAULT_SPACE_ID, SpaceId

__all__ = ["HeuristicInterpreter"]


class HeuristicInterpreter:
    """Lift a YAML-derived RawPlan into a CanonicalPlan using deterministic rules.

    Recognises the MVP schema:
    - ``project_name`` → plan identity
    - ``subjects`` → top-level categories with emoji, priority, chapters
    - ``standard_subtasks`` → template subtasks repeated under each chapter
    - ``extra_sections`` → additional sections without chapter content
    """

    def interpret(
        self,
        raw: RawPlan,
        *,
        space_id: SpaceId | None = None,
    ) -> CanonicalPlan:
        payload = raw.payload
        space = space_id or DEFAULT_SPACE_ID

        project_name = payload.get("project_name", "Untitled Plan")
        if not isinstance(project_name, str) or not project_name.strip():
            raise InterpretationError(
                "RawPlan is missing a valid 'project_name' field"
            )

        return CanonicalPlan(
            space_id=space,
            created_at=datetime.now(UTC),
            project_name=project_name,
            raw_payload=payload,
        )
