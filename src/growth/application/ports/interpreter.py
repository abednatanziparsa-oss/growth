"""Interpreter port — the Interpret stage of the ingestion pipeline.

An ``Interpreter`` lifts a ``RawPlan`` (format-neutral IR) into a
``CanonicalPlan`` (provider-agnostic domain model). Multiple
interpreters can produce plans from the same raw input:
``HeuristicInterpreter`` (rules-based, deterministic),
``LlmAssistedInterpreter`` (AI-assisted, optional).

Per the architecture review, interpreters read Knowledge Assets (not
raw bytes) once the Knowledge substrate lands in v0.4. At bootstrap
the contract is expressed against ``RawPlan`` directly.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from growth.application.dtos import CanonicalPlan, RawPlan
from growth.application.errors import ValidationError
from growth.domain.shared import SpaceId

__all__ = ["InterpretationError", "Interpreter"]


class InterpretationError(ValidationError):
    """Raised when a RawPlan cannot be lifted into a valid CanonicalPlan.

    Example: the raw plan references a subject that has no chapters, or
    contains an invalid priority label.
    """


@runtime_checkable
class Interpreter(Protocol):
    """Lift a ``RawPlan`` into a ``CanonicalPlan``.

    Implementations must be deterministic for the same input (modulo
    injected ids and timestamps). AI-assisted interpreters wrap their
    non-determinism behind the AI port so the surface stays predictable.
    """

    def interpret(
        self,
        raw: RawPlan,
        *,
        space_id: SpaceId | None = None,
    ) -> CanonicalPlan:
        """Produce a CanonicalPlan from ``raw``.

        Args:
            raw: The intermediate representation from a parser.
            space_id: Owning space. Defaults to ``DEFAULT_SPACE_ID``.

        Returns:
            A validated ``CanonicalPlan``.

        Raises:
            InterpretationError: If the raw plan is semantically invalid.
        """
        ...
