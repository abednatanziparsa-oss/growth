"""Plugin loader, installer, and activation (v1.0 platform).

Discovery and lifecycle for local plugins under
``~/.growth/plugins/<name>/`` (each with a ``plugin.yaml`` manifest —
see :mod:`growth.plugins.manifest`).

Design rules:

- **Failure isolation**: a broken plugin (bad manifest, syntax error,
  missing entry, non-plugin class, raising ``register``) never breaks
  the application — it is reported as an errored :class:`LoadedPlugin`
  and skipped, exactly like reminder sweep and workflow steps.
- **No global state**: plugin modules are imported via
  ``importlib.util.spec_from_file_location`` with unique module names —
  no ``sys.path`` mutation, no cross-test contamination.
- **Trust model**: plugins are regular Python code running with the
  user's full privileges; the manifest's ``permissions`` list is
  informational. Install only plugins you trust.
"""

from __future__ import annotations

import importlib.util
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from growth.plugins.manifest import (
    PluginManifest,
    PluginManifestError,
    parse_plugin_manifest,
    validate_plugin_name,
)

if TYPE_CHECKING:
    from growth.kernel.container import Container

__all__ = [
    "LoadedPlugin",
    "PluginInstallError",
    "activate_plugins",
    "install_plugin",
    "load_plugins",
    "uninstall_plugin",
]

_MANIFEST_FILENAME = "plugin.yaml"


class PluginInstallError(ValueError):
    """Raised when a plugin install/uninstall request is invalid."""


@dataclass(frozen=True, slots=True)
class LoadedPlugin:
    """One discovered plugin plus its load/activation outcome.

    ``instance`` is ``None`` (and ``error`` set) when discovery or
    import failed. ``activation_error`` is set when
    ``instance.register(container)`` raised.
    """

    source_dir: Path
    manifest: PluginManifest | None = None
    instance: Any = None
    error: str | None = None
    activation_error: str | None = None

    @property
    def is_active(self) -> bool:
        """``True`` when the plugin loaded and registered cleanly."""
        return self.instance is not None and self.error is None

    @property
    def display_name(self) -> str:
        """Best-effort identifier (manifest name, else directory name)."""
        if self.manifest is not None:
            return self.manifest.name
        return self.source_dir.name


def load_plugins(directory: Path) -> list[LoadedPlugin]:
    """Discover and import every plugin under ``directory``.

    Each direct subdirectory containing ``plugin.yaml`` is validated and
    imported. Failures are isolated: the returned list always has one
    entry per candidate directory, errored entries included.
    """
    if not directory.is_dir():
        return []

    results: list[LoadedPlugin] = []
    seen: set[str] = set()
    for manifest_path in sorted(directory.glob(f"*/{_MANIFEST_FILENAME}")):
        plugin_dir = manifest_path.parent
        try:
            manifest = parse_plugin_manifest(manifest_path.read_text(encoding="utf-8"))
        except (OSError, PluginManifestError) as exc:
            results.append(
                LoadedPlugin(source_dir=plugin_dir, error=f"invalid manifest: {exc}")
            )
            continue

        if manifest.name in seen:
            results.append(
                LoadedPlugin(
                    source_dir=plugin_dir,
                    manifest=manifest,
                    error=f"duplicate plugin name '{manifest.name}'",
                )
            )
            continue
        seen.add(manifest.name)

        instance, error = _instantiate(manifest, plugin_dir)
        results.append(
            LoadedPlugin(
                source_dir=plugin_dir,
                manifest=manifest,
                instance=instance,
                error=error,
            )
        )
    return results


def activate_plugins(container: Container, directory: Path) -> tuple[LoadedPlugin, ...]:
    """Load plugins and call ``register(container)`` on each valid one.

    A plugin whose ``register`` raises is recorded with
    ``activation_error`` and skipped; the application keeps running.
    """
    activated: list[LoadedPlugin] = []
    for loaded in load_plugins(directory):
        if loaded.instance is None or loaded.error is not None:
            activated.append(loaded)
            continue
        try:
            loaded.instance.register(container)
        except Exception as exc:  # plugin failure isolation
            activated.append(
                LoadedPlugin(
                    source_dir=loaded.source_dir,
                    manifest=loaded.manifest,
                    instance=loaded.instance,
                    activation_error=f"register failed: {exc}",
                )
            )
        else:
            activated.append(loaded)
    return tuple(activated)


def install_plugin(source: Path, plugins_dir: Path) -> PluginManifest:
    """Install (copy) a plugin directory into ``plugins_dir``.

    Validates the manifest before copying anything, refuses duplicate
    installs, and re-validates after the copy (defense in depth).
    Returns the installed manifest.
    """
    source = Path(source)
    if not source.is_dir():
        raise PluginInstallError(f"plugin source {source} is not a directory")

    manifest_path = source / _MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise PluginInstallError(f"{source} has no {_MANIFEST_FILENAME}")

    try:
        manifest = parse_plugin_manifest(manifest_path.read_text(encoding="utf-8"))
    except (OSError, PluginManifestError) as exc:
        raise PluginInstallError(f"invalid plugin manifest: {exc}") from exc

    resolved_source = source.resolve()
    resolved_root = plugins_dir.resolve()
    if resolved_source == resolved_root or resolved_root in resolved_source.parents:
        raise PluginInstallError(
            "refusing to install a plugin from inside the plugins directory"
        )

    target = plugins_dir / manifest.name
    if target.exists():
        raise PluginInstallError(
            f"plugin '{manifest.name}' is already installed at {target}"
        )

    plugins_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(resolved_source, target)

    try:
        return parse_plugin_manifest(
            (target / _MANIFEST_FILENAME).read_text(encoding="utf-8")
        )
    except (OSError, PluginManifestError) as exc:
        shutil.rmtree(target, ignore_errors=True)
        raise PluginInstallError(
            f"installed plugin failed re-validation, rolled back: {exc}"
        ) from exc


def uninstall_plugin(name: str, plugins_dir: Path) -> Path:
    """Remove an installed plugin directory. Returns the removed path."""
    stripped = validate_plugin_name(name)
    target = plugins_dir / stripped
    if not target.is_dir():
        raise PluginInstallError(f"plugin '{stripped}' is not installed")
    shutil.rmtree(target)
    return target


def _instantiate(manifest: PluginManifest, plugin_dir: Path) -> tuple[Any, str | None]:
    """Import the manifest entry and instantiate the plugin class.

    Returns ``(instance, None)`` on success or ``(None, error)`` on any
    failure — import errors, missing files/attributes, and classes that
    do not satisfy the Plugin contract all become error strings.
    """
    try:
        stem, attr = manifest.entry.split(":", 1)
        entry_file = plugin_dir / f"{stem}.py"
        if not entry_file.is_file():
            raise PluginManifestError(
                f"entry file '{stem}.py' not found in {plugin_dir.name}"
            )
        module_name = f"growth_plugin_{manifest.name}_{uuid.uuid4().hex[:8]}"
        spec = importlib.util.spec_from_file_location(module_name, entry_file)
        if spec is None or spec.loader is None:
            raise PluginManifestError(f"cannot import entry file '{stem}.py'")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        cls = getattr(module, attr, None)
        if cls is None:
            raise PluginManifestError(
                f"entry file '{stem}.py' does not export '{attr}'"
            )
        instance = cls() if isinstance(cls, type) else cls
        name = getattr(instance, "name", None)
        if not isinstance(name, str) or not name:
            raise PluginManifestError(
                f"'{attr}' does not expose a non-empty string 'name'"
            )
        if not callable(getattr(instance, "register", None)):
            raise PluginManifestError(
                f"'{attr}' does not expose a callable 'register(container)'"
            )
        return instance, None
    except Exception as exc:  # isolation boundary by design
        return None, f"{type(exc).__name__}: {exc}"
