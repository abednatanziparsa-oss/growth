"""Plugin manifest — validated ``plugin.yaml`` documents (v1.0 platform).

A plugin is a directory containing a ``plugin.yaml`` manifest plus its
code. The manifest is the marketplace's trust surface: it is validated
before anything is imported, and its ``permissions`` list is surfaced to
the user (advisory in this increment — plugins run with full user
privileges; see README "Plugins" for the honest trust model).

Manifest shape::

    name: hello-growth          # safe filename component (required)
    version: 0.1.0              # free-form string (required)
    description: ...            # human-readable summary (required)
    entry: hello_plugin:HelloPlugin   # file stem : exported class (required)
    author: ...                 # optional
    permissions: []             # optional, informational
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

__all__ = ["PluginManifest", "PluginManifestError", "parse_plugin_manifest"]

_ENTRY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: Characters that are unsafe in a single path component on Windows
#: (plus path separators and control characters).
_UNSAFE_NAME_CHARS = set('<>:"|?*')


class PluginManifestError(ValueError):
    """Raised when a ``plugin.yaml`` manifest is invalid."""


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """Validated plugin manifest."""

    name: str
    """Stable unique plugin id; also the install directory name."""

    version: str
    """Free-form version string (semver encouraged, not enforced)."""

    description: str
    """One-line human-readable summary."""

    entry: str
    """``<file_stem>:<ClassName>`` relative to the plugin directory."""

    author: str | None = None
    """Optional author name/org."""

    permissions: tuple[str, ...] = field(default_factory=tuple)
    """Capability names the plugin declares (informational in v1)."""


def validate_plugin_name(name: str) -> str:
    """Validate a plugin name as a safe single path component.

    Returns the stripped name; raises :class:`PluginManifestError` on
    anything that could escape the plugins directory or break Windows.
    """
    stripped = name.strip()
    if not stripped:
        raise PluginManifestError("plugin name must be a non-empty string")
    if any(ch in _UNSAFE_NAME_CHARS for ch in stripped) or any(
        ord(ch) < 32 for ch in stripped
    ):
        raise PluginManifestError(
            f"plugin name {name!r} contains characters that are unsafe "
            "in a path component"
        )
    if "/" in stripped or "\\" in stripped:
        raise PluginManifestError(
            f"plugin name {name!r} must not contain path separators"
        )
    if stripped in {".", ".."} or stripped.startswith("-"):
        raise PluginManifestError(f"plugin name {name!r} is not a safe name")
    if len(stripped) > 64:
        raise PluginManifestError("plugin name must be 64 characters or fewer")
    return stripped


def parse_plugin_manifest(text: str) -> PluginManifest:
    """Parse and validate a ``plugin.yaml`` document.

    Raises:
        PluginManifestError: On invalid YAML, missing/invalid required
            fields, unsafe names, or malformed ``entry`` references.
    """
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise PluginManifestError(f"invalid YAML: {exc}") from exc

    if not isinstance(doc, dict):
        raise PluginManifestError("plugin manifest must be a YAML mapping")

    raw_name = doc.get("name")
    if not isinstance(raw_name, str):
        raise PluginManifestError("plugin manifest requires a string 'name'")
    name = validate_plugin_name(raw_name)

    version = doc.get("version")
    if not isinstance(version, str) or not version.strip():
        raise PluginManifestError(
            f"plugin '{name}' requires a non-empty string 'version'"
        )

    description = doc.get("description")
    if not isinstance(description, str):
        raise PluginManifestError(f"plugin '{name}' requires a string 'description'")

    raw_entry = doc.get("entry")
    if not isinstance(raw_entry, str):
        raise PluginManifestError(
            f"plugin '{name}' requires a string 'entry' (module:ClassName)"
        )
    entry = raw_entry.strip()
    stem, sep, attr = entry.partition(":")
    if not sep or not _ENTRY_PATTERN.match(stem) or not _ENTRY_PATTERN.match(attr):
        raise PluginManifestError(
            f"plugin '{name}' entry must be '<file_stem>:<ClassName>' "
            f"with valid Python identifiers, got {raw_entry!r}"
        )

    author = doc.get("author")
    if author is not None and not isinstance(author, str):
        raise PluginManifestError(f"plugin '{name}' 'author' must be a string")

    raw_permissions = doc.get("permissions", [])
    if not isinstance(raw_permissions, list) or not all(
        isinstance(p, str) for p in raw_permissions
    ):
        raise PluginManifestError(
            f"plugin '{name}' 'permissions' must be a list of strings"
        )

    return PluginManifest(
        name=name,
        version=version.strip(),
        description=description.strip(),
        entry=entry,
        author=author,
        permissions=tuple(raw_permissions),
    )
