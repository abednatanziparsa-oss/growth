"""Integration tests for `growth workflow` (declarative workflows)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from growth.infrastructure.config.settings import Settings
from growth.presentation.cli.app import app
from tests.helpers import SharedDbAppFactory, yaml_file

runner = CliRunner()


def _factory(tmp_path: Path) -> SharedDbAppFactory:
    """Factory whose workflows dir lives under the test's temp dir."""
    return SharedDbAppFactory(
        settings=Settings(_env_file=None, workflows_dir=tmp_path / "workflows")
    )


def test_workflow_register_persists_and_run_loads(monkeypatch, tmp_path) -> None:
    factory = _factory(tmp_path)
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
    assert (tmp_path / "workflows" / "review.yaml").exists()

    # A fresh factory (equivalent to a separate process) loads the
    # persisted file and runs it — persistence + auto-load end-to-end.
    factory2 = _factory(tmp_path)
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory2)
    result = runner.invoke(app, ["workflow", "run", "review"])
    assert result.exit_code == 0
    assert "ok (0 step(s))" in result.stdout


def test_workflow_register_and_dry_run(monkeypatch, tmp_path) -> None:
    factory = _factory(tmp_path)
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


def test_workflow_run_with_builtin_step(monkeypatch, tmp_path) -> None:
    factory = _factory(tmp_path)
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    path = yaml_file(
        """
        name: daily-review
        trigger: time
        steps:
          - next-action
        """
    )
    runner.invoke(app, ["workflow", "register", str(path)])

    result = runner.invoke(app, ["workflow", "run", "daily-review"])
    assert result.exit_code == 0
    assert "ok (1 step(s))" in result.stdout


def test_workflow_list(monkeypatch, tmp_path) -> None:
    factory = _factory(tmp_path)
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    for name in ("alpha", "beta"):
        path = yaml_file(f"name: {name}\ntrigger: external\nsteps: []\n")
        runner.invoke(app, ["workflow", "register", str(path)])

    result = runner.invoke(app, ["workflow", "list"])
    assert result.exit_code == 0
    assert "alpha" in result.stdout
    assert "beta" in result.stdout


def test_workflow_list_empty(monkeypatch, tmp_path) -> None:
    factory = _factory(tmp_path)
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    result = runner.invoke(app, ["workflow", "list"])
    assert result.exit_code == 0
    assert "No workflows registered." in result.stdout


def test_workflow_run_unknown_fails(monkeypatch, tmp_path) -> None:
    factory = _factory(tmp_path)
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    result = runner.invoke(app, ["workflow", "run", "nope"])
    assert result.exit_code == 1
    assert "FAILED" in result.stdout
    assert "Unknown workflow 'nope'" in result.stdout


def test_workflow_run_breaks_on_invalid_file(monkeypatch, tmp_path) -> None:
    factory = _factory(tmp_path)
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    broken = tmp_path / "workflows"
    broken.mkdir(parents=True)
    (broken / "bad.yaml").write_text("name: [unclosed\n", encoding="utf-8")

    result = runner.invoke(app, ["workflow", "run", "anything"])
    assert result.exit_code == 1
    assert "Failed to load workflows" in result.stdout


def test_workflow_register_invalid_yaml(monkeypatch, tmp_path) -> None:
    factory = _factory(tmp_path)
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    path = yaml_file("name: [unclosed\n")
    result = runner.invoke(app, ["workflow", "register", str(path)])
    assert result.exit_code == 1
    assert "Failed to register workflow" in result.stdout
    assert "Invalid YAML" in result.stdout


def test_workflow_register_unknown_step(monkeypatch, tmp_path) -> None:
    factory = _factory(tmp_path)
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


def test_workflow_register_unsafe_name(monkeypatch, tmp_path) -> None:
    factory = _factory(tmp_path)
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    path = yaml_file("name: ../evil\ntrigger: external\nsteps: []\n")
    result = runner.invoke(app, ["workflow", "register", str(path)])
    assert result.exit_code == 1
    assert "safe filename" in result.stdout
