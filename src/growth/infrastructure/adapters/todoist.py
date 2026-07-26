"""Todoist provider adapter — talks to the Todoist REST API.

Evolved from the MVP's ``todoist_client.py``, now implementing the
``ProviderAdapter`` port. Supports:
- ``fetch_current``: pull live state
- ``apply``: execute a ChangeSet
"""

from __future__ import annotations

from growth.application.dtos import ApplyResult, ChangeSet, ProviderSnapshot

__all__ = ["TodoistAdapter"]


class TodoistAdapter:
    """Todoist API adapter.

    v0.1: dry-run mode only (API calls are stubbed as no-op).
    v0.2: real API integration with the sync engine.
    """

    def __init__(self, api_token: str | None = None) -> None:
        self._api_token = api_token

    @property
    def provider(self) -> str:
        return "todoist"

    def fetch_current(self, root_id: str | None) -> ProviderSnapshot:
        """Return an empty snapshot (dry-run; real fetch in v0.2)."""
        return ProviderSnapshot(
            provider="todoist",
            root_id=root_id,
            payload={},
        )

    def apply(self, changeset: ChangeSet) -> ApplyResult:
        """Log what would be applied (dry-run; real apply in v0.2)."""
        return ApplyResult(
            applied=len(changeset.operations),
            failed=0,
            errors=[],
        )
