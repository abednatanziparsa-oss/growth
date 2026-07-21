"""Noop / default implementations of optional ports.

Every port that has an optional implementation gets a ``Noop*`` (or
``System*``) class here so the application runs fully offline at
bootstrap. When real implementations land (per roadmap phase), the
composition root chooses between Noop and real based on settings.

Why this matters: it enforces the "AI / Decision / Workflow are not
core dependencies" rule. If you can run the whole app with every
optional port set to Noop, then no feature is secretly hard-wired to
an external service.
"""

from __future__ import annotations
