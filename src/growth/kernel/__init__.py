"""Kernel — composition root (dependency injection wiring).

This is the **only** place in the codebase where concrete adapter
implementations meet application ports. ``Container`` builds a wired
object graph from ``Settings``; ``bootstrap.build_app`` configures
logging and returns a runnable ``App``.

Import-linter forbids ``growth.application`` from importing ``kernel``,
which means use cases receive their dependencies as constructor
parameters — they never reach into the container themselves.
"""

from __future__ import annotations
