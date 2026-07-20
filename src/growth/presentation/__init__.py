"""Presentation layer — user-facing surfaces.

Today: CLI (Typer). Future: TUI (Textual), desktop (PySide6).

The presentation layer may only call application use cases. It must
not import infrastructure directly (enforced by import-linter). All
adapter wiring happens in ``growth.kernel``.
"""

from __future__ import annotations
