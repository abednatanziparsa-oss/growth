"""Minimal example Growth OS plugin (see examples/plugins/hello-growth).

Demonstrates the plugin contract from ``growth.plugins``: export a
class with a non-empty ``name`` and a ``register(container)`` method.
The composition root instantiates this class at startup and calls
``register`` once, with full failure isolation (a raising plugin is
reported and skipped, never fatal).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from growth.kernel.container import Container

__all__ = ["HelloPlugin"]


class HelloPlugin:
    """Logs a greeting when the plugin is activated."""

    name = "hello-growth"

    def __init__(self) -> None:
        self.activated = False

    def register(self, container: Container) -> None:
        """Announce activation (the simplest possible registration)."""
        logger = structlog.get_logger()
        logger.info("plugin.activated", plugin=self.name)
        self.activated = True
