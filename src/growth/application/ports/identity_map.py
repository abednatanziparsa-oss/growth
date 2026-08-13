"""Identity-map port — persistence of InternalId ↔ provider resource ids.

Application use cases (e.g. calendar sync) need to remember which
provider resource corresponds to which canonical entity, but must not
depend on the infrastructure implementation. This port exposes the
narrow slice those use cases need.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from growth.domain.shared import InternalId

__all__ = ["IdentityMapPort", "ProviderMapping"]


@dataclass(frozen=True, slots=True)
class ProviderMapping:
    """A canonical-entity to provider-resource mapping (application view)."""

    provider_resource_id: str
    provider_resource_type: str


@runtime_checkable
class IdentityMapPort(Protocol):
    """Persists InternalId ↔ provider resource id mappings (per provider)."""

    def get(self, internal_id: InternalId, provider: str) -> ProviderMapping | None:
        """Return the mapping for the given internal id and provider, or None."""
        ...

    def put(
        self,
        internal_id: InternalId,
        provider: str,
        provider_resource_id: str,
        provider_resource_type: str,
    ) -> None:
        """Insert or update a mapping."""
        ...
