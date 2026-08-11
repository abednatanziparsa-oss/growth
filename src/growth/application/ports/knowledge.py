"""Knowledge ports — attachment storage and search boundaries.

The knowledge substrate (v0.4) needs two seams:

- ``AttachmentRepository`` — persistence for Attachment aggregates.
- ``KnowledgeSearch`` — full-text / semantic search over knowledge
  content. v0.4 ships a keyword (LIKE-based) implementation; an
  embedding-based implementation lands with the AI substrate (v0.6).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from growth.domain.knowledge import Attachment, AttachmentTarget
from growth.domain.shared import InternalId, SpaceId

__all__ = [
    "AttachmentRepository",
    "AttachmentSearchResult",
    "KnowledgeSearch",
    "KnowledgeSearchError",
]


class KnowledgeSearchError(Exception):
    """Raised when a search cannot be executed (index missing, backend down)."""


@runtime_checkable
class AttachmentRepository(Protocol):
    """Persistence boundary for Attachment aggregates."""

    def get(self, id: InternalId) -> Attachment:
        """Return the attachment with the given id.

        Raises:
            EntityNotFoundError: If no attachment has the given id.
        """
        ...

    def save(self, attachment: Attachment) -> None:
        """Persist ``attachment`` (insert or update by id)."""
        ...

    def delete(self, id: InternalId) -> None:
        """Delete the attachment with the given id.

        Raises:
            EntityNotFoundError: If no attachment has the given id.
        """
        ...

    def list_by_target(
        self, target_type: AttachmentTarget, target_id: InternalId
    ) -> list[Attachment]:
        """Return all attachments attached to the given entity."""
        ...

    def list_by_space(self, space_id: SpaceId) -> list[Attachment]:
        """Return all attachments in a space, newest first."""
        ...

    def find_by_hash(self, content_hash: str) -> Attachment | None:
        """Return the attachment with the given content hash, if any.

        Content-addressing means re-attaching identical bytes should
        return the existing attachment instead of duplicating it.
        """
        ...


@runtime_checkable
class KnowledgeSearch(Protocol):
    """Search over the knowledge substrate."""

    def search(
        self,
        query: str,
        *,
        space_id: SpaceId | None = None,
        limit: int = 10,
    ) -> list[AttachmentSearchResult]:
        """Return attachments (and snippets) matching ``query``.

        Args:
            query: Free-text search query.
            space_id: Restrict search to a space when given.
            limit: Maximum number of results.

        Raises:
            KnowledgeSearchError: If the search backend fails.
        """
        ...


@runtime_checkable
class AttachmentSearchResult(Protocol):
    """A single search hit: attachment + matching snippet."""

    @property
    def attachment(self) -> Attachment:
        """The matching attachment."""
        ...

    @property
    def snippet(self) -> str:
        """A short excerpt of the matching content."""
        ...

    @property
    def score(self) -> float:
        """Relevance score (higher is better)."""
        ...
