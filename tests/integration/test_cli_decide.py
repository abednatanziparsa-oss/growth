"""Integration tests for `growth decide` (Decision Engine)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from typer.testing import CliRunner

from growth.application.llm_decisions import LlmDecisionEngine
from growth.domain.planning import Task
from growth.domain.shared import DEFAULT_SPACE_ID
from growth.infrastructure.decision.heuristic import HeuristicDecisionEngine
from growth.infrastructure.noop.llm import NoopLlmChat
from growth.kernel.bootstrap import App
from growth.presentation.cli.app import app
from tests.helpers import SharedDbAppFactory, apply_plan

runner = CliRunner()

PLAN = """\
project_name: Study Plan
subjects:
  - name: Math
    priority: high
    chapters:
      - name: Algebra
"""


def test_decide_next_action_recommends(monkeypatch) -> None:
    factory = SharedDbAppFactory()
    apply_plan(monkeypatch, factory, PLAN)
    result = runner.invoke(app, ["decide", "next-action"])
    assert result.exit_code == 0
    assert "Next action:" in result.stdout


def test_decide_sort_lists_tasks(monkeypatch) -> None:
    factory = SharedDbAppFactory()
    apply_plan(monkeypatch, factory, PLAN)
    result = runner.invoke(app, ["decide", "sort"])
    assert result.exit_code == 0
    assert "Algebra" in result.stdout


def test_decide_blockers_empty(monkeypatch) -> None:
    factory = SharedDbAppFactory()
    apply_plan(monkeypatch, factory, PLAN)
    result = runner.invoke(app, ["decide", "blockers"])
    assert result.exit_code == 0
    assert "No overdue tasks." in result.stdout


def test_decide_next_action_empty_db(monkeypatch) -> None:
    factory = SharedDbAppFactory()
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    result = runner.invoke(app, ["decide", "next-action"])
    assert result.exit_code == 0
    assert "No actionable tasks." in result.stdout


def test_decide_sort_empty_db(monkeypatch) -> None:
    factory = SharedDbAppFactory()
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    result = runner.invoke(app, ["decide", "sort"])
    assert result.exit_code == 0
    assert "No incomplete tasks." in result.stdout


# -- v0.8: LLM-assisted Decision Engine ---------------------------------------


class _FakeLlm:
    """LLMChat double returning a canned advice line."""

    def chat(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        return "Start with Algebra: it unblocks the rest of Math."


def test_decide_next_action_shows_ai_advice(monkeypatch) -> None:
    """With an available LLM, decide output carries the AI advice line."""
    factory = SharedDbAppFactory()
    apply_plan(monkeypatch, factory, PLAN)

    def patched(self: App) -> LlmDecisionEngine:
        return LlmDecisionEngine(
            HeuristicDecisionEngine(self.task_repo),
            _FakeLlm(),
            model="fake/model",
        )

    monkeypatch.setattr(App, "decision_engine", property(patched))
    result = runner.invoke(app, ["decide", "next-action"])
    assert result.exit_code == 0
    assert "[AI: fake/model]" in result.stdout
    assert "Start with Algebra" in result.stdout
    # The deterministic recommendation is unchanged.
    assert "Next action:" in result.stdout


def test_decide_blockers_shows_ai_advice(monkeypatch) -> None:
    factory = SharedDbAppFactory()
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    app_ctx = factory()
    now = datetime.now(UTC)
    app_ctx.task_repo.save(
        Task(
            title="overdue quiz",
            space_id=DEFAULT_SPACE_ID,
            due_at=now - timedelta(days=1),
            created_at=now,
            updated_at=now,
        )
    )

    def patched(self: App) -> LlmDecisionEngine:
        return LlmDecisionEngine(
            HeuristicDecisionEngine(self.task_repo),
            _FakeLlm(),
            model="fake/model",
        )

    monkeypatch.setattr(App, "decision_engine", property(patched))
    result = runner.invoke(app, ["decide", "blockers"])
    assert result.exit_code == 0
    assert "overdue quiz" in result.stdout
    assert "[AI: fake/model]" in result.stdout


def test_app_decision_engine_wraps_heuristic(monkeypatch) -> None:
    """Bootstrap wires the LLM wrapper over the heuristic core."""
    factory = SharedDbAppFactory()
    monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
    app_ctx = factory()

    engine = app_ctx.decision_engine
    assert isinstance(engine, LlmDecisionEngine)
    # Offline default: the wrapped LLM is the Noop backend, model hidden.
    assert isinstance(app_ctx.container.llm_chat, NoopLlmChat)
    artifact = engine.recommend("next_action")
    assert artifact.model is None
    assert artifact.prompt_version is None
