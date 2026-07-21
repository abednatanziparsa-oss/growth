"""Composition root entry point — build a runnable ``App`` from settings.

``build_app`` is what presentation-layer code (CLI today, desktop later)
calls to obtain a fully-wired application object. It:

    1. Loads ``Settings`` from environment / .env.
    2. Configures logging (structlog + file handler).
    3. Constructs the DI ``Container``.
    4. Wraps both in an ``App`` facade.

This is the only function outside ``kernel.container`` that knows about
concrete adapter classes — and it delegates to ``Container.from_settings``
for the actual wiring.
"""

from __future__ import annotations

from dataclasses import dataclass

from growth.infrastructure.config.settings import Settings
from growth.infrastructure.logging.setup import configure_logging
from growth.kernel.container import Container

__all__ = ["App", "build_app"]


@dataclass(slots=True)
class App:
    """Runnable application facade: settings + wired container."""

    settings: Settings
    container: Container


def build_app(settings: Settings | None = None) -> App:
    """Build a runnable ``App``.

    Args:
        settings: Explicit settings, or ``None`` to load from environment.

    Returns:
        An ``App`` with logging configured and the DI container wired.
    """

    if settings is None:
        settings = Settings()

    configure_logging(settings)
    container = Container.from_settings(settings)
    return App(settings=settings, container=container)
