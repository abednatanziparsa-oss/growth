"""Synchronous, in-process EventDispatcher implementation.

Routes events to handlers immediately on dispatch. Failure isolation:
each handler is called in its own try/except so one failing handler
cannot prevent others from running. Handler exceptions are logged.

This dispatcher is sufficient for the bootstrap phase and v0.1-v0.6
of the roadmap. The port (``growth.application.ports.event_dispatcher``)
remains stable when we later swap to a persistent or async dispatcher.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from growth.application.ports.event_dispatcher import Event, EventHandler
from growth.infrastructure.logging.setup import get_logger

__all__ = ["SyncEventDispatcher"]


class SyncEventDispatcher:
    """Synchronous pub/sub event dispatcher.

    Not thread-safe; designed for single-threaded use within one
    process. If concurrent dispatch becomes a requirement, wrap
    ``_handlers`` access in a lock or switch to an async dispatcher.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._log = get_logger(__name__)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register ``handler`` to receive events of ``event_type``."""

        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def dispatch(self, event: Event) -> None:
        """Dispatch ``event`` to all subscribed handlers, isolating failures.

        Handlers are called in registration order. Exceptions are caught
        per handler and logged; dispatch continues to the next handler.
        """

        handlers = self._handlers.get(event.event_type, [])
        self._log.debug(
            "event.dispatch", event_type=event.event_type, handler_count=len(handlers)
        )
        for handler in handlers:
            self._call_handler(handler, event)

    def _call_handler(self, handler: Callable[[Event], None], event: Event) -> None:
        """Call ``handler(event)`` and isolate any exception it raises."""

        try:
            handler(event)
        except Exception as exc:
            self._log.exception(
                "event.handler_failed",
                event_type=event.event_type,
                handler=repr(handler),
                error=str(exc),
            )
