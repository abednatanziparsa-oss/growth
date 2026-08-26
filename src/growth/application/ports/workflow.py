"""Workflow Engine port — declarative, observable automation.

Workflows move items through the value stream
(Knowledge → Planning → Execution → Review → Improvement) via triggers.
The engine owns **no business logic**: steps are references to use
cases. This is the explicit rejection of "autonomous agents" — we want
visible, declarative, cancelable flows, not invisible automation.

Bootstrap provides a ``NoopWorkflowEngine`` that registers definitions
but never fires. The real engine lands in v0.7.

Design rules (to be enforced when the real engine lands):
- Workflows are data (declarative YAML), not buried code.
- Every run is logged, dry-runnable, cancelable.
- Steps call use cases — never raw domain or infrastructure.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

__all__ = ["TriggerType", "WorkflowDefinition", "WorkflowEngine", "WorkflowRunResult"]


#: Stable trigger-type identifiers.
TriggerType = str


@runtime_checkable
class WorkflowDefinition(Protocol):
    """A declarative workflow: a trigger + an ordered list of use-case steps.

    Definitions are data (typically loaded from YAML). Concrete shape
    lands in v0.7; bootstrap just declares the contract.
    """

    @property
    def name(self) -> str:  # pragma: no cover - protocol shape
        """Stable workflow identifier."""
        ...

    @property
    def trigger_type(self) -> TriggerType:  # pragma: no cover - protocol shape
        """One of: ``"time"``, ``"event"``, ``"external"``."""
        ...


@runtime_checkable
class WorkflowRunResult(Protocol):
    """Outcome of a single workflow run, for observability."""

    @property
    def workflow_name(self) -> str:  # pragma: no cover - protocol shape
        ...

    @property
    def succeeded(self) -> bool:  # pragma: no cover - protocol shape
        ...

    @property
    def steps_completed(self) -> int:  # pragma: no cover - protocol shape
        ...

    @property
    def errors(self) -> tuple[str, ...]:  # pragma: no cover - protocol shape
        """Step errors; empty on success (run stops at the first error)."""
        ...

    @property
    def note(self) -> str:  # pragma: no cover - protocol shape
        """Human-readable run note (e.g. cancellation reason)."""
        ...


@runtime_checkable
class WorkflowEngine(Protocol):
    """Runs declarative workflows in response to triggers.

    Implementations own scheduling, retry, dry-run, cancellation, and
    logging. The engine itself is free of business logic — it calls
    use cases referenced by workflow steps.
    """

    def register(self, definition: WorkflowDefinition) -> None:
        """Register a workflow definition for triggering."""
        ...

    def run(
        self,
        name: str,
        *,
        dry_run: bool = False,
        inputs: dict[str, Any] | None = None,
    ) -> WorkflowRunResult:
        """Run the named workflow.

        Args:
            name: Registered workflow name.
            dry_run: When ``True``, compute and log what would happen
                without side effects. Real runs must produce identical
                logs minus the mutations.
            inputs: Optional trigger payload.

        Returns:
            A ``WorkflowRunResult`` for observability.
        """
        ...
