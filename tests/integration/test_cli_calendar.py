"""CLI tests for the calendar command group."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from growth.domain.reminders import Reminder, ReminderTarget
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId
from growth.infrastructure.config.settings import Settings
from growth.presentation.cli.app import app
from tests.helpers import SharedDbAppFactory, runner


def _configured_factory(credentials: Any, token: Any) -> SharedDbAppFactory:
    settings = Settings()
    settings.google_credentials_path = credentials
    settings.google_token_path = token
    return SharedDbAppFactory(settings=settings)


def _add_reminder(factory: SharedDbAppFactory, *, title: str = "Study") -> None:
    app_ctx = factory()
    repo = app_ctx.reminder_repo
    assert repo is not None
    now = datetime(2026, 8, 13, 10, 0, tzinfo=UTC)
    repo.save(
        Reminder(
            id=InternalId(),
            space_id=DEFAULT_SPACE_ID,
            title=title,
            due_at=datetime(2026, 8, 13, 18, 0, tzinfo=UTC),
            target_type=ReminderTarget.SPACE,
            created_at=now,
            updated_at=now,
        )
    )


class _FakeResp:
    def __init__(self, data: Any) -> None:
        self._data = data

    def execute(self) -> Any:
        return self._data


class _FakeEvents:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def insert(self, calendarId: str, body: dict[str, Any]) -> _FakeResp:
        self.calls.append(("insert", body))
        return _FakeResp({"id": f"evt-{len(self.calls)}"})

    def update(self, calendarId: str, eventId: str, body: dict[str, Any]) -> _FakeResp:
        self.calls.append(("update", eventId))
        return _FakeResp({})

    def list(self, **kwargs: Any) -> _FakeResp:
        self.calls.append(("list", kwargs))
        return _FakeResp(
            {
                "items": [
                    {
                        "id": "evt-1",
                        "summary": "Upcoming thing",
                        "start": {"dateTime": "2026-08-20T09:00:00+03:30"},
                    }
                ]
            }
        )


class _FakeService:
    def __init__(self) -> None:
        self._events = _FakeEvents()

    def events(self) -> _FakeEvents:
        return self._events


class TestCalendarCli:
    def test_push_without_config_errors(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "growth.presentation.cli.app.build_app", _configured_factory(None, None)
        )
        result = runner.invoke(app, ["calendar", "push"])
        assert result.exit_code == 1
        assert "not configured" in result.stderr

    def test_list_without_config_errors(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "growth.presentation.cli.app.build_app", _configured_factory(None, None)
        )
        result = runner.invoke(app, ["calendar", "list"])
        assert result.exit_code == 1
        assert "not configured" in result.stderr

    def test_auth_without_credentials_errors(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(
            "growth.presentation.cli.app.build_app",
            _configured_factory(None, tmp_path / "token.json"),
        )
        result = runner.invoke(app, ["calendar", "auth"])
        assert result.exit_code == 1
        assert "GROWTH_GOOGLE_CREDENTIALS_PATH" in result.stderr

    def test_auth_without_token_path_errors(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(
            "growth.presentation.cli.app.build_app",
            _configured_factory(tmp_path / "credentials.json", None),
        )
        result = runner.invoke(app, ["calendar", "auth"])
        assert result.exit_code == 1
        assert "GROWTH_GOOGLE_TOKEN_PATH" in result.stderr

    def test_auth_success_runs_oauth_and_reports(self, monkeypatch, tmp_path) -> None:
        factory = _configured_factory(
            tmp_path / "credentials.json", tmp_path / "token.json"
        )
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        written: list[object] = []
        monkeypatch.setattr(
            "growth.infrastructure.adapters.calendar.run_oauth_flow",
            lambda creds, token: written.append((creds, token)),
        )

        result = runner.invoke(app, ["calendar", "auth"])

        assert result.exit_code == 0
        assert "[OK] Token saved" in result.stdout
        assert len(written) == 1

    def test_push_creates_events(self, monkeypatch, tmp_path) -> None:
        factory = _configured_factory(
            tmp_path / "credentials.json", tmp_path / "token.json"
        )
        _add_reminder(factory, title="Math review")
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        monkeypatch.setattr(
            "growth.infrastructure.adapters.calendar.build_calendar_service",
            lambda _token: _FakeService(),
        )

        result = runner.invoke(app, ["calendar", "push"])

        assert result.exit_code == 0
        assert "[created] Math review" in result.stdout
        assert "1 created" in result.stdout

    def test_push_is_idempotent_across_runs(self, monkeypatch, tmp_path) -> None:
        factory = _configured_factory(
            tmp_path / "credentials.json", tmp_path / "token.json"
        )
        _add_reminder(factory, title="Math review")
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        monkeypatch.setattr(
            "growth.infrastructure.adapters.calendar.build_calendar_service",
            lambda _token: _FakeService(),
        )

        first = runner.invoke(app, ["calendar", "push"])
        second = runner.invoke(app, ["calendar", "push"])

        assert first.exit_code == 0
        assert second.exit_code == 0
        assert "[updated] Math review" in second.stdout
        assert "0 created, 1 updated" in second.stdout

    def test_push_with_no_reminders_reports_zeros(self, monkeypatch, tmp_path) -> None:
        factory = _configured_factory(
            tmp_path / "credentials.json", tmp_path / "token.json"
        )
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        monkeypatch.setattr(
            "growth.infrastructure.adapters.calendar.build_calendar_service",
            lambda _token: _FakeService(),
        )

        result = runner.invoke(app, ["calendar", "push"])

        assert result.exit_code == 0
        assert "0 created, 0 updated, 0 skipped" in result.stdout

    def test_list_shows_upcoming_events(self, monkeypatch, tmp_path) -> None:
        factory = _configured_factory(
            tmp_path / "credentials.json", tmp_path / "token.json"
        )
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        monkeypatch.setattr(
            "growth.infrastructure.adapters.calendar.build_calendar_service",
            lambda _token: _FakeService(),
        )

        result = runner.invoke(app, ["calendar", "list"])

        assert result.exit_code == 0
        assert "Upcoming thing" in result.stdout

    def test_list_with_no_events_reports_empty(self, monkeypatch, tmp_path) -> None:
        factory = _configured_factory(
            tmp_path / "credentials.json", tmp_path / "token.json"
        )
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)

        class EmptyService:
            def events(self) -> _FakeEvents:
                events = _FakeEvents()
                events.list = lambda **_kwargs: _FakeResp({"items": []})
                return events

        monkeypatch.setattr(
            "growth.infrastructure.adapters.calendar.build_calendar_service",
            lambda _token: EmptyService(),
        )

        result = runner.invoke(app, ["calendar", "list"])

        assert result.exit_code == 0
        assert "No upcoming events." in result.stdout

    def test_export_ics_writes_file(self, monkeypatch, tmp_path) -> None:
        factory = _configured_factory(None, None)
        _add_reminder(factory, title="Math review")
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        out = tmp_path / "reminders.ics"

        result = runner.invoke(app, ["calendar", "export-ics", "--out", str(out)])

        assert result.exit_code == 0
        assert "1 reminder(s) exported" in result.stdout
        text = out.read_text(encoding="utf-8")
        assert text.startswith("BEGIN:VCALENDAR")
        assert "SUMMARY:Math review" in text
        assert "BEGIN:VEVENT" in text

        raw = out.read_bytes()
        assert b"\r\n" in raw
        assert b"\r\r\n" not in raw  # no Windows CRLF translation
        assert raw.endswith(b"\r\n")

    def test_export_ics_with_no_reminders(self, monkeypatch, tmp_path) -> None:
        factory = _configured_factory(None, None)
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        out = tmp_path / "empty.ics"

        result = runner.invoke(app, ["calendar", "export-ics", "--out", str(out)])

        assert result.exit_code == 0
        assert "0 reminder(s) exported" in result.stdout
        text = out.read_text(encoding="utf-8")
        assert text.startswith("BEGIN:VCALENDAR")
        assert "BEGIN:VEVENT" not in text

    def test_export_ics_default_path(self, monkeypatch, tmp_path) -> None:
        factory = _configured_factory(None, None)
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        monkeypatch.setattr(
            "growth.presentation.cli.app.Path.home",
            lambda: tmp_path,
        )

        result = runner.invoke(app, ["calendar", "export-ics"])

        assert result.exit_code == 0
        default = tmp_path / ".growth" / "reminders.ics"
        assert default.exists()
        assert "0 reminder(s) exported" in result.stdout
