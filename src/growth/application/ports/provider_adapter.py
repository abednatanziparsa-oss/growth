"""Provider adapter port — executes a ChangeSet against a remote provider.

The adapter is the **only** place in the system that talks to an
external API (Todoist, Google Calendar, ...). The planner never imports
``todoist_api_python``; it depends on this port.

The adapter implements two operations:
- ``fetch_current`` — pull the live state of the provider (for diffing)
- ``apply``         — execute a ChangeSet (Create/Update/.../Delete)

Both are wrapped by the sync engine (v0.2) which handles identity
mapping, snapshots, diffs, and conflict resolution. The adapter itself
is dumb: it just translates generic ops into provider-specific API
calls and reports results.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from growth.application.dtos import ApplyResult, ChangeSet, ProviderSnapshot

__all__ = ["ProviderAdapter"]


@runtime_checkable
class ProviderAdapter(Protocol):
    """Adapter for a specific external provider.

    Implementations: ``TodoistAdapter`` (evolved from the MVP's
    ``todoist_client.py``), ``MarkdownAdapter`` (v0.3),
    ``GoogleCalendarAdapter`` (post-v0.5), ``ObsidianAdapter``.
    """

    @property
    def provider(self) -> str:
        """The provider name (matches the corresponding Projection)."""
        ...

    def fetch_current(self, root_id: str | None) -> ProviderSnapshot:
        """Return the live state of the provider's representation.

        Args:
            root_id: Provider-side id of the root resource, or ``None``
                if nothing has been synced yet (returns an empty snapshot).

        Raises:
            ProviderUnavailableError: If the provider cannot be reached.
        """
        ...

    def apply(self, changeset: ChangeSet) -> ApplyResult:
        """Execute ``changeset`` against the provider.

        Best-effort: ops that fail are recorded in the result rather
        than aborting the whole apply. Fatal errors (auth, network)
        raise ``ProviderUnavailableError``.

        Idempotency is the caller's responsibility (the sync engine
        ensures no-op changesets are not passed in), but the adapter
        should not duplicate-create if the same op is applied twice.

        Raises:
            ProviderUnavailableError: If the provider cannot be reached.
        """
        ...
