"""Unit tests for the heuristic Decision Engine (v0.7)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from growth.domain.planning import Priority, Task
from growth.domain.shared import DEFAULT_SPACE_ID
from growth.infrastructure.decision.heuristic import HeuristicDecisionEngine
from growth.infrastructure.storage.planning_repos import (
    TaskRepository,
    new_in_memory_db,
)


def _now() -> datetime:
    return datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


def _task(
    title: str,
    *,
    priority: Priority | None = None,
    due_at: datetime | None = None,
    estimated_minutes: int | None = None,
    parent_id=None,
    completed: bool = False,
) -> Task:
    base = _now()
    return Task(
        title=title,
        space_id=DEFAULT_SPACE_ID,
        priority=priority,
        due_at=due_at,
        estimated_minutes=estimated_minutes,
        parent_id=parent_id,
        created_at=base,
        updated_at=base,
        completed_at=base if completed else None,
    )


def _engine(
    tasks: list[Task], *, now: datetime | None = None
) -> HeuristicDecisionEngine:
    repo = TaskRepository(new_in_memory_db())
    for t in tasks:
        repo.save(t)
    return HeuristicDecisionEngine(repo, now=(lambda: now) if now is not None else None)


# -- next_action ----------------------------------------------------------


def test_next_action_empty() -> None:
    a = _engine([]).recommend("next_action")
    assert a.recommendation is None
    assert "No actionable" in (a.reasoning or "")


def test_next_action_highest_priority() -> None:
    low = _task("low task", priority=Priority.LOW)
    urgent = _task("urgent task", priority=Priority.URGENT)
    a = _engine([low, urgent]).recommend("next_action")
    assert a.recommendation["title"] == "urgent task"


def test_next_action_skips_completed() -> None:
    done = _task("done", priority=Priority.URGENT, completed=True)
    todo = _task("todo", priority=Priority.LOW)
    a = _engine([done, todo]).recommend("next_action")
    assert a.recommendation["title"] == "todo"


def test_next_action_prefers_leaf_over_parent_with_open_children() -> None:
    parent = _task("parent chapter", priority=Priority.URGENT)
    child = _task("child subtask", priority=Priority.LOW, parent_id=parent.id)
    a = _engine([parent, child]).recommend("next_action")
    assert a.recommendation["title"] == "child subtask"


def test_next_action_parent_actionable_when_children_complete() -> None:
    parent = _task("parent", priority=Priority.URGENT)
    child = _task("child", priority=Priority.LOW, parent_id=parent.id, completed=True)
    a = _engine([parent, child]).recommend("next_action")
    assert a.recommendation["title"] == "parent"


def test_next_action_due_date_tiebreak() -> None:
    later = _task("later", priority=Priority.HIGH, due_at=_now() + timedelta(days=2))
    sooner = _task("sooner", priority=Priority.HIGH, due_at=_now() + timedelta(days=1))
    a = _engine([later, sooner]).recommend("next_action")
    assert a.recommendation["title"] == "sooner"


def test_next_action_effort_tiebreak() -> None:
    big = _task("big", priority=Priority.MEDIUM, estimated_minutes=120)
    small = _task("small", priority=Priority.MEDIUM, estimated_minutes=15)
    a = _engine([big, small]).recommend("next_action")
    assert a.recommendation["title"] == "small"


def test_next_action_title_tiebreak_stable() -> None:
    b = _task("B task", priority=Priority.MEDIUM)
    a = _task("A task", priority=Priority.MEDIUM)
    rec = _engine([b, a]).recommend("next_action")
    assert rec.recommendation["title"] == "A task"


# -- blockers --------------------------------------------------------------


def test_blockers_overdue_sorted() -> None:
    now = _now()
    older = _task("older", due_at=now - timedelta(days=2))
    newer = _task("newer", due_at=now - timedelta(days=1))
    a = _engine([newer, older], now=now).recommend("blockers")
    assert [i["title"] for i in a.recommendation] == ["older", "newer"]


def test_blockers_empty_when_nothing_overdue() -> None:
    now = _now()
    future = _task("future", due_at=now + timedelta(days=1))
    nodue = _task("no due")
    a = _engine([future, nodue], now=now).recommend("blockers")
    assert a.recommendation == []


def test_blockers_excludes_completed_overdue() -> None:
    now = _now()
    done = _task("done", due_at=now - timedelta(days=5), completed=True)
    a = _engine([done], now=now).recommend("blockers")
    assert a.recommendation == []


def test_blockers_reports_overdue_minutes() -> None:
    now = _now()
    task = _task("late", due_at=now - timedelta(minutes=90))
    a = _engine([task], now=now).recommend("blockers")
    assert a.recommendation[0]["overdue_minutes"] == 90


# -- priority_sort ----------------------------------------------------------


def test_priority_sort_order() -> None:
    low = _task("low", priority=Priority.LOW)
    urgent = _task("urgent", priority=Priority.URGENT)
    high = _task("high", priority=Priority.HIGH)
    none = _task("none", priority=None)
    a = _engine([none, low, high, urgent]).recommend("priority_sort")
    assert [i["title"] for i in a.recommendation] == ["urgent", "high", "low", "none"]


def test_priority_sort_excludes_completed() -> None:
    done = _task("done", priority=Priority.URGENT, completed=True)
    todo = _task("todo", priority=Priority.LOW)
    a = _engine([done, todo]).recommend("priority_sort")
    assert [i["title"] for i in a.recommendation] == ["todo"]


# -- misc -------------------------------------------------------------------


def test_unknown_query() -> None:
    a = _engine([]).recommend("bogus_query")
    assert a.recommendation is None
    assert "Unknown" in (a.reasoning or "")


def test_artifact_metadata() -> None:
    task = _task("only", priority=Priority.HIGH)
    a = _engine([task]).recommend("next_action")
    assert a.capability == "decision:next_action"
    assert a.model is None
    assert a.prompt_version is None
    assert a.cost_estimate == 0.0
