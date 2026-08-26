"""Declarative workflow YAML loader (v0.7).

Parses a workflow YAML document into a runnable ``DeclarativeWorkflow``.
Steps are referenced by name and resolved against a registry of
use-case callables — the loader and the engine stay free of business
logic. Invalid documents raise ``WorkflowParseError`` with a
human-readable message.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import yaml

from growth.infrastructure.workflow.engine import (
    DeclarativeWorkflow,
    WorkflowStep,
)

__all__ = ["WorkflowParseError", "parse_workflow_yaml"]


class WorkflowParseError(ValueError):
    """Raised when a workflow YAML document is invalid."""


def parse_workflow_yaml(
    text: str,
    step_registry: Mapping[str, Callable[[dict[str, Any]], Any]],
) -> DeclarativeWorkflow:
    """Parse and validate a declarative workflow YAML document.

    Expected shape::

        name: daily-review
        trigger: time
        steps:
          - next-action
          - blockers

    ``steps`` entries are step names; each must exist in
    ``step_registry`` (name → use-case callable). ``steps`` may be
    omitted (an empty workflow).
    """
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise WorkflowParseError(f"Invalid YAML: {exc}") from exc

    if not isinstance(doc, dict):
        raise WorkflowParseError("Workflow YAML must be a mapping.")

    name = doc.get("name")
    if not isinstance(name, str) or not name.strip():
        raise WorkflowParseError("Workflow YAML requires a non-empty string 'name'.")
    name = name.strip()
    if "/" in name or "\\" in name or name in {".", ".."}:
        raise WorkflowParseError(f"Workflow name {name!r} is not a safe filename.")

    trigger = doc.get("trigger")
    if not isinstance(trigger, str) or not trigger.strip():
        raise WorkflowParseError(
            f"Workflow '{name}' requires a non-empty string 'trigger'."
        )
    trigger = trigger.strip()

    raw_steps = doc.get("steps", [])
    if not isinstance(raw_steps, list):
        raise WorkflowParseError(f"Workflow '{name}' 'steps' must be a list.")

    steps: list[WorkflowStep] = []
    for item in raw_steps:
        if not isinstance(item, str) or not item.strip():
            raise WorkflowParseError(
                f"Workflow '{name}' step entries must be non-empty "
                f"strings, got {item!r}."
            )
        fn = step_registry.get(item)
        if fn is None:
            raise WorkflowParseError(
                f"Workflow '{name}' references unknown step '{item}'."
            )
        steps.append(WorkflowStep(name=item, fn=fn))

    return DeclarativeWorkflow(
        name=name,
        trigger_type=trigger,
        steps=tuple(steps),
    )
