"""Integration tests for the reminder CLI commands."""

from __future__ import annotations

from uuid import uuid4

from typer.testing import CliRunner

from growth.presentation.cli.app import app
from tests.helpers import SharedDbAppFactory

runner = CliRunner()


def _factory(monkeypatch) -> SharedDbAppFactory:
    factory = SharedDbAppFactory()
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    return factory


class TestReminderAdd:
    def test_add_with_naive_time(self, monkeypatch) -> None:
        _factory(monkeypatch)
        result = runner.invoke(
            app, ["reminder", "add", "Study algebra", "--at", "2026-08-13 09:00"]
        )

        assert result.exit_code == 0
        assert "[OK] Reminder created" in result.stdout
        assert "2026-08-13T09:00:00+00:00" in result.stdout

    def test_add_with_aware_time(self, monkeypatch) -> None:
        _factory(monkeypatch)
        result = runner.invoke(
            app,
            ["reminder", "add", "Call mom", "--at", "2026-08-13T09:00:00+03:30"],
        )

        assert result.exit_code == 0
        assert "+03:30" in result.stdout

    def test_add_attached_to_task(self, monkeypatch) -> None:
        _factory(monkeypatch)
        task_id = str(uuid4())
        result = runner.invoke(
            app,
            [
                "reminder",
                "add",
                "Finish essay",
                "--at",
                "2026-08-14 10:00",
                "--task",
                task_id,
            ],
        )

        assert result.exit_code == 0
        listing = runner.invoke(app, ["reminder", "list"])
        assert f"task:{task_id}" in listing.stdout

    def test_add_invalid_time_errors(self, monkeypatch) -> None:
        _factory(monkeypatch)
        result = runner.invoke(app, ["reminder", "add", "X", "--at", "not-a-time"])

        assert result.exit_code == 1
        assert "Invalid --at value" in result.stderr

    def test_add_recurring_daily(self, monkeypatch) -> None:
        _factory(monkeypatch)
        result = runner.invoke(
            app,
            [
                "reminder",
                "add",
                "Daily pushup",
                "--at",
                "2026-08-13 07:00",
                "--repeat",
                "daily",
                "--interval",
                "2",
                "--count",
                "30",
            ],
        )

        assert result.exit_code == 0
        assert "repeats daily every 2" in result.stdout

    def test_add_recurring_invalid_repeat_errors(self, monkeypatch) -> None:
        _factory(monkeypatch)
        result = runner.invoke(
            app,
            ["reminder", "add", "X", "--at", "2026-08-13 07:00", "--repeat", "hourly"],
        )

        assert result.exit_code == 1
        assert "Invalid --repeat" in result.stderr

    def test_add_options_without_repeat_error(self, monkeypatch) -> None:
        _factory(monkeypatch)
        result = runner.invoke(
            app,
            ["reminder", "add", "X", "--at", "2026-08-13 07:00", "--count", "3"],
        )

        assert result.exit_code == 1
        assert "require --repeat" in result.stderr

    def test_add_invalid_until_errors(self, monkeypatch) -> None:
        _factory(monkeypatch)
        result = runner.invoke(
            app,
            [
                "reminder",
                "add",
                "X",
                "--at",
                "2026-08-13 07:00",
                "--repeat",
                "daily",
                "--until",
                "nope",
            ],
        )

        assert result.exit_code == 1
        assert "Invalid --until" in result.stderr

    def test_add_invalid_count_errors(self, monkeypatch) -> None:
        _factory(monkeypatch)
        result = runner.invoke(
            app,
            [
                "reminder",
                "add",
                "X",
                "--at",
                "2026-08-13 07:00",
                "--repeat",
                "daily",
                "--count",
                "0",
            ],
        )

        assert result.exit_code == 1
        assert "count must be >= 1" in result.stderr


class TestReminderList:
    def test_list_empty(self, monkeypatch) -> None:
        _factory(monkeypatch)
        result = runner.invoke(app, ["reminder", "list"])

        assert result.exit_code == 0
        assert "No reminders yet" in result.stdout

    def test_list_shows_reminders(self, monkeypatch) -> None:
        _factory(monkeypatch)
        runner.invoke(app, ["reminder", "add", "Study", "--at", "2026-08-13 09:00"])

        result = runner.invoke(app, ["reminder", "list"])

        assert result.exit_code == 0
        assert "Study" in result.stdout
        assert "pending" in result.stdout


class TestReminderDue:
    def test_due_empty(self, monkeypatch) -> None:
        _factory(monkeypatch)
        result = runner.invoke(app, ["reminder", "due"])

        assert result.exit_code == 0
        assert "No due reminders" in result.stdout

    def test_due_after_add(self, monkeypatch) -> None:
        _factory(monkeypatch)
        runner.invoke(app, ["reminder", "add", "Past due", "--at", "2020-01-01 09:00"])

        result = runner.invoke(app, ["reminder", "due"])

        assert result.exit_code == 0
        assert "Past due" in result.stdout

    def test_due_excludes_future(self, monkeypatch) -> None:
        _factory(monkeypatch)
        runner.invoke(app, ["reminder", "add", "Future", "--at", "2099-01-01 09:00"])

        result = runner.invoke(app, ["reminder", "due"])

        assert result.exit_code == 0
        assert "No due reminders" in result.stdout


class TestReminderFire:
    def test_fire_marks_fired(self, monkeypatch) -> None:
        _factory(monkeypatch)
        runner.invoke(app, ["reminder", "add", "Do it", "--at", "2020-01-01 09:00"])

        listing = runner.invoke(app, ["reminder", "list"])
        reminder_id = listing.stdout.split()[1]  # second token is the id

        result = runner.invoke(app, ["reminder", "fire", reminder_id])
        assert result.exit_code == 0
        assert "[OK] Reminder fired: Do it" in result.stdout

        after = runner.invoke(app, ["reminder", "list"])
        assert "fired" in after.stdout

    def test_fire_missing_id_errors(self, monkeypatch) -> None:
        _factory(monkeypatch)
        result = runner.invoke(app, ["reminder", "fire", str(uuid4())])

        assert result.exit_code == 1
        assert "[ERROR]" in result.stderr

    def test_fire_invalid_id_errors(self, monkeypatch) -> None:
        _factory(monkeypatch)
        result = runner.invoke(app, ["reminder", "fire", "not-a-uuid"])

        assert result.exit_code == 1
        assert "[ERROR]" in result.stderr


class TestReminderSweep:
    def test_sweep_with_no_due(self, monkeypatch) -> None:
        _factory(monkeypatch)
        result = runner.invoke(app, ["reminder", "sweep"])

        assert result.exit_code == 0
        assert "No due reminders" in result.stdout

    def test_sweep_fires_due(self, monkeypatch) -> None:
        _factory(monkeypatch)
        runner.invoke(app, ["reminder", "add", "Past due", "--at", "2020-01-01 09:00"])

        result = runner.invoke(app, ["reminder", "sweep"])

        assert result.exit_code == 0
        assert "Past due" in result.stdout
        assert "1 fired, 0 rescheduled" in result.stdout
        after = runner.invoke(app, ["reminder", "list"])
        assert "fired" in after.stdout

    def test_sweep_reschedules_recurring(self, monkeypatch) -> None:
        _factory(monkeypatch)
        runner.invoke(
            app,
            [
                "reminder",
                "add",
                "Daily habit",
                "--at",
                "2020-01-01 09:00",
                "--repeat",
                "daily",
            ],
        )

        result = runner.invoke(app, ["reminder", "sweep"])

        assert result.exit_code == 0
        assert "Daily habit" in result.stdout
        assert "0 fired, 1 rescheduled" in result.stdout
        after = runner.invoke(app, ["reminder", "list"])
        assert "pending" in after.stdout
        assert "2020-01-02" in after.stdout
