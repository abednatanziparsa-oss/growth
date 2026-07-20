"""Application ports — the interfaces that adapters implement.

Each port is a ``Protocol`` (PEP 544). Implementations live in
``growth.infrastructure``. Application use cases depend on these
Protocols, never on concrete adapter classes.

This package is the seam the architecture review (doc 2) demanded:
every future engine (Decision, Workflow, AI Orchestration) has a
reserved slot here. Bootstrap provides Noop implementations so the
system runs fully offline today.

Importing a port module is free; importing an implementation is not,
except inside ``growth.kernel`` (the composition root).
"""

from __future__ import annotations
