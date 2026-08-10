"""Integration tests for SyncEngine — end-to-end sync pipeline.

Uses a stub adapter (in-memory) so no real Todoist API calls are made.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from growth.application.dtos import (
    ApplyResult,
    CanonicalPlan,
    ChangeSet,
    ProviderSnapshot,
)
from growth.domain.shared import DEFAULT_SPACE_ID
from growth.infrastructure.storage.identity_map import (
    IdentityMap,
    init_identity_map,
)
from growth.infrastructure.sync.engine import SyncEngine, SyncResult, init_sync_state

# =============================================================================
# Stub Projection — returns predictable empty snapshots
# =============================================================================


class _StubProjection:
    provider = "todoist"

    def project(self, plan: CanonicalPlan) -> ProviderSnapshot:
        return ProviderSnapshot(
            provider="todoist",
            root_id=None,
            payload={
                "project_name": plan.project_name,
                "sections": [],
                "items": [],
            },
        )


class _RichProjection:
    provider = "todoist"

    def project(self, plan: CanonicalPlan) -> ProviderSnapshot:
        return ProviderSnapshot(
            provider="todoist",
            root_id=None,
            payload={
                "project_name": plan.project_name,
                "sections": [{"name": "Section A"}],
                "items": [
                    {"content": "Task 1", "priority": 3, "subtasks": []}
                ],
            },
        )


# =============================================================================
# Stub Adapter — records what was called, returns controlled results
# =============================================================================


class _StubAdapter:
    provider = "todoist"

    def __init__(self) -> None:
        self.fetch_calls: list[str | None] = []
        self.apply_calls: list[ChangeSet] = []
        self.fetch_result: ProviderSnapshot | None = None
        self._apply_result: ApplyResult | None = None

    def fetch_current(self, root_id: str | None) -> ProviderSnapshot:
        self.fetch_calls.append(root_id)
        if self.fetch_result is not None:
            return self.fetch_result
        return ProviderSnapshot(provider="todoist", root_id=root_id, payload={})

    @property
    def apply_result(self) -> ApplyResult:
        if self._apply_result is not None:
            return self._apply_result
        # Default: return applied=count of ops in the last changeset
        if self.apply_calls:
            cs = self.apply_calls[-1]
            return ApplyResult(applied=len(cs.operations), failed=0)
        return ApplyResult(applied=0, failed=0)

    @apply_result.setter
    def apply_result(self, value: ApplyResult) -> None:
        self._apply_result = value

    def apply(self, changeset: ChangeSet) -> ApplyResult:
        self.apply_calls.append(changeset)
        if self._apply_result is not None:
            return self._apply_result
        return ApplyResult(applied=len(changeset.operations), failed=0)


# =============================================================================
# Helpers
# =============================================================================


def _new_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    init_identity_map(db)
    init_sync_state(db)
    return db


def _make_plan(name: str = "Test Plan") -> CanonicalPlan:
    return CanonicalPlan(
        space_id=DEFAULT_SPACE_ID,
        created_at=datetime.now(UTC),
        project_name=name,
    )


# =============================================================================
# Tests
# =============================================================================


class TestSyncEngineFirstSync:
    """First sync — no base snapshot exists."""

    def test_first_sync_with_empty_changeset_returns_result(self) -> None:
        db = _new_db()
        projection = _StubProjection()
        adapter = _StubAdapter()
        im = IdentityMap(db)
        engine = SyncEngine(projection, adapter, im, db)

        result = engine.sync(_make_plan())

        assert result.provider == "todoist"
        assert result.apply_result.failed == 0
        # _StubProjection with empty sections/items still produces create_project
        assert result.apply_result.applied >= 1

    def test_first_sync_persists_base(self) -> None:
        db = _new_db()
        projection = _RichProjection()
        adapter = _StubAdapter()
        im = IdentityMap(db)
        engine = SyncEngine(projection, adapter, im, db)

        result = engine.sync(_make_plan("Persist Test"))
        assert result.apply_result.applied > 0  # at minimum one create_project

        # Verify base was persisted
        row = db.execute(
            "SELECT * FROM sync_state WHERE provider = ?", ("todoist",)
        ).fetchone()
        assert row is not None

    def test_sync_with_stub_noop_idempotent(self) -> None:
        """Second sync with same plan (no changes) should produce zero ops."""
        db = _new_db()
        projection = _StubProjection()
        adapter = _StubAdapter()
        im = IdentityMap(db)
        engine = SyncEngine(projection, adapter, im, db)

        # First sync
        engine.sync(_make_plan("Same"))
        # Second sync — base should match desired, so no ops
        r2 = engine.sync(_make_plan("Same"))

        assert r2.changeset.operations == []
        assert r2.apply_result.applied == 0


class TestSyncEngineBasePersistence:
    """Sync state persistence across runs."""

    def test_base_persisted_and_reloaded(self) -> None:
        db = _new_db()
        projection = _RichProjection()
        adapter = _StubAdapter()
        im = IdentityMap(db)
        engine = SyncEngine(projection, adapter, im, db)

        engine.sync(_make_plan("Plan A"))

        # New engine on same db should load the base
        engine2 = SyncEngine(projection, adapter, im, db)
        base = engine2._load_base("todoist")
        assert base is not None
        assert base.payload.get("project_name") == "Plan A"

    def test_no_base_for_unknown_provider(self) -> None:
        db = _new_db()
        engine = SyncEngine(
            _StubProjection(), _StubAdapter(), IdentityMap(db), db
        )

        base = engine._load_base("nonexistent")
        assert base is None


class TestSyncEngineResult:
    """SyncResult structure correctness."""

    def test_empty_sync_result_shape(self) -> None:
        db = _new_db()
        engine = SyncEngine(
            _StubProjection(), _StubAdapter(), IdentityMap(db), db
        )

        result = engine.sync(_make_plan())

        assert isinstance(result, SyncResult)
        assert result.provider == "todoist"
        assert isinstance(result.changeset, ChangeSet)
        assert isinstance(result.apply_result, ApplyResult)
        assert result.created_at is not None
