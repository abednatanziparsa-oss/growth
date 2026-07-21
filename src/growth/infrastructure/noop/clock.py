"""Real-time clock implementation of the ``Clock`` port.

Not a Noop (it returns the actual wall clock). The ``Clock`` port has
no "off" mode — every use case that needs time gets this implementation
in production and a ``FakeClock`` in tests.
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["SystemClock"]


class SystemClock:
    """Production ``Clock`` implementation backed by ``datetime.now()``."""

    def now_utc(self) -> datetime:
        """Return the current timezone-aware UTC time."""

        return datetime.now(UTC)
