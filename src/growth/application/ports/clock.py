"""Clock port — abstracts wall-clock time so domain logic is testable.

The domain must never call ``datetime.now()`` directly. Instead it
depends on this port; the composition root injects a real
``SystemClock`` (or a ``FakeClock`` in tests). This is the standard
hexagonal pattern for the "time" external dependency.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

__all__ = ["Clock"]


@runtime_checkable
class Clock(Protocol):
    """Provides the current wall-clock time.

    All timestamps in the system are UTC (timezone-aware). Render to
    local time only at projection boundaries (e.g., when emitting a
    Todoist due date).
    """

    def now_utc(self) -> datetime:
        """Return the current time as a timezone-aware UTC ``datetime``."""
        ...


def utc_now() -> datetime:
    """Convenience helper: return the current UTC time.

    Use only in places that cannot reasonably take a ``Clock`` dependency
    (e.g., module-level constants or ``__post_init__`` defaults). Real
    domain code should accept a ``Clock`` parameter.
    """

    return datetime.now(UTC)
