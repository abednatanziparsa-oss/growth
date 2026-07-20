"""Application layer — use cases and ports.

This package is the dependency-inversion seam of the hexagon: it
defines the interfaces (ports) that adapters implement, and the use
cases that orchestrate them. import-linter forbids this package from
importing infrastructure or presentation.

Bootstrap scope: ports and DTO shells only. No use cases are
implemented yet — they land per roadmap phase.
"""

from __future__ import annotations
