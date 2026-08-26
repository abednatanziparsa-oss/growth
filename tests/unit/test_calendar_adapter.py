"""Unit tests for the Google Calendar adapter (fake service injected)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import google.oauth2.credentials as creds_mod
import google_auth_oauthlib.flow as flow_mod
import googleapiclient.discovery as discovery_mod
import pytest

from growth.application.errors import ProviderUnavailableError
from growth.domain.reminders import Reminder, ReminderTarget
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId
from growth.infrastructure.adapters.calendar import (
    SCOPES,
    GoogleCalendarAdapter,
    build_calendar_service,
    run_oauth_flow,
)
from growth.infrastructure.projections.calendar import (
    CalendarProjection,
)


class _Response:
    def __init__(self, data: Any) -> None:
        self._data = data

    def execute(self) -> Any:
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


class FakeEvents:
    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self.calls: list[tuple[str, Any]] = []
        self._items = items or []

    def insert(self, calendarId: str, body: dict[str, Any]) -> _Response:
        self.calls.append(("insert", body))
        return _Response({"id": f"evt-{len(self.calls)}"})

    def update(self, calendarId: str, eventId: str, body: dict[str, Any]) -> _Response:
        self.calls.append(("update", {"eventId": eventId, "body": body}))
        return _Response({})

    def delete(self, calendarId: str, eventId: str) -> _Response:
        self.calls.append(("delete", eventId))
        return _Response({})

    def list(self, **kwargs: Any) -> _Response:
        self.calls.append(("list", kwargs))
        return _Response({"items": self._items})


class FakeService:
    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self._events = FakeEvents(items)

    def events(self) -> FakeEvents:
        return self._events


def _payload(title: str = "Study") -> Any:
    now = datetime(2026, 8, 13, 8, 0, tzinfo=UTC)
    reminder = Reminder(
        id=InternalId(),
        space_id=DEFAULT_SPACE_ID,
        title=title,
        due_at=datetime(2026, 8, 13, 12, 0, tzinfo=UTC),
        target_type=ReminderTarget.SPACE,
        created_at=now,
        updated_at=now,
    )
    return CalendarProjection().project(reminder)


class TestGoogleCalendarAdapter:
    def test_run_oauth_flow_writes_token_file(self, monkeypatch, tmp_path) -> None:
        class FakeCreds:
            def to_json(self) -> str:
                return '{"token": "abc"}'

        class FakeFlow:
            @classmethod
            def from_client_secrets_file(cls, path: str, scopes: list[str]) -> FakeFlow:
                assert path.endswith("credentials.json")
                assert scopes == SCOPES
                return cls()

            def run_local_server(self, port: int = 0) -> FakeCreds:
                assert port == 0
                return FakeCreds()

        monkeypatch.setattr(flow_mod, "InstalledAppFlow", FakeFlow)
        credentials_path = tmp_path / "credentials.json"
        credentials_path.write_text("{}", encoding="utf-8")
        token_path = tmp_path / "nested" / "token.json"

        run_oauth_flow(credentials_path, token_path)

        assert token_path.read_text(encoding="utf-8") == '{"token": "abc"}'

    def test_build_calendar_service_builds_client(self, monkeypatch, tmp_path) -> None:
        called: dict[str, object] = {}

        class FakeCreds:
            pass

        the_creds = FakeCreds()
        monkeypatch.setattr(
            creds_mod.Credentials,
            "from_authorized_user_file",
            classmethod(lambda _cls, _path, _scopes: the_creds),
        )

        http_kwargs: dict[str, object] = {}

        class FakeHttp:
            def __init__(self, **kwargs: object) -> None:
                http_kwargs.update(kwargs)

        monkeypatch.setattr("httplib2.Http", FakeHttp)

        class FakeAuthorizedHttp:
            def __init__(self, credentials: object, http: object) -> None:
                self.credentials = credentials
                self.http = http

        monkeypatch.setattr("google_auth_httplib2.AuthorizedHttp", FakeAuthorizedHttp)

        def fake_build(api: str, version: str, **kwargs: object) -> str:
            called["api"] = api
            called["version"] = version
            called["http"] = kwargs.get("http")
            called["cache"] = kwargs.get("cache")
            return "service"

        monkeypatch.setattr(discovery_mod, "build", fake_build)
        token_path = tmp_path / "token.json"
        token_path.write_text("{}", encoding="utf-8")

        service = build_calendar_service(token_path)

        assert service == "service"
        cache = called.pop("cache")
        http = called.pop("http")
        assert called == {"api": "calendar", "version": "v3"}
        assert isinstance(http, FakeAuthorizedHttp)
        assert http.credentials is the_creds
        assert isinstance(http.http, FakeHttp)
        # httplib2 0.32 times out on empty proxy env vars (HTTP_PROXY="");
        # the service must be built with proxy discovery disabled.
        assert http_kwargs.get("proxy_info") is None
        assert cache is not None
        assert cache.get("url") is None
        assert cache.set("url", "resp") is None

    def test_scopes_are_read_write_events(self) -> None:
        assert SCOPES == ["https://www.googleapis.com/auth/calendar.events"]

    def test_create_event_returns_provider_id(self) -> None:
        service = FakeService()
        adapter = GoogleCalendarAdapter(service)
        event_id = adapter.create_event(_payload("Review"))

        assert event_id == "evt-1"
        method, body = service.events().calls[0]
        assert method == "insert"
        assert body["summary"] == "Review"
        assert body["start"]["dateTime"].endswith("+00:00")

    def test_update_event_sends_body(self) -> None:
        service = FakeService()
        adapter = GoogleCalendarAdapter(service)
        adapter.update_event("evt-9", _payload("Changed"))

        method, call = service.events().calls[0]
        assert method == "update"
        assert call["eventId"] == "evt-9"
        assert call["body"]["summary"] == "Changed"

    def test_delete_event(self) -> None:
        service = FakeService()
        adapter = GoogleCalendarAdapter(service)
        adapter.delete_event("evt-5")

        assert service.events().calls == [("delete", "evt-5")]

    def test_list_events_returns_items(self) -> None:
        items = [{"id": "a", "summary": "Study"}]
        service = FakeService(items=items)
        adapter = GoogleCalendarAdapter(service)

        result = adapter.list_events(
            time_min="2026-01-01T00:00:00Z", time_max="2026-02-01T00:00:00Z"
        )
        assert result == items
        method, kwargs = service.events().calls[0]
        assert method == "list"
        assert kwargs["singleEvents"] is True
        assert kwargs["orderBy"] == "startTime"

    def test_create_failure_raises_provider_error(self) -> None:
        service = FakeService()
        service._events.insert = lambda _calendar_id, _body: _Response(
            RuntimeError("boom")
        )
        adapter = GoogleCalendarAdapter(service)

        with pytest.raises(ProviderUnavailableError):
            adapter.create_event(_payload())

    def test_update_failure_raises_provider_error(self) -> None:
        service = FakeService()
        service._events.update = lambda _calendar_id, _event_id, _body: _Response(
            RuntimeError("boom")
        )
        adapter = GoogleCalendarAdapter(service)

        with pytest.raises(ProviderUnavailableError):
            adapter.update_event("evt-1", _payload())

    def test_delete_failure_raises_provider_error(self) -> None:
        service = FakeService()
        service._events.delete = lambda _calendar_id, _event_id: _Response(
            RuntimeError("boom")
        )
        adapter = GoogleCalendarAdapter(service)

        with pytest.raises(ProviderUnavailableError):
            adapter.delete_event("evt-1")

    def test_list_failure_raises_provider_error(self) -> None:
        service = FakeService()
        service._events.list = lambda **_kwargs: _Response(RuntimeError("boom"))
        adapter = GoogleCalendarAdapter(service)

        with pytest.raises(ProviderUnavailableError):
            adapter.list_events(time_min="a", time_max="b")
