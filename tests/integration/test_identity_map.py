"""Integration tests for IdentityMap."""

from __future__ import annotations

import sqlite3

from growth.domain.shared import InternalId
from growth.infrastructure.storage.identity_map import (
    IdentityMap,
    init_identity_map,
)


def _new_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    init_identity_map(db)
    return db


class TestIdentityMapBasic:
    def test_put_and_get(self) -> None:
        db = _new_db()
        im = IdentityMap(db)
        iid = InternalId()

        im.put(iid, "todoist", "t-123", "task")
        entry = im.get(iid, "todoist")

        assert entry is not None
        assert entry.internal_id.value == iid.value
        assert entry.provider == "todoist"
        assert entry.provider_resource_id == "t-123"
        assert entry.provider_resource_type == "task"

    def test_get_missing_returns_none(self) -> None:
        db = _new_db()
        im = IdentityMap(db)
        iid = InternalId()

        assert im.get(iid, "todoist") is None

    def test_put_updates_existing(self) -> None:
        db = _new_db()
        im = IdentityMap(db)
        iid = InternalId()

        im.put(iid, "todoist", "t-123", "task")
        im.put(iid, "todoist", "t-999", "project")

        entry = im.get(iid, "todoist")
        assert entry is not None
        assert entry.provider_resource_id == "t-999"
        assert entry.provider_resource_type == "project"

    def test_remove(self) -> None:
        db = _new_db()
        im = IdentityMap(db)
        iid = InternalId()

        im.put(iid, "todoist", "t-123", "task")
        im.remove(iid, "todoist")

        assert im.get(iid, "todoist") is None

    def test_remove_missing_noop(self) -> None:
        db = _new_db()
        im = IdentityMap(db)
        # Should not raise
        im.remove(InternalId(), "todoist")
        im.remove(InternalId(), "gcal")

    def test_find_by_provider_id(self) -> None:
        db = _new_db()
        im = IdentityMap(db)
        iid = InternalId()

        im.put(iid, "todoist", "t-abc", "task")

        found = im.find_by_provider_id("t-abc", "todoist")
        assert found is not None
        assert found.internal_id.value == iid.value

        missing = im.find_by_provider_id("no-such", "todoist")
        assert missing is None

    def test_list_by_provider(self) -> None:
        db = _new_db()
        im = IdentityMap(db)

        im.put(InternalId(), "todoist", "t-1", "task")
        im.put(InternalId(), "todoist", "t-2", "section")
        im.put(InternalId(), "gcal", "g-1", "event")

        todoist_entries = im.list_by_provider("todoist")
        assert len(todoist_entries) == 2

        gcal_entries = im.list_by_provider("gcal")
        assert len(gcal_entries) == 1
        assert gcal_entries[0].provider_resource_id == "g-1"

    def test_list_by_provider_empty(self) -> None:
        db = _new_db()
        im = IdentityMap(db)

        assert im.list_by_provider("unknown") == []

    def test_multiple_providers_isolation(self) -> None:
        db = _new_db()
        im = IdentityMap(db)
        iid = InternalId()

        im.put(iid, "todoist", "t-200", "task")

        # Same internal_id, different provider, different mapping
        im.put(iid, "gcal", "g-200", "event")

        te = im.get(iid, "todoist")
        ge = im.get(iid, "gcal")

        assert te is not None and te.provider_resource_id == "t-200"
        assert ge is not None and ge.provider_resource_id == "g-200"

    def test_remove_only_targets_specific_provider(self) -> None:
        db = _new_db()
        im = IdentityMap(db)
        iid = InternalId()

        im.put(iid, "todoist", "t-1", "task")
        im.put(iid, "gcal", "g-1", "event")

        im.remove(iid, "todoist")
        assert im.get(iid, "todoist") is None
        assert im.get(iid, "gcal") is not None  # gcal entry survived
