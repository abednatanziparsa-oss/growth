"""Unit tests for SyncEventDispatcher — pub/sub with failure isolation."""

from __future__ import annotations

from dataclasses import dataclass

from growth.application.ports.event_dispatcher import Event
from growth.infrastructure.events.sync_dispatcher import SyncEventDispatcher


@dataclass
class _FakeEvent:
    """Minimal concrete event satisfying the Event protocol."""

    event_type: str


def _event(event_type: str = "task.created") -> Event:
    return _FakeEvent(event_type=event_type)


class _Recorder:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def __call__(self, event: Event) -> None:
        self.events.append(event)


class _BoomHandler:
    def __call__(self, event: Event) -> None:
        raise RuntimeError("handler exploded")


class TestSyncEventDispatcher:
    def test_subscribe_and_dispatch(self) -> None:
        dispatcher = SyncEventDispatcher()
        recorder = _Recorder()
        dispatcher.subscribe("task.created", recorder)

        dispatcher.dispatch(_event())

        assert len(recorder.events) == 1
        assert recorder.events[0].event_type == "task.created"

    def test_only_matching_type_receives(self) -> None:
        dispatcher = SyncEventDispatcher()
        recorder = _Recorder()
        dispatcher.subscribe("other.event", recorder)

        dispatcher.dispatch(_event())

        assert recorder.events == []

    def test_duplicate_subscription_deduped(self) -> None:
        dispatcher = SyncEventDispatcher()
        recorder = _Recorder()
        dispatcher.subscribe("task.created", recorder)
        dispatcher.subscribe("task.created", recorder)

        dispatcher.dispatch(_event())

        assert len(recorder.events) == 1

    def test_handler_exception_isolated(self) -> None:
        dispatcher = SyncEventDispatcher()
        boom = _BoomHandler()
        recorder = _Recorder()
        dispatcher.subscribe("task.created", boom)
        dispatcher.subscribe("task.created", recorder)

        dispatcher.dispatch(_event())  # must not raise

        assert len(recorder.events) == 1

    def test_dispatch_without_handlers_is_noop(self) -> None:
        dispatcher = SyncEventDispatcher()
        dispatcher.dispatch(_event())  # must not raise

    def test_multiple_handlers_in_order(self) -> None:
        dispatcher = SyncEventDispatcher()
        order: list[str] = []
        dispatcher.subscribe("e", lambda _ev: order.append("first"))
        dispatcher.subscribe("e", lambda _ev: order.append("second"))

        dispatcher.dispatch(_event("e"))

        assert order == ["first", "second"]
