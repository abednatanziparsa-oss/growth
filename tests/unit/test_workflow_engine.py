"""Unit tests for the declarative Workflow Engine (v0.7)."""

from __future__ import annotations

from typing import Any

from growth.infrastructure.workflow.engine import (
    DeclarativeWorkflow,
    DeclarativeWorkflowEngine,
    WorkflowStep,
)


def test_run_executes_steps_in_order() -> None:
    calls: list[str] = []
    engine = DeclarativeWorkflowEngine()
    engine.register(
        DeclarativeWorkflow(
            name="review",
            trigger_type="external",
            steps=(
                WorkflowStep("one", lambda _: calls.append("one")),
                WorkflowStep("two", lambda _: calls.append("two")),
            ),
        )
    )
    result = engine.run("review")
    assert result.succeeded is True
    assert result.steps_completed == 2
    assert calls == ["one", "two"]


def test_run_unknown_workflow() -> None:
    engine = DeclarativeWorkflowEngine()
    result = engine.run("nope")
    assert result.succeeded is False
    assert result.steps_completed == 0
    assert "Unknown" in result.note


def test_run_empty_workflow_succeeds() -> None:
    engine = DeclarativeWorkflowEngine()
    engine.register(DeclarativeWorkflow(name="empty", trigger_type="external"))
    result = engine.run("empty")
    assert result.succeeded is True
    assert result.steps_completed == 0


def test_dry_run_does_not_execute() -> None:
    calls: list[str] = []
    engine = DeclarativeWorkflowEngine()
    engine.register(
        DeclarativeWorkflow(
            name="w",
            trigger_type="external",
            steps=(WorkflowStep("s", lambda _: calls.append("s")),),
        )
    )
    result = engine.run("w", dry_run=True)
    assert result.dry_run is True
    assert result.succeeded is True
    assert result.steps_completed == 1
    assert calls == []


def test_step_failure_stops_run() -> None:
    def boom(inputs: dict[str, Any]) -> None:
        raise RuntimeError("boom")

    calls: list[str] = []
    engine = DeclarativeWorkflowEngine()
    engine.register(
        DeclarativeWorkflow(
            name="w",
            trigger_type="external",
            steps=(
                WorkflowStep("first", lambda _: calls.append("first")),
                WorkflowStep("boom", boom),
                WorkflowStep("third", lambda _: calls.append("third")),
            ),
        )
    )
    result = engine.run("w")
    assert result.succeeded is False
    assert result.steps_completed == 1
    assert result.errors == ("boom: boom",)
    assert "Stopped at step 'boom'" in result.note
    assert calls == ["first"]


def test_cancel_stops_before_steps() -> None:
    calls: list[str] = []
    engine = DeclarativeWorkflowEngine()
    engine.register(
        DeclarativeWorkflow(
            name="w",
            trigger_type="external",
            steps=(WorkflowStep("s", lambda _: calls.append("s")),),
        )
    )
    engine.cancel()
    result = engine.run("w")
    assert result.steps_completed == 0
    assert result.succeeded is False
    assert calls == []
    assert "Cancelled" in result.note


def test_reset_allows_run_after_cancel() -> None:
    calls: list[str] = []
    engine = DeclarativeWorkflowEngine()
    engine.register(
        DeclarativeWorkflow(
            name="w",
            trigger_type="external",
            steps=(WorkflowStep("s", lambda _: calls.append("s")),),
        )
    )
    engine.cancel()
    engine.reset()
    result = engine.run("w")
    assert result.succeeded is True
    assert calls == ["s"]


def test_runs_history_records_outcomes() -> None:
    engine = DeclarativeWorkflowEngine()
    engine.register(DeclarativeWorkflow(name="w", trigger_type="external"))
    engine.run("w")
    engine.run("w", dry_run=True)
    assert len(engine.runs) == 2
    assert engine.runs[0].dry_run is False
    assert engine.runs[1].dry_run is True


def test_steps_receive_inputs() -> None:
    received: list[dict[str, Any]] = []

    def capture(inputs: dict[str, Any]) -> None:
        received.append(inputs)

    engine = DeclarativeWorkflowEngine()
    engine.register(
        DeclarativeWorkflow(
            name="w",
            trigger_type="external",
            steps=(WorkflowStep("capture", capture),),
        )
    )
    engine.run("w", inputs={"k": "v"})
    assert received == [{"k": "v"}]


def test_inputs_default_to_empty() -> None:
    received: list[dict[str, Any]] = []

    def capture(inputs: dict[str, Any]) -> None:
        received.append(inputs)

    engine = DeclarativeWorkflowEngine()
    engine.register(
        DeclarativeWorkflow(
            name="w",
            trigger_type="external",
            steps=(WorkflowStep("capture", capture),),
        )
    )
    engine.run("w")
    assert received == [{}]
