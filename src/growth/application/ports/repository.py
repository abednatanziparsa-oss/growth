"""Repository port — generic persistence boundary.

Each bounded context will define its own concrete repository interface
(e.g. ``PlanRepository``, ``ExecutionRepository``) by sub-typing
``Repository[T]`` with the context's entity type. Bootstrap ships only
the generic shape so the pattern is established.

Why a port and not direct ORM usage: the hexagonal rule is that the
application layer must not know whether storage is SQLite, JSON files,
or Postgres. Phases can swap implementations without touching use cases.
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from growth.application.errors import PortError
from growth.domain.shared import InternalId

__all__ = ["EntityNotFoundError", "Repository", "T"]

T = TypeVar("T")


class EntityNotFoundError(PortError):
    """Raised by ``Repository.get`` when no entity matches the given id."""


@runtime_checkable
class Repository(Protocol[T]):
    """Generic persistence port for entities of type ``T``.

    All methods key off ``InternalId``. Concrete repositories may add
    query methods specific to their entity (e.g. ``find_by_space``); those
    are defined in the context that owns the entity, not here.
    """

    def get(self, id: InternalId) -> T:
        """Return the entity with the given id.

        Raises:
            EntityNotFoundError: If no entity has the given id.
        """
        ...

    def save(self, entity: T) -> None:
        """Persist ``entity`` (insert or update by id)."""
        ...

    def delete(self, id: InternalId) -> None:
        """Delete the entity with the given id.

        Raises:
            EntityNotFoundError: If no entity has the given id.
        """
        ...
