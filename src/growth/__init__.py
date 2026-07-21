"""Growth OS — a personal growth operating system.

Public package layout (hexagonal):

- ``growth.domain``         — pure domain model. No I/O. No framework deps.
- ``growth.application``    — use cases and ports (interfaces).
- ``growth.infrastructure`` — adapter implementations (config, logging, AI, ...).
- ``growth.presentation``   — user-facing surfaces (CLI today; desktop later).
- ``growth.kernel``         — composition root (DI wiring).
- ``growth.plugins``        — extension contract.

Import-linter contracts enforce the dependency direction. See
``docs/adr/0001-hexagonal-architecture.md``.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def _resolve_version() -> str:
    """Resolve the installed package version, with a sane fallback.

    Returns:
        The package version string (PEP 440). Falls back to ``"0.0.0+unknown"``
        when the package is not installed (e.g., running from a source
        checkout without ``uv sync``).
    """

    try:
        return version("growth-os")
    except PackageNotFoundError:
        return "0.0.0+unknown"


__version__: str = _resolve_version()

__all__ = ["__version__"]
