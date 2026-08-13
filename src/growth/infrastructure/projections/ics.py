"""iCalendar (.ics) projection — renders event payloads as RFC 5545 text.

Zero-auth alternative to pushing to Google Calendar: the CLI exports
pending reminders as a single ``.ics`` file that any calendar app
(Google Calendar, Outlook, Apple Calendar) can import.

RFC 5545 essentials implemented here:

- CRLF line endings
- value escaping (backslash, semicolon, comma, newline)
- line folding at 75 octets (continuation lines start with a space)
- stable per-reminder UIDs so re-imports don't duplicate events
- all datetimes normalized to UTC (basic format ``YYYYMMDDTHHMMSSZ``)
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from growth.infrastructure.projections.calendar import EventPayload

__all__ = ["IcsProjection"]

PRODID = "-//Growth OS//Growth OS 0.1//EN"
FOLD_LIMIT = 75  # octets per line, RFC 5545 §3.1


def _escape(value: str) -> str:
    """Escape RFC 5545 special characters in a text value."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Fold a logical line at 75 octets; continuation lines lead with a space."""
    if len(line.encode("utf-8")) <= FOLD_LIMIT:
        return line
    parts: list[str] = []
    current = ""
    for char in line:
        candidate = current + char
        if current and len(candidate.encode("utf-8")) > FOLD_LIMIT:
            parts.append(current)
            current = char
        else:
            current = candidate
    if current:
        parts.append(current)
    return "\r\n ".join(parts)


def _format_dt(value: datetime) -> str:
    """Format a datetime as UTC basic format (``20260813T143000Z``)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


class IcsProjection:
    """Render EventPayloads as a complete iCalendar document."""

    def render(self, events: Iterable[EventPayload]) -> str:
        """Return the full .ics text (CRLF, folded, trailing newline)."""
        stamp = _format_dt(datetime.now(UTC))
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            f"PRODID:{PRODID}",
            "CALSCALE:GREGORIAN",
        ]
        for event in events:
            lines.extend(self._render_event(event, stamp))
        lines.append("END:VCALENDAR")
        folded = [_fold(line) for line in lines]
        return "\r\n".join(folded) + "\r\n"

    @staticmethod
    def _render_event(event: EventPayload, stamp: str) -> list[str]:
        """Render a single VEVENT block."""
        uid = event.uid or "anon"
        return [
            "BEGIN:VEVENT",
            f"UID:{uid}@growth.local",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{_format_dt(datetime.fromisoformat(event.start))}",
            f"DTEND:{_format_dt(datetime.fromisoformat(event.end))}",
            f"SUMMARY:{_escape(event.summary)}",
            f"DESCRIPTION:{_escape(event.description)}",
            "END:VEVENT",
        ]
