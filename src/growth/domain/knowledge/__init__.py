"""Knowledge bounded context — attachments, notes, and searchable content.

The knowledge substrate (v0.4) gives every planning entity the ability
to carry rich context: files, notes, and other artifacts that don't fit
in a title. This is the bridge to the Knowledge-Centric Architecture
(see docs/adr/0002): plans reference knowledge assets; assets are
searchable; search results feed back into planning.

Aggregates:
- **Attachment** — a file (or external reference) attached to a
  planning entity (Task, Goal, Milestone, Project) or to a Space.
- **KnowledgeNote** — a small free-text note attached to an entity.
  (Planned; not yet materialized.)

Design invariants:
- An attachment is immutable after creation: content is stored
  content-addressed (hash), and re-uploading the same bytes yields
  the same Attachment id.
- Attachments never store the source of truth — they reference it
  (local path, URL, asset id) so the system stays lightweight.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from hashlib import sha256

from growth.domain.shared import InternalId, SpaceId

__all__ = [
    "Attachment",
    "AttachmentKind",
    "AttachmentTarget",
    "content_hash",
]


class AttachmentKind(StrEnum):
    """The kind of content an attachment holds.

    Used to route search and rendering: a PDF is parsed differently
    from an image or a plain note.
    """

    FILE = "file"
    """A local or remote file (PDF, image, audio, ...)."""

    NOTE = "note"
    """A free-text note (no external file)."""

    URL = "url"
    """A reference to an external web resource."""

    EMBEDDING = "embedding"
    """A derived vector embedding of another attachment's content."""


class AttachmentTarget(StrEnum):
    """Which planning entity an attachment hangs off of."""

    TASK = "task"
    GOAL = "goal"
    MILESTONE = "milestone"
    PROJECT = "project"
    WORKSPACE = "workspace"
    SPACE = "space"


def content_hash(data: bytes) -> str:
    """Return the SHA-256 hex digest of ``data``.

    Content addressing: identical bytes produce identical ids. This is
    what makes re-attaching the same file a no-op.
    """

    return sha256(data).hexdigest()


@dataclass(kw_only=True, slots=True)
class Attachment:
    """A content-addressed artifact attached to a planning entity.

    The attachment stores *references* (local path / URL / asset id),
    never the content itself. The content hash is the stable identity
    for dedup and content-addressed storage.
    """

    id: InternalId = field(default_factory=InternalId)
    """Stable id. For content-addressed attachments this is derived from
    the hash; for notes/urls it is a fresh random id."""

    space_id: SpaceId
    """Owning space."""

    kind: AttachmentKind = AttachmentKind.FILE
    """What kind of content this is."""

    target_type: AttachmentTarget = AttachmentTarget.TASK
    """The kind of entity this is attached to."""

    target_id: InternalId | None = None
    """The specific entity id (None when space-scoped)."""

    title: str
    """Human-readable title (e.g. file name)."""

    content_hash: str | None = None
    """SHA-256 of the content, when content is available (dedup key)."""

    mime_type: str | None = None
    """MIME type hint (e.g. ``application/pdf``)."""

    source_ref: str | None = None
    """Where the content lives: local path, URL, or asset id."""

    size_bytes: int | None = None
    """Content size in bytes, when known."""

    content_text: str | None = None
    """Extracted text of the content (PDFs, office docs), when read.

    v0.6 enrichment: populated by a ``DocumentParser`` at attach time
    so documents become keyword- and semantically-searchable without
    storing the original bytes.
    """

    summary: str | None = None
    """AI-generated summary of ``content_text``, when requested."""

    created_at: datetime
    """Wall-clock creation time. Use the Clock port in real code."""

    updated_at: datetime
    """Wall-clock last-modification time."""
