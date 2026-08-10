"""Sync engine — orchestrates the plan → provider synchronization pipeline.

Flow:
  1. Project: CanonicalPlan → desired ProviderSnapshot (via Projection)
  2. Fetch: pull live state from provider (via Adapter)
  3. Load base: last-synced snapshot (from sync_state table)
  4. Diff: desired vs base → ChangeSet (via Differ)
  5. Apply: execute ChangeSet on provider (via Adapter)
  6. Persist: save new base snapshot + identity mappings

The sync engine is the brain of v0.2. It coordinates the projection,
adapter, differ, and identity map but does not itself contain any
provider-specific logic.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from growth.application.dtos import (
    ApplyResult,
    CanonicalPlan,
    ChangeSet,
    ProviderSnapshot,
)
from growth.application.ports.projection import Projection
from growth.application.ports.provider_adapter import ProviderAdapter
from growth.domain.shared import InternalId
from growth.infrastructure.storage.identity_map import IdentityMap
from growth.infrastructure.sync.differ import Differ

__all__ = ["SyncEngine", "SyncResult", "init_sync_state"]


def init_sync_state(db: sqlite3.Connection) -> None:
    """Create the sync_state table for persisting base snapshots."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_state (
            provider TEXT PRIMARY KEY,
            base_snapshot TEXT NOT NULL,
            root_id TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.commit()


@dataclass(slots=True)
class SyncResult:
    """Outcome of a sync run."""

    provider: str
    root_id: str | None
    changeset: ChangeSet
    apply_result: ApplyResult
    created_at: datetime


class SyncEngine:
    """Orchestrate plan → provider synchronization.

    Args:
        projection: Maps a CanonicalPlan to a provider-shaped snapshot.
        adapter: Talks to the remote provider.
        identity_map: Persists InternalId ↔ provider resource id mappings.
        db: SQLite connection for persisting sync state.
    """

    def __init__(
        self,
        projection: Projection,
        adapter: ProviderAdapter,
        identity_map: IdentityMap,
        db: sqlite3.Connection,
    ) -> None:
        self._projection = projection
        self._adapter = adapter
        self._identity_map = identity_map
        self._db = db
        self._differ = Differ()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sync(self, plan: CanonicalPlan) -> SyncResult:
        """Run a full sync cycle: project → diff → apply → persist.

        Args:
            plan: The canonical plan to synchronize.

        Returns:
            ``SyncResult`` with the ChangeSet, ApplyResult, and timing.

        Raises:
            growth.application.errors.ProviderUnavailableError: If the
                provider cannot be reached.
        """
        # 1. Project the plan
        desired = self._projection.project(plan)

        # 2. Load the base (last-synced) snapshot
        base = self._load_base(desired.provider)

        # 3. Diff desired vs base → ChangeSet
        changeset = self._differ.diff(desired, base)

        if not changeset.operations:
            # Nothing to do — return empty result
            return SyncResult(
                provider=desired.provider,
                root_id=base.root_id if base else None,
                changeset=changeset,
                apply_result=ApplyResult(applied=0, failed=0),
                created_at=datetime.now(UTC),
            )

        # 4. Resolve placeholders in the ChangeSet (project_id, section_ids)
        self._resolve_placeholders(changeset, base)

        # 5. Apply the ChangeSet
        apply_result = self._adapter.apply(changeset)

        # 6. Persist the new base snapshot
        root_id = self._persist_base(desired, apply_result, base)

        # 7. Record identity mappings
        self._record_mappings(changeset, apply_result, desired.provider)

        return SyncResult(
            provider=desired.provider,
            root_id=root_id,
            changeset=changeset,
            apply_result=apply_result,
            created_at=datetime.now(UTC),
        )

    # ------------------------------------------------------------------
    # Base snapshot persistence
    # ------------------------------------------------------------------

    def _load_base(self, provider: str) -> ProviderSnapshot | None:
        """Load the last-synced snapshot from the sync_state table."""
        row = self._db.execute(
            "SELECT * FROM sync_state WHERE provider = ?", (provider,)
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["base_snapshot"])
        return ProviderSnapshot(
            provider=provider,
            root_id=row["root_id"],
            payload=payload,
        )

    def _persist_base(
        self,
        desired: ProviderSnapshot,
        apply_result: ApplyResult,
        base: ProviderSnapshot | None,
    ) -> str | None:
        """Save the new desired snapshot as the base for next sync.

        Returns the root_id (provider project id) if known.
        """
        # Determine root_id: use the one from apply_result if a project was created,
        # or reuse the existing one from base.
        root_id = None
        for _op_key, pid in apply_result.provider_ids.items():
            root_id = pid
            break  # first created project id is our root

        if root_id is None and base:
            root_id = base.root_id

        now = datetime.now(UTC).isoformat()
        self._db.execute(
            """
            INSERT INTO sync_state (provider, base_snapshot, root_id, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (provider) DO UPDATE SET
                base_snapshot = excluded.base_snapshot,
                root_id = excluded.root_id,
                updated_at = excluded.updated_at
            """,
            (desired.provider, json.dumps(desired.payload, default=str), root_id, now),
        )
        self._db.commit()
        return root_id

    # ------------------------------------------------------------------
    # Placeholder resolution
    # ------------------------------------------------------------------

    def _resolve_placeholders(
        self, changeset: ChangeSet, base: ProviderSnapshot | None
    ) -> None:
        """Walk the ChangeSet and replace __PROJECT__ / __SECTION_X__ placeholders.

        On first sync, project_id is a placeholder. After the create_project
        op succeeds, the sync engine sets it. For now, this is a pass-through
        since the apply step handles placeholders naively:
        - First op is always create_project (returns real project_id)
        - Caller pre-resolves or the adapter batches correctly.
        """
        # For v0.2 MVP: the placeholders are handled by ordering —
        # create_project runs first, subsequent ops reference the
        # returned id. The apply method processes ops sequentially.
        pass

    # ------------------------------------------------------------------
    # Identity mapping
    # ------------------------------------------------------------------

    def _record_mappings(
        self,
        changeset: ChangeSet,
        apply_result: ApplyResult,
        provider: str,
    ) -> None:
        """Persist InternalId ↔ provider resource id mappings."""
        for internal_id_str, provider_resource_id in apply_result.provider_ids.items():
            try:
                internal_id = InternalId.from_string(internal_id_str)
            except ValueError:
                continue

            # Determine resource type from the changeset op
            resource_type = "unknown"
            for op in changeset.operations:
                if op.get("internal_id") == internal_id_str:
                    op_name = op.get("op", "")
                    if "project" in op_name:
                        resource_type = "project"
                    elif "section" in op_name:
                        resource_type = "section"
                    elif "task" in op_name:
                        resource_type = "task"
                    break

            self._identity_map.put(internal_id, provider, provider_resource_id, resource_type)
