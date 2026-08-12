"""End-to-end test against the REAL Todoist API.

Skipped unless ``GROWTH_TODOIST_API_TOKEN`` is set in the environment —
normal CI runs never execute this (the project's own ``.env`` is not
loaded here by design). Run it manually when you want to verify the
adapter against live Todoist:

    $env:GROWTH_TODOIST_API_TOKEN = "<token>"   # PowerShell
    uv run pytest tests/integration/test_todoist_e2e.py -v

Safety: the test creates a uniquely-named project and deletes it in a
``finally`` block, so a failure cannot leave test data behind.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from growth.application.dtos import ChangeSet
from growth.infrastructure.adapters.todoist import TodoistAdapter

pytestmark = pytest.mark.skipif(
    not os.environ.get("GROWTH_TODOIST_API_TOKEN"),
    reason="GROWTH_TODOIST_API_TOKEN not set (live API test)",
)


@pytest.fixture
def adapter() -> TodoistAdapter:
    token = os.environ["GROWTH_TODOIST_API_TOKEN"]
    return TodoistAdapter(token)


def _run_name() -> str:
    return f"growth-e2e-{uuid4().hex[:8]}"


class TestTodoistLiveRoundTrip:
    def test_create_sync_fetch_cleanup(self, adapter: TodoistAdapter) -> None:
        name = _run_name()
        project_id: str | None = None
        try:
            # --- create project ------------------------------------------
            project_id = adapter._apply_op({"op": "create_project", "name": name})
            assert project_id

            # --- create section + task ------------------------------------
            section_id = adapter._apply_op(
                {"op": "create_section", "name": "Math", "project_id": project_id}
            )
            assert section_id
            task_id = adapter._apply_op(
                {
                    "op": "create_task",
                    "content": "Study algebra",
                    "project_id": project_id,
                    "section_id": section_id,
                }
            )
            assert task_id

            # --- fetch live state -----------------------------------------
            snap = adapter.fetch_current(project_id)
            assert snap.root_id == project_id
            assert snap.payload["project"]["name"] == name
            section_names = [s["name"] for s in snap.payload["sections"]]
            assert "Math" in section_names
            task_contents = [t["content"] for t in snap.payload["tasks"]]
            assert "Study algebra" in task_contents

            # --- update + complete the task -------------------------------
            up = adapter.apply(
                ChangeSet(
                    provider="todoist",
                    operations=[
                        {
                            "op": "update_task",
                            "provider_id": task_id,
                            "content": "Study algebra (done)",
                        },
                        {"op": "complete_task", "provider_id": task_id},
                    ],
                )
            )
            assert up.failed == 0

            # Todoist's get_tasks() returns only ACTIVE tasks — a completed
            # task disappears from the active list. Verify via the
            # completed-tasks endpoint instead. The task has no due date, so
            # query by completion time (its since/until window must not
            # exceed 6 weeks) and match the unique task id.
            now = datetime.now(UTC)
            completed_pages = list(
                adapter._api.get_completed_tasks_by_completion_date(
                    since=now - timedelta(hours=1),
                    until=now,
                )
            )
            completed_tasks = [t for page in completed_pages for t in page]
            done = [t for t in completed_tasks if t.id == task_id]
            assert done and done[0].completed_at is not None
        finally:
            if project_id:
                adapter.apply(
                    ChangeSet(
                        provider="todoist",
                        operations=[
                            {"op": "delete_project", "provider_id": project_id}
                        ],
                    )
                )
