"""Unit tests for the workflow YAML loader (v0.7)."""

from __future__ import annotations

from typing import Any

import pytest

from growth.infrastructure.workflow.engine import DeclarativeWorkflow
from growth.infrastructure.workflow.loader import (
    WorkflowParseError,
    parse_workflow_yaml,
)


def _registry() -> dict[str, Any]:
    return {
        "next-action": lambda _: "next",
        "blockers": lambda _: "blocked",
    }


def test_parses_workflow_with_resolved_steps() -> None:
    wf = parse_workflow_yaml(
        "name: daily-review\ntrigger: time\nsteps:\n  - next-action\n  - blockers\n",
        _registry(),
    )
    assert isinstance(wf, DeclarativeWorkflow)
    assert wf.name == "daily-review"
    assert wf.trigger_type == "time"
    assert [s.name for s in wf.steps] == ["next-action", "blockers"]
    assert [s.fn({}) for s in wf.steps] == ["next", "blocked"]


def test_steps_default_to_empty() -> None:
    wf = parse_workflow_yaml("name: w\ntrigger: external\n", _registry())
    assert wf.name == "w"
    assert wf.trigger_type == "external"
    assert wf.steps == ()


def test_non_mapping_root_rejected() -> None:
    with pytest.raises(WorkflowParseError, match="mapping"):
        parse_workflow_yaml("- a\n- b\n", _registry())


def test_missing_name_rejected() -> None:
    with pytest.raises(WorkflowParseError, match="name"):
        parse_workflow_yaml("trigger: time\nsteps: []\n", _registry())


def test_missing_trigger_rejected() -> None:
    with pytest.raises(WorkflowParseError, match="trigger"):
        parse_workflow_yaml("name: w\nsteps: []\n", _registry())


def test_steps_not_a_list_rejected() -> None:
    with pytest.raises(WorkflowParseError, match="list"):
        parse_workflow_yaml("name: w\ntrigger: time\nsteps: next-action\n", _registry())


def test_unknown_step_rejected() -> None:
    with pytest.raises(WorkflowParseError, match="unknown step 'nope'"):
        parse_workflow_yaml("name: w\ntrigger: time\nsteps:\n  - nope\n", _registry())


def test_invalid_yaml_rejected() -> None:
    with pytest.raises(WorkflowParseError, match="Invalid YAML"):
        parse_workflow_yaml("name: [unclosed\n", _registry())


def test_unsafe_name_rejected() -> None:
    with pytest.raises(WorkflowParseError, match="safe filename"):
        parse_workflow_yaml("name: ../evil\ntrigger: time\nsteps: []\n", _registry())


def test_name_is_stripped() -> None:
    wf = parse_workflow_yaml("name:  review \ntrigger: time\nsteps: []\n", _registry())
    assert wf.name == "review"
