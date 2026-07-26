"""Dependency-injection container — manual wiring, no framework."""

from __future__ import annotations

from dataclasses import dataclass

from growth.application.ports.ai_services import AiServices
from growth.application.ports.clock import Clock
from growth.application.ports.decision import DecisionEngine
from growth.application.ports.event_dispatcher import EventDispatcher
from growth.application.ports.workflow import WorkflowEngine
from growth.infrastructure.config.settings import Settings
from growth.infrastructure.events.sync_dispatcher import SyncEventDispatcher
from growth.infrastructure.noop.ai import NoopAiServices
from growth.infrastructure.noop.clock import SystemClock
from growth.infrastructure.noop.decision import NoopDecisionEngine
from growth.infrastructure.noop.workflow import NoopWorkflowEngine

__all__ = ["Container"]


@dataclass(slots=True)
class Container:
    """Application-wide dependency graph.

    Construct once per process via ``Container.from_settings(settings)``.
    Use cases accept only the specific ports they need, not the whole
    container — this keeps use-case signatures honest about their
    dependencies.
    """

    settings: Settings
    clock: Clock
    event_dispatcher: EventDispatcher
    ai_services: AiServices
    decision_engine: DecisionEngine
    workflow_engine: WorkflowEngine

    @classmethod
    def from_settings(cls, settings: Settings) -> Container:
        """Build the default container for ``settings``.

        All optional ports get Noop implementations. As real adapters
        land (per roadmap phase), add branches here that select between
        Noop and real based on the relevant ``Settings`` flag.
        """

        return cls(
            settings=settings,
            clock=SystemClock(),
            event_dispatcher=SyncEventDispatcher(),
            # AI is Noop until real backends land (v0.6). The
            # settings.ai_enabled flag will then switch between Noop
            # and a concrete AiServices implementation.
            ai_services=NoopAiServices(),
            decision_engine=NoopDecisionEngine(),
            workflow_engine=NoopWorkflowEngine(),
        )
