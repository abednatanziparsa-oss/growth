"""Event dispatcher port — in-process pub/sub for domain events.

Bootstrap ships a synchronous, in-process dispatcher (see
``growth.infrastructure.events.sync_dispatcher``). The port keeps the
door open for a persistent / out-of-process bus later (when workflows
need to survive restarts), without changing event types.

Convention: events are **notifications, not RPC**. Handlers cannot
return values to the dispatcher; they cannot rely on execution order;
failures are isolated and logged. Cross-cutting concerns subscribe
here (read models, analytics, audit, workflow triggers).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

__all__ = ["Event", "EventDispatcher", "EventHandler"]


class Event(Protocol):
    """Marker for all domain events.

    Concrete events live with their bounded context (e.g.
    ``growth.domain.planning.events.PlanCreated``). At bootstrap, the
    protocol is empty — what matters is that every event is a small
    immutable dataclass carrying the IDs needed to react.
    """

    @property
    def event_type(self) -> str:  # pragma: no cover - protocol shape
        """Stable string identifier for this event type (e.g. ``"plan.created"``)."""
        ...


# ``EventHandler`` is a simple Callable alias rather than a generic
# Protocol because Protocol + covariant TypeVar is unsound when the
# typevar appears in a parameter position (mypy misc error). The
# dispatcher routes by ``event_type`` string at runtime, so the
# handler's concrete event type is not statically constrained here.
EventHandler = Callable[[Event], None]


@runtime_checkable
class EventDispatcher(Protocol):
    """Dispatches events to subscribed handlers.

    Implementations are responsible for failure isolation: a handler
    exception must not prevent other handlers from running or bubble
    back to the dispatcher's caller.
    """

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register ``handler`` to receive events of ``event_type``."""
        ...

    def dispatch(self, event: Event) -> None:
        """Send ``event`` to all subscribed handlers.

        Implementations may dispatch synchronously (bootstrap) or queue
        for later (future). The contract is fire-and-forget: callers do
        not wait for handlers to finish.
        """
        ...
