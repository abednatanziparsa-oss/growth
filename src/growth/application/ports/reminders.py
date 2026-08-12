"""Reminder repository port — persistence boundary for the Reminder aggregate."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from growth.domain.reminders import Reminder
from growth.domain.shared import InternalId, SpaceId

__all__ = ["ReminderRepository"]


@runtime_checkable
class ReminderRepository(Protocol):
    """Persistence for Reminder aggregates.

    Adds query methods specific to reminders: pending and due lookups.
    """

    def get(self, id: InternalId) -> Reminder:
        """Return the reminder with the given id.

        Raises:
            EntityNotFoundError: If no reminder has the given id.
        """
        ...

    def save(self, reminder: Reminder) -> None:
        """Persist ``reminder`` (insert or update by id)."""
        ...

    def delete(self, id: InternalId) -> None:
        """Delete the reminder with the given id.

        Raises:
            EntityNotFoundError: If no reminder has the given id.
        """
        ...

    def list_by_space(self, space_id: SpaceId) -> list[Reminder]:
        """Return all reminders in a space, soonest due first."""
        ...

    def list_pending(self, space_id: SpaceId) -> list[Reminder]:
        """Return reminders that have not fired yet, soonest due first."""
        ...

    def list_due(self, space_id: SpaceId, now: datetime) -> list[Reminder]:
        """Return pending reminders whose ``due_at`` has passed ``now``."""
        ...
