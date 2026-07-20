"""Infrastructure layer — adapter implementations of application ports.

This is where external systems are reached (Todoist API, file system,
SQLite, AI backends). import-linter forbids ``growth.application`` and
``growth.domain`` from importing anything here; only ``growth.kernel``
(the composition root) and ``growth.presentation`` may.

Subpackages are added per roadmap phase:

- ``config``      — Pydantic Settings (v0.1, this commit's sibling)
- ``logging``     — structlog setup (v0.1)
- ``events``      — synchronous EventBus (v0.1)
- ``noop``        — Noop implementations of every optional port (v0.1)
- ``parsers``     — YAML/Markdown/JSON/CSV/PDF parsers (v0.1+)
- ``interpreters``— Heuristic and LLM-assisted interpreters (v0.1+)
- ``projections`` — Todoist/Markdown/GCal projections (v0.1+)
- ``adapters``    — Provider adapters (v0.1+)
- ``storage``     — SQLite repositories (v0.1+)
- ``ai``          — Ollama/OpenAI/Anthropic backends (v0.6)
"""

from __future__ import annotations
