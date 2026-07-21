"""Centralized logging setup.

Wraps ``structlog`` over the standard library ``logging`` module so we
get structured, JSON-friendly log events with a clean developer
experience in the console. Two sinks are wired by default:

    - **Console**: human-friendly, colored, only when running in a TTY.
    - **File**:    JSON lines, appended to ``settings.log_file`` if set.

To add another sink (e.g., a remote aggregator), register a handler on
the ``growth`` logger — no other code changes required.

The function is idempotent: calling it multiple times reuses the
existing configuration rather than stacking handlers.
"""

from __future__ import annotations

import contextlib
import logging
import sys
from pathlib import Path
from typing import Final

import structlog
from structlog.types import EventDict, Processor

from growth.infrastructure.config.settings import Environment, Settings

__all__ = ["configure_logging", "get_logger"]


#: The top-level logger name used throughout the project. Every module
#: calls ``get_logger(__name__)`` and inherits this prefix.
APP_LOGGER_NAME: Final[str] = "growth"

#: Has logging been configured already? Prevents stacking handlers on
#: repeated calls (which happen in tests).
_configured: bool = False


def configure_logging(settings: Settings) -> None:
    """Configure structlog + stdlib logging based on ``settings``.

    Idempotent: subsequent calls are no-ops until ``reset_logging()``.

    Args:
        settings: Application settings (log_level, log_file, environment).
    """

    global _configured
    if _configured:
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # --- stdlib root logger -------------------------------------------------
    root = logging.getLogger()
    root.setLevel(level)

    # Console handler — always on; structlog renders it pretty in dev.
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(console_handler)

    # File handler — JSON lines, only when a path is configured.
    if settings.log_file is not None:
        log_path = Path(settings.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter('{"event": %(message)s}'))
        root.addHandler(file_handler)

    # --- structlog processors ----------------------------------------------
    # In development: pretty colored output. In testing/production: JSON.
    is_dev = settings.environment is Environment.DEVELOPMENT
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer: Processor = (
        structlog.dev.ConsoleRenderer(colors=is_dev)
        if is_dev
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _configured = True


def reset_logging() -> None:
    """Reset logging state — intended for tests only.

    Removes all handlers from the root logger and clears the
    ``_configured`` flag so the next ``configure_logging`` call wires
    handlers fresh.
    """

    global _configured
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        with contextlib.suppress(Exception):
            handler.close()
    structlog.reset_defaults()
    _configured = False


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to ``name`` (typically ``__name__``)."""

    return structlog.stdlib.get_logger(name)


def _drop_color_message(
    _logger: object, _method: str, event_dict: EventDict
) -> EventDict:
    """Strip the redundant ``color_message`` key added by uvicorn-style loggers."""

    event_dict.pop("color_message", None)
    return event_dict
