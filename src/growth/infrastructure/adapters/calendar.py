"""Google Calendar adapter — talks to the Google Calendar REST API.

Wraps ``googleapiclient`` behind a narrow, mockable surface:

- ``run_oauth_flow`` performs the installed-app OAuth dance and writes
  ``token.json`` (this is where the human authorizes in the browser).
- ``build_calendar_service`` loads an existing token and builds the
  service object.
- ``GoogleCalendarAdapter`` takes the service object directly, so tests
  inject a fake and never touch the network.

The OAuth client must be a **Desktop app** client (credentials.json from
the Google Cloud Console). Scopes are minimal: calendar.events (read and
write events, no ACLs or settings).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from growth.application.errors import ProviderUnavailableError

__all__ = [
    "SCOPES",
    "GoogleCalendarAdapter",
    "build_calendar_service",
    "run_oauth_flow",
]

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def run_oauth_flow(credentials_path: Path, token_path: Path) -> None:
    """Run the installed-app OAuth flow and persist the token.

    Opens a browser at the Google consent screen; the human authorizes
    and the loopback redirect captures the code. Requires
    ``credentials.json`` from a Desktop-app OAuth client.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]  # noqa: I001

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")


def build_calendar_service(token_path: Path) -> Any:
    """Build a Calendar API service from a previously stored token."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build  # type: ignore[import-untyped]

    creds = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
        str(token_path), SCOPES
    )
    return build("calendar", "v3", credentials=creds, cache=None)


class GoogleCalendarAdapter:
    """Narrow Calendar API adapter (service injected for testability)."""

    def __init__(self, service: Any, calendar_id: str = "primary") -> None:
        self._service = service
        self._calendar_id = calendar_id

    def create_event(self, payload: Any) -> str:
        """Create an event; returns its provider id."""
        body = {
            "summary": payload.summary,
            "start": {"dateTime": payload.start},
            "end": {"dateTime": payload.end},
            "description": payload.description,
        }
        try:
            event = (
                self._service.events()
                .insert(calendarId=self._calendar_id, body=body)
                .execute()
            )
        except Exception as exc:
            raise ProviderUnavailableError(
                f"Failed to create calendar event: {exc}"
            ) from exc
        return str(event["id"])

    def update_event(self, event_id: str, payload: Any) -> None:
        """Update an existing event's summary/times."""
        body = {
            "summary": payload.summary,
            "start": {"dateTime": payload.start},
            "end": {"dateTime": payload.end},
            "description": payload.description,
        }
        try:
            self._service.events().update(
                calendarId=self._calendar_id, eventId=event_id, body=body
            ).execute()
        except Exception as exc:
            raise ProviderUnavailableError(
                f"Failed to update calendar event {event_id}: {exc}"
            ) from exc

    def delete_event(self, event_id: str) -> None:
        """Delete an event by provider id."""
        try:
            self._service.events().delete(
                calendarId=self._calendar_id, eventId=event_id
            ).execute()
        except Exception as exc:
            raise ProviderUnavailableError(
                f"Failed to delete calendar event {event_id}: {exc}"
            ) from exc

    def list_events(self, *, time_min: str, time_max: str) -> list[dict[str, Any]]:
        """Return events in the window (start time ascending)."""
        try:
            result = (
                self._service.events()
                .list(
                    calendarId=self._calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except Exception as exc:
            raise ProviderUnavailableError(
                f"Failed to list calendar events: {exc}"
            ) from exc
        return list(result.get("items", []))
