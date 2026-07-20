"""Domain shared primitives — identity types used across all bounded contexts.

These are the only domain symbols that the bootstrap phase materializes;
aggregate roots (Workspace, Project, Goal, Milestone, Task) and the
execution model land in v0.1. Keeping this file minimal at bootstrap is
intentional (YAGNI): ports reference ``InternalId`` and ``SpaceId``, so
they exist now. Everything else grows when its first consumer appears.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID, uuid4

__all__ = ["DEFAULT_SPACE_ID", "InternalId", "SpaceId"]


class InternalId:
    """A stable, globally-unique identifier for any domain entity.

    Wraps a UUID to give identity a distinct type at the API boundary —
    so a function parameter named ``internal_id`` cannot be accidentally
    passed a provider resource id (a plain ``str``).

    The underlying value is a random UUID (UUIDv4) today. The roadmap
    (see docs/adr/0002-knowledge-centric-architecture.md) calls out a
    planned migration to UUIDv7 (time-sortable) once persistence lands,
    so callers must treat the value as opaque.

    Immutability:
        Instances are immutable. Equality and hashing are by underlying
        UUID value, so ``InternalId`` values can be used as dict keys
        and set members.
    """

    __slots__ = ("_value",)

    def __init__(self, value: UUID | None = None) -> None:
        """Initialize with an existing UUID, or generate a fresh one.

        Args:
            value: An existing UUID. When ``None`` (default), a new
                random UUID is generated.
        """

        self._value: Final[UUID] = value if value is not None else uuid4()

    @property
    def value(self) -> UUID:
        """The underlying UUID."""

        return self._value

    @classmethod
    def from_string(cls, raw: str) -> InternalId:
        """Parse an InternalId from its canonical hyphenated string form.

        Args:
            raw: A UUID string (any form accepted by ``UUID``).

        Returns:
            A new ``InternalId``.

        Raises:
            ValueError: If ``raw`` is not a valid UUID string.
        """

        return cls(UUID(raw))

    def __str__(self) -> str:
        return str(self._value)

    def __repr__(self) -> str:
        return f"InternalId({self._value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, InternalId):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)


class SpaceId:
    """Identifier for a *Space* — the owning dimension above Workspace.

    A Space separates contexts (e.g., personal vs. work) within a single
    installation. Bootstrap ships a single default Space; the seam is
    reserved now because retrofitting it later would touch every
    aggregate, table, and projection.

    See ``DEFAULT_SPACE_ID`` for the implicit owner when none is given.
    """

    __slots__ = ("_value",)

    def __init__(self, value: UUID | None = None) -> None:
        """Initialize with an existing UUID, or generate a fresh one.

        Args:
            value: An existing UUID. When ``None`` (default), a new
                random UUID is generated.
        """

        self._value: Final[UUID] = value if value is not None else uuid4()

    @property
    def value(self) -> UUID:
        """The underlying UUID."""

        return self._value

    def __str__(self) -> str:
        return str(self._value)

    def __repr__(self) -> str:
        return f"SpaceId({self._value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SpaceId):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)


#: The implicit owner for all entities at bootstrap. Single-user,
#: single-context. Phases that introduce multi-context use will start
#: creating additional SpaceIds.
DEFAULT_SPACE_ID: Final[SpaceId] = SpaceId(UUID(int=0))
