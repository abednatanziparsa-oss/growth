"""Projection port — pure canonical-to-provider-shape transformation.

A ``Projection`` takes a ``CanonicalPlan`` and produces the desired
``ProviderSnapshot`` for a specific provider (Todoist, Markdown, Google
Calendar, ...). Projections are **pure functions**: no I/O, no side
effects, no clock. They are trivially testable and diffable.

This is the architectural firewall that keeps the canonical model
provider-agnostic: every Todoist-ism (priority 1..4, emoji section
names) lives in the Todoist projection, never in the domain.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from growth.application.dtos import CanonicalPlan, ProviderSnapshot

__all__ = ["Projection"]


@runtime_checkable
class Projection(Protocol):
    """Project a ``CanonicalPlan`` into a provider-shaped snapshot.

    The provider name identifies which projection this is. The Differ
    (v0.2) compares the projected snapshot against the last-synced
    snapshot and the live remote state to compute a ``ChangeSet``.
    """

    @property
    def provider(self) -> str:
        """The provider name this projection targets (e.g. ``"todoist"``)."""
        ...

    def project(self, plan: CanonicalPlan) -> ProviderSnapshot:
        """Return the desired provider snapshot for ``plan``.

        Pure: the same ``plan`` always yields the same snapshot (modulo
        inserted ids when the provider hasn't been created yet).
        """
        ...
