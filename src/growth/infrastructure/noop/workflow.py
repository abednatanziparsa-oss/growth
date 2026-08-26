"""Noop Workflow Engine — registers definitions but never fires.

Workflow definitions may still be registered (so callers don't need to
branch on engine presence), but ``run`` always returns a not-run result
explaining that the workflow engine is disabled. The real engine lands
in v0.7.
"""

from __future__ import annotations

from dataclasses import dataclass

from growth.application.ports.workflow import (
    WorkflowDefinition,
    WorkflowRunResult,
)

__all__ = ["NoopWorkflowEngine", "NoopWorkflowRunResult"]


@dataclass(frozen=True, slots=True)
class NoopWorkflowRunResult:
    """Result returned by the Noop engine for any ``run`` call."""

    workflow_name: str
    succeeded: bool = False
    steps_completed: int = 0
    errors: tuple[str, ...] = ()
    note: str = "Workflow engine disabled; no steps executed."


class NoopWorkflowEngine:
    """Workflow Engine that registers but never executes workflows."""

    def __init__(self) -> None:
        self._definitions: dict[str, WorkflowDefinition] = {}

    def register(self, definition: WorkflowDefinition) -> None:
        """Record the definition; never used to fire."""

        self._definitions[definition.name] = definition

    def run(
        self,
        name: str,
        *,
        dry_run: bool = False,
        inputs: dict[str, object] | None = None,
    ) -> WorkflowRunResult:
        """Return a not-run result regardless of inputs."""

        return NoopWorkflowRunResult(workflow_name=name)
