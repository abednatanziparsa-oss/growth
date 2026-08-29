"""Integration tests for `growth plugin` (marketplace lifecycle)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from growth.infrastructure.config.settings import Settings
from growth.kernel.bootstrap import build_app
from growth.plugins.loader import install_plugin
from growth.presentation.cli.app import app
from tests.helpers import SharedDbAppFactory

runner = CliRunner()

PLUGIN_YAML = """\
name: hello-growth
version: 0.2.0
description: Test plugin for CLI.
entry: hello_plugin:HelloPlugin
permissions:
  - network
"""

PLUGIN_PY = """\
class HelloPlugin:
    name = "hello-growth"

    def __init__(self):
        self.activated = False

    def register(self, container):
        self.activated = True
"""


def _make_source(tmp_path: Path) -> Path:
    source = tmp_path / "staging" / "hello-growth"
    source.mkdir(parents=True)
    (source / "plugin.yaml").write_text(PLUGIN_YAML, encoding="utf-8")
    (source / "hello_plugin.py").write_text(PLUGIN_PY, encoding="utf-8")
    return source.parent


def _factory(tmp_path: Path) -> SharedDbAppFactory:
    return SharedDbAppFactory(
        settings=Settings(
            _env_file=None,
            workflows_dir=tmp_path / "workflows",
            plugins_dir=tmp_path / "plugins",
        )
    )


def test_plugin_list_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("growth.presentation.cli.app.build_app", _factory(tmp_path))
    result = runner.invoke(app, ["plugin", "list"])
    assert result.exit_code == 0
    assert "No plugins installed" in result.stdout


def test_plugin_install_list_info_uninstall(monkeypatch, tmp_path) -> None:
    source = _make_source(tmp_path)
    monkeypatch.setattr("growth.presentation.cli.app.build_app", _factory(tmp_path))

    result = runner.invoke(app, ["plugin", "install", str(source / "hello-growth")])
    assert result.exit_code == 0
    assert "Installed 'hello-growth' v0.2.0" in result.stdout
    assert (tmp_path / "plugins" / "hello-growth" / "plugin.yaml").is_file()

    result = runner.invoke(app, ["plugin", "list"])
    assert result.exit_code == 0
    assert "hello-growth" in result.stdout
    assert "0.2.0" in result.stdout
    assert "[active]" in result.stdout

    result = runner.invoke(app, ["plugin", "info", "hello-growth"])
    assert result.exit_code == 0
    assert "Version:      0.2.0" in result.stdout
    assert "network" in result.stdout
    assert "not enforced" in result.stdout

    result = runner.invoke(app, ["plugin", "uninstall", "hello-growth"])
    assert result.exit_code == 0
    assert not (tmp_path / "plugins" / "hello-growth").exists()

    result = runner.invoke(app, ["plugin", "list"])
    assert result.exit_code == 0
    assert "No plugins installed" in result.stdout


def test_plugin_install_duplicate_fails(monkeypatch, tmp_path) -> None:
    source = _make_source(tmp_path)
    monkeypatch.setattr("growth.presentation.cli.app.build_app", _factory(tmp_path))
    runner.invoke(app, ["plugin", "install", str(source / "hello-growth")])

    result = runner.invoke(app, ["plugin", "install", str(source / "hello-growth")])
    assert result.exit_code == 1
    assert "already installed" in result.stdout + result.stderr


def test_plugin_info_unknown_fails(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("growth.presentation.cli.app.build_app", _factory(tmp_path))
    result = runner.invoke(app, ["plugin", "info", "ghost"])
    assert result.exit_code == 1
    assert "not installed" in result.stdout + result.stderr


def test_plugin_uninstall_unknown_fails(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("growth.presentation.cli.app.build_app", _factory(tmp_path))
    result = runner.invoke(app, ["plugin", "uninstall", "ghost"])
    assert result.exit_code == 1
    assert "not installed" in result.stdout + result.stderr


def test_plugin_list_shows_broken_plugin(monkeypatch, tmp_path) -> None:
    broken = tmp_path / "plugins" / "broken"
    broken.mkdir(parents=True)
    (broken / "plugin.yaml").write_text("name: [oops\n", encoding="utf-8")
    monkeypatch.setattr("growth.presentation.cli.app.build_app", _factory(tmp_path))

    result = runner.invoke(app, ["plugin", "list"])
    assert result.exit_code == 0
    assert "broken" in result.stdout


def test_build_app_activates_plugins(tmp_path) -> None:
    """The composition root activates installed plugins at startup."""
    source = _make_source(tmp_path)
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        plugins_dir=tmp_path / "plugins",
    )
    install_plugin(source / "hello-growth", settings.plugins_dir)

    app_ctx = build_app(settings)
    assert len(app_ctx.plugins) == 1
    entry = app_ctx.plugins[0]
    assert entry.is_active
    assert entry.instance is not None
    assert entry.instance.activated is True


def test_build_app_survives_broken_plugin(tmp_path) -> None:
    """A broken plugin never breaks the app bootstrap."""
    broken = tmp_path / "plugins" / "broken"
    broken.mkdir(parents=True)
    (broken / "plugin.yaml").write_text("name: [oops\n", encoding="utf-8")

    app_ctx = build_app(
        Settings(
            _env_file=None,
            data_dir=tmp_path / "data",
            plugins_dir=tmp_path / "plugins",
        )
    )
    assert len(app_ctx.plugins) == 1
    assert app_ctx.plugins[0].error is not None
