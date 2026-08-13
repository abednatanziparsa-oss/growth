"""Google Calendar projection — maps reminders to calendar event payloads.

Pure transformation: a pending reminder becomes a calendar event whose
start time is the reminder's ``due_at`` (default duration 30 minutes).
Recurring reminders project their *current* occurrence; when the
scheduler advances ``due_at``, the calendar sync updates the event.

The projection knows nothing about Google APIs — it produces plain
dicts that the adapter sends. Keeping it pure makes the mapping fully
testable offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from growth.domain.reminders import Reminder

__all__ = ["CalendarProjection", "EventPayload"]

DEFAULT_DURATION = timedelta(minutes=30)


@dataclass(frozen=True, slots=True)
class EventPayload:
    """A calendar event ready to send to the provider."""

    summary: str
    start: str  # ISO-8601 with timezone
    end: str
    description: str = ""
    uid: str = ""  # stable per-reminder id (used by the ICS projection)


class CalendarProjection:
    """Map Reminder aggregates to event payloads."""

    def project(self, reminder: Reminder) -> EventPayload:
        """Return the event payload for a single reminder."""
        end = reminder.due_at + DEFAULT_DURATION
        target = reminder.target_id.value if reminder.target_id else "space"
        return EventPayload(
            summary=reminder.title,
            start=reminder.due_at.isoformat(),
            end=end.isoformat(),
            description=f"Growth OS reminder -> {reminder.target_type.value}:{target}",
            uid=str(reminder.id),
        )
