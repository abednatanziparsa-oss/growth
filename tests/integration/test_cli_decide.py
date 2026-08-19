"""Integration tests for `growth decide` (heuristic Decision Engine)."""

from __future__ import annotations

from typer.testing import CliRunner

from growth.presentation.cli.app import app
from tests.helpers import SharedDbAppFactory, apply_plan

runner = CliRunner()

PLAN = """\
project_name: Study Plan
subjects:
  - name: Math
    priority: high
    chapters:
      - name: Algebra
"""


def test_decide_next_action_recommends(monkeypatch) -> None:
    factory = SharedDbAppFactory()
    apply_plan(monkeypatch, factory, PLAN)
    result = runner.invoke(app, ["decide", "next-action"])
    assert result.exit_code == 0
    assert "Next action:" in result.stdout


def test_decide_sort_lists_tasks(monkeypatch) -> None:
    factory = SharedDbAppFactory()
    apply_plan(monkeypatch, factory, PLAN)
    result = runner.invoke(app, ["decide", "sort"])
    assert result.exit_code == 0
    assert "Algebra" in result.stdout


def test_decide_blockers_empty(monkeypatch) -> None:
    factory = SharedDbAppFactory()
    apply_plan(monkeypatch, factory, PLAN)
    result = runner.invoke(app, ["decide", "blockers"])
    assert result.exit_code == 0
    assert "No overdue tasks." in result.stdout


def test_decide_next_action_empty_db(monkeypatch) -> None:
    factory = SharedDbAppFactory()
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    result = runner.invoke(app, ["decide", "next-action"])
    assert result.exit_code == 0
    assert "No actionable tasks." in result.stdout


def test_decide_sort_empty_db(monkeypatch) -> None:
    factory = SharedDbAppFactory()
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    result = runner.invoke(app, ["decide", "sort"])
    assert result.exit_code == 0
    assert "No incomplete tasks." in result.stdout
