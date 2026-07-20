"""Data Transfer Objects (DTOs) shared across ports.

These are *transport shapes*, not domain aggregates. They are intentionally
minimal at bootstrap — just enough structure for the port method signatures
to type-check. Each one will be fleshed out in the phase that first needs
its fields (see ROADMAP.md).

Conventions:
- DTOs are frozen dataclasses (value semantics; safe to pass around).
- DTOs never contain behaviour — only data.
- DTOs at boundaries may be Pydantic models; DTOs internal to a port
  contract are plain dataclasses to keep the domain framework-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from growth.domain.shared import InternalId, SpaceId

# =============================================================================
# Ingestion DTOs
# =============================================================================


@dataclass(frozen=True, slots=True)
class RawPlan:
    """Format-neutral intermediate representation produced by parsers.

    The Extract stage of the two-stage ingestion pipeline (see
    docs/architecture/ARCHITECTURE.md) produces this. Interpreters then
    map it to a ``CanonicalPlan``.

    Bootstrap: a thin shell. Fields are added as parsers grow.
    """

    source_format: str
    """The format the raw plan was extracted from (e.g. ``"yaml"``, ``"pdf"``)."""

    payload: dict[str, Any]
    """The parsed content as a plain dict, ready for an interpreter to lift."""

    source_ref: str | None = None
    """Optional reference to the origin (file path, URL, asset id)."""


# =============================================================================
# Planning DTOs
# =============================================================================


@dataclass(frozen=True, slots=True)
class CanonicalPlan:
    """The canonical plan model — provider-agnostic intended state.

    This is what gets diffed and projected. Bootstrap ships a minimal
    shell: identity + a space reference. The real aggregate hierarchy
    (Workspace → Project → Goal → Milestone → Task tree) lands in v0.1.

    The plan is *intended* state, distinct from *observed* state
    (Execution) and *projected* state (provider snapshots). See
    docs/adr/0002-knowledge-centric-architecture.md.
    """

    id: InternalId
    space_id: SpaceId
    created_at: datetime
    """Wall-clock creation time. Use the Clock port in real code; tests inject."""

    # TODO(v0.1): workspace, projects, goals, milestones, task tree.


# =============================================================================
# Sync DTOs
# =============================================================================


@dataclass(frozen=True, slots=True)
class ProviderSnapshot:
    """The desired shape of a plan in a specific provider's vocabulary.

    Produced by a ``Projection`` (pure function, no I/O). The Differ
    compares two snapshots to compute a ``ChangeSet``.

    Bootstrap: opaque payload. Concrete projections (Todoist, Markdown,
    Google Calendar) define their own richer shapes internally and
    serialize into this for diffing.
    """

    provider: str
    """Provider name, e.g. ``"todoist"``, ``"markdown"``, ``"gcal"``."""

    root_id: str | None
    """Provider-side id of the root resource, or ``None`` if not yet created."""

    payload: dict[str, Any]
    """Provider-shaped tree of resources (projects, sections, tasks, ...)."""


@dataclass(frozen=True, slots=True)
class ChangeSet:
    """Provider-agnostic list of operations produced by the Differ.

    Each operation is one of: Create, Update, Rename, Delete, Archive, Move.
    Bootstrap carries them as opaque dicts; the sync engine (v0.2) will
    type them as a small union of frozen dataclasses.

    Idempotency invariant (enforced by the v0.2 engine): applying an
    empty ChangeSet issues zero remote calls; applying the same ChangeSet
    twice has the same effect as applying it once.
    """

    provider: str
    """Target provider name."""

    operations: list[dict[str, Any]] = field(default_factory=list)
    """Ordered ops. Each dict has at least ``{"op": ..., "internal_id": ...}``."""


@dataclass(frozen=True, slots=True)
class ApplyResult:
    """Outcome of applying a ChangeSet through a provider adapter.

    Records what actually happened on the remote, including new provider
    resource ids (for the IdentityMap) and any per-op failures.
    """

    applied: int
    """Number of operations successfully applied."""

    failed: int = 0
    """Number of operations that failed (non-fatal; see ``errors``)."""

    provider_ids: dict[str, str] = field(default_factory=dict)
    """Mapping of internal_id -> provider resource id for created resources."""

    errors: list[str] = field(default_factory=list)
    """Per-op error messages, for surfacing to the user."""


# =============================================================================
# Decision / AI DTOs
# =============================================================================


@dataclass(frozen=True, slots=True)
class DecisionArtifact:
    """A recorded recommendation produced by the Decision Engine or AI.

    Critical for auditability and AI evaluation: every AI-derived output
    is wrapped in a ``DecisionArtifact`` recording inputs, prompt version,
    model, cost, and the recommendation itself. Acceptance (by a human
    or the Workflow Engine) is recorded separately.

    Bootstrap: schema shell. Fields stabilize before the first real AI
    call lands in v0.6.
    """

    id: InternalId
    """Unique id of this artifact."""

    capability: str
    """Name of the producing capability (e.g. ``"difficulty_estimator"``)."""

    recommendation: Any
    """The recommendation payload (shape defined per capability)."""

    reasoning: str | None = None
    """Human-readable explanation, when available."""

    model: str | None = None
    """Model identifier (e.g. ``"ollama/llama3"``), or ``None`` if heuristic."""

    prompt_version: str | None = None
    """Versioned prompt identifier, when AI-assisted."""

    cost_estimate: float | None = None
    """Estimated cost in USD, when known."""

    created_at: datetime | None = None
    """Wall-clock creation time. Use the Clock port in real code."""


# =============================================================================
# Generic Repository element type
# =============================================================================


@runtime_checkable
class Identifiable(Protocol):
    """Marker for entities that expose an ``id`` attribute.

    Used by ``Repository[T]`` so that callers can parameterize a
    repository over a concrete entity type without coupling to it.
    """

    @property
    def id(self) -> InternalId:  # pragma: no cover - protocol shape
        ...
