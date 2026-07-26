"""Unit tests for the domain layer — pure business logic, no I/O.

Tests in this module never touch the file system, network, or database.
They exercise internal domain invariants in isolation.
"""

from __future__ import annotations

import uuid

from growth.domain.errors import (
    DomainError,
    InvalidPriorityError,
    InvalidTaskTreeError,
)
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId, SpaceId


class TestInternalId:
    """InternalId — identity value object."""

    def test_default_creates_fresh_uuid(self) -> None:
        """Calling InternalId() creates a new random UUID."""
        a = InternalId()
        b = InternalId()
        assert a.value != b.value
        assert isinstance(a.value, uuid.UUID)

    def test_from_explicit_uuid(self) -> None:
        """Passing a UUID preserves the value."""
        raw = uuid.uuid4()
        iid = InternalId(raw)
        assert iid.value == raw

    def test_from_string_roundtrip(self) -> None:
        """from_string parses the standard string form."""
        raw = uuid.uuid4()
        parsed = InternalId.from_string(str(raw))
        assert parsed.value == raw

    def test_equality(self) -> None:
        """Two InternalId with the same UUID are equal."""
        raw = uuid.uuid4()
        assert InternalId(raw) == InternalId(raw)

    def test_inequality(self) -> None:
        """Two InternalId with different UUIDs are not equal."""
        assert InternalId() != InternalId()

    def test_hashable(self) -> None:
        """InternalId can be used as a dict key."""
        d: dict[InternalId, str] = {}
        key = InternalId()
        d[key] = "value"
        assert d[key] == "value"

    def test_str_returns_uuid_string(self) -> None:
        """str() returns the hyphenated UUID form."""
        raw = uuid.uuid4()
        assert str(InternalId(raw)) == str(raw)


class TestSpaceId:
    """SpaceId — owning dimension identifier."""

    def test_default_space_id_is_zero_uuid(self) -> None:
        """The DEFAULT_SPACE_ID is the nil UUID."""
        assert DEFAULT_SPACE_ID.value == uuid.UUID(int=0)

    def test_equality(self) -> None:
        """SpaceId equality is value-based."""
        raw = uuid.uuid4()
        assert SpaceId(raw) == SpaceId(raw)

    def test_hashable(self) -> None:
        """SpaceId works as a dict key."""
        d: dict[SpaceId, str] = {}
        key = SpaceId()
        d[key] = "value"
        assert d[key] == "value"


class TestDomainErrors:
    """Domain error hierarchy."""

    def test_domain_error_is_exception(self) -> None:
        """DomainError is a proper Exception subclass."""
        assert issubclass(DomainError, Exception)

        try:
            raise DomainError("test")
        except DomainError as e:
            assert str(e) == "test"

    def test_invalid_priority_error(self) -> None:
        """InvalidPriorityError inherits from DomainError."""
        assert issubclass(InvalidPriorityError, DomainError)

    def test_invalid_task_tree_error(self) -> None:
        """InvalidTaskTreeError inherits from DomainError."""
        assert issubclass(InvalidTaskTreeError, DomainError)
