"""Additional SyncEngine tests — identity mapping, root_id persistence, placeholders."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from growth.application.dtos import (
    ApplyResult,
    CanonicalPlan,
    ChangeSet,
    ProviderSnapshot,
)
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId
from growth.infrastructure.storage.identity_map import (
    IdentityMap,
    init_identity_map,
)
from growth.infrastructure.sync.engine import SyncEngine, init_sync_state


class _StubProjection:
    provider = "todoist"

    def __init__(self, sections: list[dict[str, str]] | None = None) -> None:
        self._sections = sections or []

    def project(self, plan: CanonicalPlan) -> ProviderSnapshot:
        return ProviderSnapshot(
            provider="todoist",
            root_id=None,
            payload={
                "project_name": plan.project_name,
                "sections": self._sections,
                "items": [],
            },
        )


class _StubAdapter:
    provider = "todoist"

    def __init__(self, result: ApplyResult) -> None:
        self._result = result
        self.applied_changesets: list[ChangeSet] = []

    def fetch_current(self, root_id: str | None) -> ProviderSnapshot:
        return ProviderSnapshot(provider="todoist", root_id=root_id, payload={})

    def apply(self, changeset: ChangeSet) -> ApplyResult:
        self.applied_changesets.append(changeset)
        return self._result


def _new_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    init_identity_map(db)
    init_sync_state(db)
    return db


def _make_plan(name: str = "Plan") -> CanonicalPlan:
    return CanonicalPlan(
        space_id=DEFAULT_SPACE_ID,
        created_at=datetime.now(UTC),
        project_name=name,
    )


class TestSyncEngineRootId:
    def test_root_id_taken_from_first_provider_id(self) -> None:
        db = _new_db()
        internal_id = InternalId()
        adapter = _StubAdapter(
            ApplyResult(
                applied=2,
                failed=0,
                provider_ids={str(internal_id): "proj-42"},
            )
        )
        engine = SyncEngine(_StubProjection(), adapter, IdentityMap(db), db)

        result = engine.sync(_make_plan())

        assert result.root_id == "proj-42"
        row = db.execute(
            "SELECT root_id FROM sync_state WHERE provider = 'todoist'"
        ).fetchone()
        assert row["root_id"] == "proj-42"

    def test_root_id_falls_back_to_base(self) -> None:
        db = _new_db()
        adapter = _StubAdapter(ApplyResult(applied=1, failed=0))
        engine = SyncEngine(_StubProjection(), adapter, IdentityMap(db), db)

        # First sync: no provider ids → root stays None
        engine.sync(_make_plan("First"))
        row = db.execute(
            "SELECT root_id FROM sync_state WHERE provider = 'todoist'"
        ).fetchone()
        assert row["root_id"] is None

    def test_empty_changeset_keeps_base_root_id(self) -> None:
        db = _new_db()
        # First sync creates a project (root_id recorded)
        internal_id = InternalId()
        adapter = _StubAdapter(
            ApplyResult(applied=1, provider_ids={str(internal_id): "proj-7"})
        )
        engine = SyncEngine(_StubProjection(), adapter, IdentityMap(db), db)
        engine.sync(_make_plan("Stable"))

        # Second sync: same plan → no ops → early return with base root_id
        adapter2 = _StubAdapter(ApplyResult(applied=0))
        engine2 = SyncEngine(_StubProjection(), adapter2, IdentityMap(db), db)
        result = engine2.sync(_make_plan("Stable"))

        assert result.changeset.operations == []
        assert result.apply_result.applied == 0
        assert result.root_id == "proj-7"


class TestSyncEngineIdentityMapping:
    def test_record_mappings_skips_invalid_internal_ids(self) -> None:
        db = _new_db()
        engine = SyncEngine(
            _StubProjection(), _StubAdapter(ApplyResult(0)), IdentityMap(db), db
        )

        engine._record_mappings(
            ChangeSet(provider="todoist", operations=[]),
            ApplyResult(applied=0, provider_ids={"not-a-uuid": "x-1"}),
            "todoist",
        )

        assert IdentityMap(db).list_by_provider("todoist") == []

    def test_record_mappings_classifies_resource_types(self) -> None:
        db = _new_db()
        im = IdentityMap(db)
        engine = SyncEngine(_StubProjection(), _StubAdapter(ApplyResult(0)), im, db)

        id_proj = InternalId()
        id_sec = InternalId()
        id_task = InternalId()
        id_other = InternalId()

        changeset = ChangeSet(
            provider="todoist",
            operations=[
                {"op": "create_project", "internal_id": str(id_proj)},
                {"op": "create_section", "internal_id": str(id_sec)},
                {"op": "create_task", "internal_id": str(id_task)},
                {"op": "weird_thing", "internal_id": str(id_other)},
            ],
        )
        engine._record_mappings(
            changeset,
            ApplyResult(
                applied=4,
                provider_ids={
                    str(id_proj): "p-1",
                    str(id_sec): "s-1",
                    str(id_task): "t-1",
                    str(id_other): "w-1",
                },
            ),
            "todoist",
        )

        by_type = {e.provider_resource_type: e for e in im.list_by_provider("todoist")}
        assert by_type["project"].provider_resource_id == "p-1"
        assert by_type["section"].provider_resource_id == "s-1"
        assert by_type["task"].provider_resource_id == "t-1"
        assert by_type["unknown"].provider_resource_id == "w-1"

    def test_record_mappings_updates_existing_entry(self) -> None:
        db = _new_db()
        im = IdentityMap(db)
        engine = SyncEngine(_StubProjection(), _StubAdapter(ApplyResult(0)), im, db)
        internal_id = InternalId()

        for pid in ("old-id", "new-id"):
            engine._record_mappings(
                ChangeSet(
                    provider="todoist",
                    operations=[{"op": "create_task", "internal_id": str(internal_id)}],
                ),
                ApplyResult(applied=1, provider_ids={str(internal_id): pid}),
                "todoist",
            )

        entries = im.list_by_provider("todoist")
        assert len(entries) == 1
        assert entries[0].provider_resource_id == "new-id"


class TestSyncEnginePlaceholders:
    def test_resolve_placeholders_is_pass_through(self) -> None:
        db = _new_db()
        engine = SyncEngine(
            _StubProjection(), _StubAdapter(ApplyResult(0)), IdentityMap(db), db
        )
        cs = ChangeSet(
            provider="todoist",
            operations=[{"op": "create_section", "project_id": "__PROJECT__"}],
        )

        engine._resolve_placeholders(cs, None)

        assert cs.operations[0]["project_id"] == "__PROJECT__"

    def test_sync_calls_apply_with_resolved_changeset(self) -> None:
        db = _new_db()
        adapter = _StubAdapter(ApplyResult(applied=1))
        engine = SyncEngine(_StubProjection(), adapter, IdentityMap(db), db)

        engine.sync(_make_plan())

        assert len(adapter.applied_changesets) == 1
        assert adapter.applied_changesets[0].operations[0]["op"] == "create_project"
