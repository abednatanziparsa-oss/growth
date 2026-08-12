"""Unit tests for PlanStore — plan history persistence."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from growth.domain.shared import DEFAULT_SPACE_ID, InternalId, SpaceId
from growth.infrastructure.storage.plan_store import PlanStore, init_plan_store


def _new_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    init_plan_store(db)
    return db


class TestPlanStore:
    def test_save_and_latest(self) -> None:
        db = _new_db()
        store = PlanStore(db)
        now = datetime.now(UTC)

        store.save(
            DEFAULT_SPACE_ID,
            "My Plan",
            {"project_name": "My Plan", "subjects": []},
            now,
        )

        stored = store.latest(DEFAULT_SPACE_ID)
        assert stored is not None
        assert stored.project_name == "My Plan"
        assert stored.raw_payload == {"project_name": "My Plan", "subjects": []}
        assert stored.space_id == DEFAULT_SPACE_ID
        assert stored.created_at == now

    def test_latest_returns_most_recent(self) -> None:
        db = _new_db()
        store = PlanStore(db)
        now = datetime.now(UTC)

        store.save(DEFAULT_SPACE_ID, "First", {"project_name": "First"}, now)
        store.save(DEFAULT_SPACE_ID, "Second", {"project_name": "Second"}, now)

        stored = store.latest(DEFAULT_SPACE_ID)
        assert stored is not None
        assert stored.project_name == "Second"

    def test_latest_empty_returns_none(self) -> None:
        db = _new_db()
        store = PlanStore(db)

        assert store.latest(DEFAULT_SPACE_ID) is None

    def test_latest_scoped_to_space(self) -> None:
        db = _new_db()
        store = PlanStore(db)
        other_space = SpaceId()

        store.save(other_space, "Other", {"project_name": "Other"}, datetime.now(UTC))

        assert store.latest(DEFAULT_SPACE_ID) is None
        assert store.latest(other_space) is not None

    def test_raw_payload_with_non_json_types(self) -> None:
        db = _new_db()
        store = PlanStore(db)
        internal_id = InternalId()

        store.save(
            DEFAULT_SPACE_ID,
            "Rich",
            {"project_name": "Rich", "owner": internal_id},
            datetime.now(UTC),
        )

        stored = store.latest(DEFAULT_SPACE_ID)
        assert stored is not None
        assert stored.raw_payload["owner"] == str(internal_id)
