"""Unit tests for the plugin manifest and loader (v1.0 platform)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from growth.plugins.loader import (
    PluginInstallError,
    activate_plugins,
    install_plugin,
    load_plugins,
    uninstall_plugin,
)
from growth.plugins.manifest import PluginManifestError, parse_plugin_manifest

VALID_YAML = """\
name: hello-growth
version: 0.1.0
description: Greets on activation.
entry: hello_plugin:HelloPlugin
author: Growth OS
permissions:
  - workflow-steps
"""


def _make_plugin(
    directory: Path,
    *,
    name: str = "hello-growth",
    entry: str = "hello_plugin:HelloPlugin",
    body: str | None = None,
    yaml_text: str | None = None,
) -> Path:
    """Write a minimal plugin directory; returns the plugin dir."""
    plugin_dir = directory / name
    plugin_dir.mkdir(parents=True)
    if yaml_text is None:
        yaml_text = (
            f"name: {name}\nversion: 0.1.0\ndescription: test plugin\nentry: {entry}\n"
        )
    (plugin_dir / "plugin.yaml").write_text(yaml_text, encoding="utf-8")
    (plugin_dir / "hello_plugin.py").write_text(
        body
        or (
            "class HelloPlugin:\n"
            f"    name = {name!r}\n"
            "    def __init__(self):\n"
            "        self.activated = False\n"
            "    def register(self, container):\n"
            "        self.activated = True\n"
        ),
        encoding="utf-8",
    )
    return plugin_dir


# -- manifest ---------------------------------------------------------------


class TestManifest:
    def test_valid_manifest(self) -> None:
        m = parse_plugin_manifest(VALID_YAML)
        assert m.name == "hello-growth"
        assert m.version == "0.1.0"
        assert m.description == "Greets on activation."
        assert m.entry == "hello_plugin:HelloPlugin"
        assert m.author == "Growth OS"
        assert m.permissions == ("workflow-steps",)

    def test_defaults(self) -> None:
        m = parse_plugin_manifest(
            "name: p1\nversion: '1.0'\ndescription: d\nentry: a:B\n"
        )
        assert m.author is None
        assert m.permissions == ()

    def test_invalid_yaml(self) -> None:
        with pytest.raises(PluginManifestError, match="invalid YAML"):
            parse_plugin_manifest("name: [unclosed\n")

    def test_non_mapping(self) -> None:
        with pytest.raises(PluginManifestError, match="mapping"):
            parse_plugin_manifest("- just\n- a list\n")

    @pytest.mark.parametrize("yaml_text", ["version: '1.0'\n", "name: 5\n"])
    def test_name_required_string(self, yaml_text: str) -> None:
        with pytest.raises(PluginManifestError, match="'name'"):
            parse_plugin_manifest(yaml_text)

    @pytest.mark.parametrize(
        "name", ["", "   ", ".", "..", "../evil", "a/b", "a\\b", "a:b", "a|b"]
    )
    def test_unsafe_names(self, name: str) -> None:
        with pytest.raises(PluginManifestError):
            parse_plugin_manifest(
                f"name: {name}\nversion: '1.0'\ndescription: d\nentry: a:B\n"
            )

    def test_name_length_cap(self) -> None:
        with pytest.raises(PluginManifestError, match="64"):
            parse_plugin_manifest(
                f"name: {'a' * 65}\nversion: '1.0'\ndescription: d\nentry: a:B\n"
            )

    def test_name_only_whitespace_is_empty(self) -> None:
        with pytest.raises(PluginManifestError, match="non-empty"):
            parse_plugin_manifest(
                "name: '   '\nversion: '1.0'\ndescription: d\nentry: a:B\n"
            )

    @pytest.mark.parametrize("field", ["version", "description", "entry"])
    def test_required_fields(self, field: str) -> None:
        lines = {
            "version": "name: p1\ndescription: d\nentry: a:B\n",
            "description": "name: p1\nversion: '1.0'\nentry: a:B\n",
            "entry": "name: p1\nversion: '1.0'\ndescription: d\n",
        }
        with pytest.raises(PluginManifestError, match=f"'{field}'"):
            parse_plugin_manifest(lines[field])

    def test_empty_version(self) -> None:
        with pytest.raises(PluginManifestError, match="'version'"):
            parse_plugin_manifest(
                "name: p1\nversion: '  '\ndescription: d\nentry: a:B\n"
            )

    @pytest.mark.parametrize(
        "entry",
        ["nocolon", ":Attr", "'mod:'", "1bad:Attr", "mod:1bad", "a:b:c"],
    )
    def test_bad_entry(self, entry: str) -> None:
        with pytest.raises(PluginManifestError, match="entry must be"):
            parse_plugin_manifest(
                f"name: p1\nversion: '1.0'\ndescription: d\nentry: {entry}\n"
            )

    def test_bad_permissions(self) -> None:
        with pytest.raises(PluginManifestError, match="permissions"):
            parse_plugin_manifest(
                "name: p1\nversion: '1.0'\ndescription: d\nentry: a:B\n"
                "permissions: [1, 2]\n"
            )

    def test_bad_author(self) -> None:
        with pytest.raises(PluginManifestError, match="author"):
            parse_plugin_manifest(
                "name: p1\nversion: '1.0'\ndescription: d\nentry: a:B\nauthor: 5\n"
            )


# -- load_plugins -------------------------------------------------------------


def test_load_plugins_missing_dir(tmp_path: Path) -> None:
    assert load_plugins(tmp_path / "nope") == []


def test_load_plugins_empty_dir(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    assert load_plugins(tmp_path) == []


def test_load_valid_plugin(tmp_path: Path) -> None:
    _make_plugin(tmp_path)
    loaded = load_plugins(tmp_path)
    assert len(loaded) == 1
    entry = loaded[0]
    assert entry.error is None
    assert entry.manifest is not None
    assert entry.manifest.name == "hello-growth"
    assert entry.instance is not None
    assert entry.instance.name == "hello-growth"
    assert entry.is_active


def test_load_ignores_non_directory_entries(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "plugin.yaml").write_text("stray file", encoding="utf-8")
    assert load_plugins(tmp_path) == []


def test_load_broken_manifest_is_isolated(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "bad"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.yaml").write_text("name: [unclosed\n", encoding="utf-8")
    loaded = load_plugins(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].manifest is None
    assert loaded[0].error is not None
    assert loaded[0].display_name == "bad"


def test_load_missing_entry_file(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "lonely"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.yaml").write_text(
        "name: lonely\nversion: '1.0'\ndescription: d\nentry: ghost:Ghost\n",
        encoding="utf-8",
    )
    loaded = load_plugins(tmp_path)
    assert loaded[0].instance is None
    assert "ghost.py" in (loaded[0].error or "")


def test_load_missing_attr(tmp_path: Path) -> None:
    _make_plugin(tmp_path, entry="hello_plugin:Missing")
    loaded = load_plugins(tmp_path)
    assert loaded[0].instance is None
    assert "Missing" in (loaded[0].error or "")


def test_load_syntax_error_is_isolated(tmp_path: Path) -> None:
    _make_plugin(tmp_path, body="def broken(:\n")
    loaded = load_plugins(tmp_path)
    assert loaded[0].instance is None
    assert loaded[0].error is not None


def test_load_non_plugin_class(tmp_path: Path) -> None:
    _make_plugin(
        tmp_path,
        body="class HelloPlugin:\n    name = 'hello-growth'\n",
    )
    loaded = load_plugins(tmp_path)
    assert loaded[0].instance is None
    assert "register" in (loaded[0].error or "")


def test_load_instance_not_class(tmp_path: Path) -> None:
    _make_plugin(
        tmp_path,
        entry="hello_plugin:instance",
        body=(
            "class HelloPlugin:\n"
            "    name = 'hello-growth'\n"
            "    def register(self, container):\n"
            "        pass\n"
            "instance = HelloPlugin()\n"
        ),
    )
    loaded = load_plugins(tmp_path)
    assert loaded[0].instance is not None
    assert loaded[0].error is None


def test_load_instance_without_name(tmp_path: Path) -> None:
    _make_plugin(
        tmp_path,
        body=(
            "class HelloPlugin:\n"
            "    def register(self, container):\n"
            "        pass\n"
        ),
    )
    loaded = load_plugins(tmp_path)
    assert loaded[0].instance is None
    assert "non-empty string 'name'" in (loaded[0].error or "")


def test_load_spec_unavailable_is_isolated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CPython refuses to build a spec -> isolated error, not a crash."""
    _make_plugin(tmp_path)
    monkeypatch.setattr(
        importlib.util,
        "spec_from_file_location",
        lambda *_args, **_kwargs: None,
    )
    loaded = load_plugins(tmp_path)
    assert loaded[0].instance is None
    assert "cannot import" in (loaded[0].error or "")


def test_load_duplicate_names_second_is_errored(tmp_path: Path) -> None:
    _make_plugin(tmp_path, name="dup")
    _make_plugin(tmp_path / "nested", name="dup")
    (tmp_path / "nested" / "dup").rename(tmp_path / "dup-2")
    # second directory name differs but manifest name collides
    loaded = load_plugins(tmp_path)
    assert len(loaded) == 2
    assert loaded[0].is_active
    assert loaded[1].error is not None
    assert "duplicate" in (loaded[1].error or "")


# -- activate_plugins ----------------------------------------------------------


class _Container:
    def __init__(self) -> None:
        self.settings = object()


def test_activate_calls_register(tmp_path: Path) -> None:
    _make_plugin(tmp_path)
    activated = activate_plugins(_Container(), tmp_path)
    assert activated[0].is_active
    assert activated[0].instance.activated is True


def test_activate_isolates_raising_register(tmp_path: Path) -> None:
    _make_plugin(
        tmp_path,
        body=(
            "class HelloPlugin:\n"
            "    name = 'hello-growth'\n"
            "    def register(self, container):\n"
            "        raise RuntimeError('boom')\n"
        ),
    )
    activated = activate_plugins(_Container(), tmp_path)
    assert activated[0].instance is not None
    assert "boom" in (activated[0].activation_error or "")


def test_activate_keeps_broken_plugins_in_results(tmp_path: Path) -> None:
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "plugin.yaml").write_text("name: [oops\n", encoding="utf-8")
    activated = activate_plugins(_Container(), tmp_path)
    assert len(activated) == 1
    assert activated[0].error is not None


# -- install / uninstall ---------------------------------------------------------


def test_install_copies_and_validates(tmp_path: Path) -> None:
    source = _make_plugin(tmp_path / "staging")
    target_dir = tmp_path / "plugins"
    manifest = install_plugin(source, target_dir)
    assert manifest.name == "hello-growth"
    assert (target_dir / "hello-growth" / "plugin.yaml").is_file()
    assert (target_dir / "hello-growth" / "hello_plugin.py").is_file()


def test_install_requires_directory(tmp_path: Path) -> None:
    file = tmp_path / "not-a-dir"
    file.write_text("x", encoding="utf-8")
    with pytest.raises(PluginInstallError, match="not a directory"):
        install_plugin(file, tmp_path / "plugins")


def test_install_requires_manifest(tmp_path: Path) -> None:
    bare = tmp_path / "bare"
    bare.mkdir()
    with pytest.raises(PluginInstallError, match=r"plugin\.yaml"):
        install_plugin(bare, tmp_path / "plugins")


def test_install_rejects_invalid_manifest(tmp_path: Path) -> None:
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "plugin.yaml").write_text("name: [oops\n", encoding="utf-8")
    with pytest.raises(PluginInstallError, match="invalid plugin manifest"):
        install_plugin(bad, tmp_path / "plugins")


def test_install_rejects_duplicate(tmp_path: Path) -> None:
    source = _make_plugin(tmp_path / "staging")
    target_dir = tmp_path / "plugins"
    install_plugin(source, target_dir)
    with pytest.raises(PluginInstallError, match="already installed"):
        install_plugin(source, target_dir)


def test_install_rejects_source_inside_plugins_dir(tmp_path: Path) -> None:
    target_dir = tmp_path / "plugins"
    inside = _make_plugin(target_dir, name="already-there")
    with pytest.raises(PluginInstallError, match="inside the plugins directory"):
        install_plugin(inside, target_dir)


def test_install_rolls_back_on_revalidation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _make_plugin(tmp_path / "staging")
    target_dir = tmp_path / "plugins"
    original_parse = "growth.plugins.loader.parse_plugin_manifest"
    real = parse_plugin_manifest
    calls = {"n": 0}

    def flaky(text: str) -> object:
        calls["n"] += 1
        if calls["n"] == 2:  # first = pre-copy validation, second = post-copy
            raise PluginManifestError("sabotaged")
        return real(text)

    monkeypatch.setattr(original_parse, flaky)
    with pytest.raises(PluginInstallError, match="rolled back"):
        install_plugin(source, target_dir)
    assert not (target_dir / "hello-growth").exists()


def test_uninstall_removes_directory(tmp_path: Path) -> None:
    source = _make_plugin(tmp_path / "staging")
    target_dir = tmp_path / "plugins"
    install_plugin(source, target_dir)
    removed = uninstall_plugin("hello-growth", target_dir)
    assert removed == target_dir / "hello-growth"
    assert not removed.exists()


def test_uninstall_missing_plugin(tmp_path: Path) -> None:
    with pytest.raises(PluginInstallError, match="not installed"):
        uninstall_plugin("ghost", tmp_path)


def test_uninstall_unsafe_name(tmp_path: Path) -> None:
    with pytest.raises(PluginManifestError):
        uninstall_plugin("../evil", tmp_path)
