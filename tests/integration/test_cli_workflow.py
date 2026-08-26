"""Integration tests for `growth workflow` (declarative workflows)."""

from __future__ import annotations

from typer.testing import CliRunner

from growth.presentation.cli.app import app
from tests.helpers import SharedDbAppFactory, yaml_file

runner = CliRunner()


def test_workflow_register_and_run(monkeypatch) -> None:
    factory = SharedDbAppFactory()
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    path = yaml_file(
        """
        name: review
        trigger: external
        steps: []
        """
    )
    result = runner.invoke(app, ["workflow", "register", str(path)])
    assert result.exit_code == 0
    assert "Registered workflow 'review'" in result.stdout

    result = runner.invoke(app, ["workflow", "run", "review"])
    assert result.exit_code == 0
    assert "ok (0 step(s))" in result.stdout


def test_workflow_register_and_dry_run(monkeypatch) -> None:
    factory = SharedDbAppFactory()
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    path = yaml_file(
        """
        name: review
        trigger: external
        steps: []
        """
    )
    result = runner.invoke(app, ["workflow", "register", str(path)])
    assert result.exit_code == 0

    result = runner.invoke(app, ["workflow", "run", "review", "--dry-run"])
    assert result.exit_code == 0
    assert "ok (0 step(s))" in result.stdout


def test_workflow_run_unknown_fails(monkeypatch) -> None:
    factory = SharedDbAppFactory()
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    result = runner.invoke(app, ["workflow", "run", "nope"])
    assert result.exit_code == 1
    assert "FAILED" in result.stdout
    assert "Unknown workflow 'nope'" in result.stdout


def test_workflow_register_invalid_yaml(monkeypatch) -> None:
    factory = SharedDbAppFactory()
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    path = yaml_file("name: [unclosed\n")
    result = runner.invoke(app, ["workflow", "register", str(path)])
    assert result.exit_code == 1
    assert "Failed to register workflow" in result.stdout
    assert "Invalid YAML" in result.stdout


def test_workflow_register_unknown_step(monkeypatch) -> None:
    factory = SharedDbAppFactory()
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    path = yaml_file(
        """
        name: review
        trigger: external
        steps:
          - nope
        """
    )
    result = runner.invoke(app, ["workflow", "register", str(path)])
    assert result.exit_code == 1
    assert "unknown step 'nope'" in result.stdout
