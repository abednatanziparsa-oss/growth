"""Application-layer error hierarchy.

Application errors cover use-case-level failures: invalid input at
boundaries, port contract violations, and synchronization problems
(conflicts, unreachable providers). They wrap or translate the more
specific domain errors raised by the inner ring.

Hierarchy:

    GrowthError                       (project root)
        ├── DomainError               (see growth.domain.errors)
        └── ApplicationError
              ├── ValidationError       (input failed boundary checks)
              ├── PortError             (a port impl violated its contract)
              └── SyncError             (synchronization failed)
                    ├── ConflictDetectedError
                    └── ProviderUnavailableError
"""

from __future__ import annotations

__all__ = [
    "ApplicationError",
    "ConflictDetectedError",
    "EmbeddingUnavailableError",
    "LLMUnavailableError",
    "PortError",
    "ProviderUnavailableError",
    "SyncError",
    "ValidationError",
]


class GrowthError(Exception):
    """Root of the entire error hierarchy in Growth OS.

    Every domain, application, and (where it makes sense) infrastructure
    error derives from this, so callers can ``except GrowthError`` to
    catch any Growth-originated failure.
    """


class ApplicationError(GrowthError):
    """Base class for all application-layer errors."""


class ValidationError(ApplicationError):
    """Raised when input fails validation at a system boundary.

    Example: a YAML study plan missing a required field, or a CLI flag
    combination that cannot be satisfied.
    """


class PortError(ApplicationError):
    """Raised when a port implementation violates its contract.

    Example: a ``Projection`` returns ``None`` for a non-optional field,
    or a ``Repository.get`` returns a stale type.
    """


class SyncError(ApplicationError):
    """Base class for synchronization failures."""


class ConflictDetectedError(SyncError):
    """Raised when three-way diff detects a conflict that cannot auto-resolve.

    Carries enough detail (desired / base / remote fields) for the UI to
    present a per-field resolution prompt.
    """

    def __init__(self, message: str, *, conflicts: list[str] | None = None) -> None:
        """Initialize with a message and an optional list of conflict field paths.

        Args:
            message: Human-readable summary.
            conflicts: Dotted field paths that diverge (e.g. ``["task.title"]``).
        """

        super().__init__(message)
        self.conflicts: list[str] = conflicts or []


class ProviderUnavailableError(SyncError):
    """Raised when a sync target (Todoist, Google Calendar, ...) is unreachable.

    Surfaced so callers can retry with backoff or fall back to a backup
    provider (e.g., Markdown export when the API is down).
    """


class EmbeddingUnavailableError(ApplicationError):
    """Raised when a model-backed embedder cannot produce vectors.

    Covers connection failures, HTTP errors, and malformed responses.
    Callers (e.g. semantic search) fall back to the offline
    ``LocalNGramEmbedder`` when this is raised.
    """


class LLMUnavailableError(ApplicationError):
    """Raised when an LLM backend cannot produce a response.

    Covers connection failures, HTTP errors, and malformed payloads.
    Callers (e.g. the AI interpreter) fall back to deterministic
    heuristics when this is raised, keeping queries offline-safe.
    """
