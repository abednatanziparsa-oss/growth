"""Plugin contract — minimal extension point.

Bootstrap scope (per refinement #1 in the approved plan): only the
``Plugin`` protocol. No registry, no discovery, no lifecycle, no loader.
Those arrive when at least two real plugins exist (YAGNI).

How plugins will work (future):
- A plugin is a class implementing ``Plugin``.
- It is registered via a Python entry point in its own package, under
  the ``growth.plugins`` group.
- The composition root (``growth.kernel``) discovers and instantiates
  plugins at startup, giving each a handle to register adapters into
  the appropriate ports.

Today, first-party adapters (Todoist, Markdown, ...) are wired directly
in ``growth.kernel.container`` as if they were plugins. The contract is
defined so that the future wiring shape is fixed, even though no
external plugin can register yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from growth.kernel.container import Container

__all__ = ["Plugin"]


@runtime_checkable
class Plugin(Protocol):
    """Contract for Growth OS plugins.

    A plugin receives the application ``Container`` and is free to
    register its own adapter implementations against any of the ports.
    Plugins must not mutate existing registrations destructively.

    Versioning: this protocol is the long-term public API for plugin
    authors. Breaking changes here require a Growth OS major version bump.
    """

    @property
    def name(self) -> str:
        """Stable, unique plugin identifier (e.g. ``"growth-todoist"``)."""
        ...

    def register(self, container: Container) -> None:
        """Wire this plugin's adapters into the application container.

        Called once at startup by the composition root. Implementations
        may read ``container.settings`` to decide what to register.
        """
        ...
