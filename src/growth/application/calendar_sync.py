"""Calendar sync use case — push pending reminders as calendar events.

Idempotency is guaranteed through the identity map (provider ``gcal``):
a reminder that already has an event is updated in place; only new
reminders create events. Re-running the push never duplicates events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from growth.application.ports.identity_map import IdentityMapPort
from growth.application.ports.reminders import ReminderRepository
from growth.domain.reminders import Reminder
from growth.domain.shared import SpaceId

__all__ = ["CalendarSync", "PushResult"]

_PROVIDER = "gcal"
_EVENT_TYPE = "event"


@dataclass(slots=True)
class PushResult:
    """Outcome of one ``CalendarSync.push`` run."""

    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: int = 0


class CalendarSync:
    """Push pending reminders to Google Calendar (idempotent)."""

    def __init__(
        self,
        reminders: ReminderRepository,
        identity_map: IdentityMapPort,
        projection: Any,
        adapter: Any,
    ) -> None:
        self._reminders = reminders
        self._identity_map = identity_map
        self._projection = projection
        self._adapter = adapter

    def push(self, space_id: SpaceId, now: datetime | None = None) -> PushResult:
        """Create/update calendar events for all pending reminders."""
        now = now or datetime.now(UTC)
        result = PushResult()

        for reminder in self._reminders.list_pending(space_id):
            if reminder.due_at < now:
                continue  # past-due reminders are the scheduler's job, not calendar's
            try:
                self._push_one(reminder, result)
            except Exception:
                result.errors += 1

        return result

    def _push_one(self, reminder: Reminder, result: PushResult) -> None:
        """Create or update a single reminder's calendar event."""
        payload = self._projection.project(reminder)
        entry = self._identity_map.get(reminder.id, _PROVIDER)

        if entry is None:
            event_id = self._adapter.create_event(payload)
            self._identity_map.put(reminder.id, _PROVIDER, event_id, _EVENT_TYPE)
            result.created.append(reminder.title)
            return

        self._adapter.update_event(entry.provider_resource_id, payload)
        result.updated.append(reminder.title)
