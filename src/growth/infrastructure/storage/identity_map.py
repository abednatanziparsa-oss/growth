"""Identity map — persists InternalId ↔ provider resource id mappings.

The identity map is the bridge between the canonical domain model and
the external provider's world. Every time the sync engine creates or
discovers a resource on a provider, it records the mapping here so that
the next diff knows what "already exists" looks like.

Table schema:
    internal_id: TEXT PRIMARY KEY — canonical InternalId (UUID string)
    provider: TEXT — e.g. "todoist", "markdown", "gcal"
    provider_resource_id: TEXT — the remote id (e.g. Todoist task id)
    provider_resource_type: TEXT — "project" | "section" | "task" | ...
    created_at: TEXT — ISO-8601 timestamp
    updated_at: TEXT — ISO-8601 timestamp
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import NamedTuple

from growth.domain.shared import InternalId

__all__ = ["IdentityMap", "IdentityMapEntry", "init_identity_map"]


class IdentityMapEntry(NamedTuple):
    """A single identity-mapping record."""

    internal_id: InternalId
    provider: str
    provider_resource_id: str
    provider_resource_type: str
    created_at: datetime
    updated_at: datetime


def init_identity_map(db: sqlite3.Connection) -> None:
    """Create the identity_map table if it does not already exist."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS identity_map (
            internal_id     TEXT NOT NULL,
            provider        TEXT NOT NULL,
            provider_resource_id TEXT NOT NULL,
            provider_resource_type TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            PRIMARY KEY (internal_id, provider)
        )
        """
    )
    db.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_identity_map_provider_resource
        ON identity_map (provider, provider_resource_id)
        """
    )
    db.commit()


class IdentityMap:
    """Repository for InternalId ↔ provider resource id mappings.

    All methods accept a ``provider`` filter so a single database can
    hold mappings for multiple providers (Todoist, Google Calendar, …).
    """

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Writers
    # ------------------------------------------------------------------

    def put(
        self,
        internal_id: InternalId,
        provider: str,
        provider_resource_id: str,
        provider_resource_type: str,
    ) -> None:
        """Insert or update a mapping."""
        now = datetime.now(UTC).isoformat()
        self._db.execute(
            """
            INSERT INTO identity_map (
                internal_id, provider, provider_resource_id,
                provider_resource_type, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (internal_id, provider) DO UPDATE SET
                provider_resource_id = excluded.provider_resource_id,
                provider_resource_type = excluded.provider_resource_type,
                updated_at = excluded.updated_at
            """,
            (
                str(internal_id),
                provider,
                provider_resource_id,
                provider_resource_type,
                now,
                now,
            ),
        )
        self._db.commit()

    def remove(self, internal_id: InternalId, provider: str) -> None:
        """Remove a mapping by internal id and provider."""
        self._db.execute(
            "DELETE FROM identity_map WHERE internal_id = ? AND provider = ?",
            (str(internal_id), provider),
        )
        self._db.commit()

    # ------------------------------------------------------------------
    # Readers
    # ------------------------------------------------------------------

    def get(self, internal_id: InternalId, provider: str) -> IdentityMapEntry | None:
        """Return the mapping for the given internal id and provider, or None."""
        row = self._db.execute(
            "SELECT * FROM identity_map WHERE internal_id = ? AND provider = ?",
            (str(internal_id), provider),
        ).fetchone()
        if row is None:
            return None
        return IdentityMapEntry(
            internal_id=InternalId.from_string(row["internal_id"]),
            provider=row["provider"],
            provider_resource_id=row["provider_resource_id"],
            provider_resource_type=row["provider_resource_type"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def find_by_provider_id(
        self, provider_resource_id: str, provider: str
    ) -> IdentityMapEntry | None:
        """Reverse-lookup: find the internal id for a given provider resource id."""
        row = self._db.execute(
            "SELECT * FROM identity_map WHERE provider_resource_id = ? AND provider = ?",
            (provider_resource_id, provider),
        ).fetchone()
        if row is None:
            return None
        return IdentityMapEntry(
            internal_id=InternalId.from_string(row["internal_id"]),
            provider=row["provider"],
            provider_resource_id=row["provider_resource_id"],
            provider_resource_type=row["provider_resource_type"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def list_by_provider(self, provider: str) -> list[IdentityMapEntry]:
        """Return all mappings for the given provider."""
        rows = self._db.execute(
            "SELECT * FROM identity_map WHERE provider = ? ORDER BY provider_resource_type",
            (provider,),
        ).fetchall()
        return [
            IdentityMapEntry(
                internal_id=InternalId.from_string(r["internal_id"]),
                provider=r["provider"],
                provider_resource_id=r["provider_resource_id"],
                provider_resource_type=r["provider_resource_type"],
                created_at=datetime.fromisoformat(r["created_at"]),
                updated_at=datetime.fromisoformat(r["updated_at"]),
            )
            for r in rows
        ]
