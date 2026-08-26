"""Declarative Workflow Engine — observable, cancelable automation.

v0.7 real implementation of the ``WorkflowEngine`` port. Workflows are
data (a trigger + an ordered list of use-case steps); the engine owns
scheduling, dry-run, cancellation, and logging — zero business logic.
Steps are callables that wrap use cases (see the port docstring: steps
call use cases, never raw domain or infrastructure).

Design rules (from the port):
- Workflows are data, not buried code.
- Every run is logged (see ``runs``) and dry-runnable.
- Cancellation is cooperative: ``cancel()`` sets a flag checked before
  each step; ``reset()`` clears it.
- A failing step stops the run and records the error (failure isolation
  per step, deterministic ordering).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from growth.application.ports.workflow import (
    TriggerType,
    WorkflowDefinition,
    WorkflowRunResult,
)

__all__ = [
    "DeclarativeWorkflow",
    "DeclarativeWorkflowEngine",
    "WorkflowRunOutcome",
    "WorkflowStep",
]


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    """One step in a workflow: a named callable wrapping a use case.

    ``fn`` receives the run's inputs dict and may return a value that
    later steps ignore (steps communicate via shared inputs when needed).
    """

    name: str
    fn: Callable[[dict[str, Any]], Any]
    description: str | None = None


@dataclass(frozen=True, slots=True)
class DeclarativeWorkflow:
    """A declarative workflow: a trigger + ordered use-case steps."""

    name: str
    trigger_type: TriggerType
    steps: tuple[WorkflowStep, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkflowRunOutcome:
    """Outcome of a single workflow run, for observability."""

    workflow_name: str
    succeeded: bool
    steps_completed: int
    dry_run: bool = False
    errors: tuple[str, ...] = ()
    note: str = ""


class DeclarativeWorkflowEngine:
    """Runs registered declarative workflows.

    Lifecycle:
        - ``register(workflow)`` — make a workflow runnable.
        - ``run(name, dry_run=..., inputs=...)`` — run (or dry-run) it.
        - ``cancel()`` / ``reset()`` — cooperative cancellation.
        - ``runs`` — completed-run history, oldest first.
    """

    def __init__(self) -> None:
        self._definitions: dict[str, DeclarativeWorkflow] = {}
        self._cancelled = False
        self._runs: list[WorkflowRunOutcome] = []

    def register(self, definition: WorkflowDefinition) -> None:
        """Register a workflow definition for triggering."""
        workflow = cast(DeclarativeWorkflow, definition)
        self._definitions[workflow.name] = workflow

    def cancel(self) -> None:
        """Request cancellation; checked before each step of a run."""
        self._cancelled = True

    def reset(self) -> None:
        """Clear the cancellation flag."""
        self._cancelled = False

    @property
    def runs(self) -> tuple[WorkflowRunOutcome, ...]:
        """Completed-run history, oldest first."""
        return tuple(self._runs)

    def run(
        self,
        name: str,
        *,
        dry_run: bool = False,
        inputs: dict[str, Any] | None = None,
    ) -> WorkflowRunResult:
        """Run (or dry-run) the named workflow.

        Dry runs count every step as "would complete" but never invoke
        ``fn``, so they have no side effects.
        """
        definition = self._definitions.get(name)
        if definition is None:
            return self._record(
                WorkflowRunOutcome(
                    workflow_name=name,
                    succeeded=False,
                    steps_completed=0,
                    dry_run=dry_run,
                    note=f"Unknown workflow '{name}'.",
                )
            )

        payload = dict(inputs) if inputs is not None else {}
        completed = 0
        errors: list[str] = []
        note = ""
        for step in definition.steps:
            if self._cancelled:
                note = "Cancelled before completion."
                break
            if dry_run:
                completed += 1
                continue
            try:
                step.fn(payload)
            except Exception as exc:  # step failure isolation
                errors.append(f"{step.name}: {exc}")
                note = f"Stopped at step '{step.name}'."
                break
            completed += 1

        succeeded = not errors and completed == len(definition.steps)
        return self._record(
            WorkflowRunOutcome(
                workflow_name=name,
                succeeded=succeeded,
                steps_completed=completed,
                dry_run=dry_run,
                errors=tuple(errors),
                note=note,
            )
        )

    def _record(self, outcome: WorkflowRunOutcome) -> WorkflowRunOutcome:
        self._runs.append(outcome)
        return outcome
