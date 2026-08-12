"""Integration tests for export / knowledge / sync CLI commands."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from types import SimpleNamespace
from uuid import uuid4

from typer.testing import CliRunner

import growth.infrastructure.adapters.todoist as todoist_module
from growth.application.dtos import ApplyResult
from growth.infrastructure.config.settings import Settings
from growth.kernel.bootstrap import App
from growth.presentation.cli.app import app
from tests.helpers import SharedDbAppFactory, apply_plan, yaml_file

runner = CliRunner()

_PLAN = """\
    project_name: "CLI Export Plan"
    subjects:
      - name: "Math"
        emoji: "📘"
        chapters:
          - name: "Algebra"
    standard_subtasks:
      - "Study"
"""


def _temp_file(suffix: str = ".txt") -> Path:
    with NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as f:
        f.write("")
        return Path(f.name)


# ============================================================================
# version
# ============================================================================


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "growth-os" in result.stdout


# ============================================================================
# export markdown
# ============================================================================


class TestExportMarkdown:
    def test_export_without_plan_errors(self, monkeypatch) -> None:
        factory = SharedDbAppFactory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)

        result = runner.invoke(app, ["export", "markdown"])

        assert result.exit_code == 1
        assert "No plan found" in result.stderr

    def test_export_to_stdout(self, monkeypatch) -> None:
        factory = SharedDbAppFactory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        runner.invoke(app, ["plan", "apply", str(yaml_file(_PLAN))])

        result = runner.invoke(app, ["export", "markdown"])

        assert result.exit_code == 0
        assert "# CLI Export Plan" in result.stdout
        assert "## 📘 Math" in result.stdout
        assert "- [ ] Study" in result.stdout

    def test_export_to_file(self, monkeypatch) -> None:
        factory = SharedDbAppFactory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        runner.invoke(app, ["plan", "apply", str(yaml_file(_PLAN))])

        out = _temp_file(".md")
        result = runner.invoke(app, ["export", "markdown", "-o", str(out)])

        assert result.exit_code == 0
        assert "[OK] Exported" in result.stdout
        assert out.read_text(encoding="utf-8").startswith("# CLI Export Plan")
        out.unlink()

    def test_export_fallback_for_legacy_db(self, monkeypatch) -> None:
        """DBs created before the plan store fall back to entity reconstruction."""
        factory = SharedDbAppFactory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        runner.invoke(app, ["plan", "apply", str(yaml_file(_PLAN))])

        # Simulate a pre-plan-store database: entities exist, no stored plan.
        factory._db.execute("DELETE FROM plans")
        factory._db.commit()

        result = runner.invoke(app, ["export", "markdown"])

        assert result.exit_code == 0
        assert "# CLI Export Plan" in result.stdout
        # Legacy fallback reconstructs a minimal plan — no subjects.
        assert "## 📘 Math" not in result.stdout


# ============================================================================
# knowledge
# ============================================================================


class TestKnowledgeCommands:
    def test_list_empty(self, monkeypatch) -> None:
        factory = SharedDbAppFactory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)

        result = runner.invoke(app, ["knowledge", "list"])

        assert result.exit_code == 0
        assert "No attachments yet" in result.stdout

    def test_attach_and_list(self, monkeypatch) -> None:
        factory = SharedDbAppFactory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)

        f = _temp_file(".pdf")
        f.write_text("some content", encoding="utf-8")

        r1 = runner.invoke(app, ["knowledge", "attach", str(f)])
        assert r1.exit_code == 0
        assert "[OK] Attached" in r1.stdout

        r2 = runner.invoke(app, ["knowledge", "list"])
        assert r2.exit_code == 0
        assert f.name in r2.stdout
        f.unlink()

    def test_attach_dedup_by_hash(self, monkeypatch) -> None:
        factory = SharedDbAppFactory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)

        f = _temp_file(".pdf")
        f.write_text("identical bytes", encoding="utf-8")

        runner.invoke(app, ["knowledge", "attach", str(f)])
        r2 = runner.invoke(app, ["knowledge", "attach", str(f)])

        assert r2.exit_code == 0
        assert "Already attached" in r2.stdout
        f.unlink()

    def test_attach_to_task(self, monkeypatch) -> None:
        factory = SharedDbAppFactory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)

        f = _temp_file(".pdf")
        f.write_text("task content", encoding="utf-8")
        task_id = str(uuid4())

        result = runner.invoke(app, ["knowledge", "attach", str(f), "--task", task_id])
        assert result.exit_code == 0

        listing = runner.invoke(app, ["knowledge", "list"])
        assert f"task:{task_id}" in listing.stdout
        f.unlink()

    def test_search_found_and_not_found(self, monkeypatch, tmp_path) -> None:
        factory = SharedDbAppFactory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)

        f = tmp_path / "growth-roadmap.pdf"
        f.write_text("growth roadmap notes", encoding="utf-8")
        runner.invoke(app, ["knowledge", "attach", str(f)])

        hit = runner.invoke(app, ["knowledge", "search", "roadmap"])
        assert hit.exit_code == 0
        assert "growth-roadmap.pdf" in hit.stdout

        miss = runner.invoke(app, ["knowledge", "search", "zzz"])
        assert miss.exit_code == 0
        assert "No results" in miss.stdout

    def test_semantic_search_flag(self, monkeypatch, tmp_path) -> None:
        factory = SharedDbAppFactory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)

        f = tmp_path / "growth-roadmap.pdf"
        f.write_text("growth roadmap notes", encoding="utf-8")
        runner.invoke(app, ["knowledge", "attach", str(f)])

        hit = runner.invoke(app, ["knowledge", "search", "--semantic", "roadmapp"])
        assert hit.exit_code == 0
        assert "growth-roadmap.pdf" in hit.stdout

    def test_semantic_search_unavailable_errors(self, monkeypatch) -> None:
        # Simulate an App without a semantic search engine.
        monkeypatch.setattr(
            "growth.presentation.cli.app.build_app",
            lambda: SimpleNamespace(semantic_search=None),
        )

        result = runner.invoke(app, ["knowledge", "search", "--semantic", "x"])

        assert result.exit_code == 1
        assert "Semantic search is not available" in result.stderr


# ============================================================================
# sync todoist
# ============================================================================


class TestSyncTodoist:
    def test_no_token_errors(self, monkeypatch) -> None:
        factory = SharedDbAppFactory(settings=Settings(_env_file=None))
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        monkeypatch.delenv("GROWTH_TODOIST_API_TOKEN", raising=False)
        monkeypatch.delenv("TODOIST_API_TOKEN", raising=False)

        result = runner.invoke(app, ["sync", "todoist"])

        assert result.exit_code == 1
        assert "GROWTH_TODOIST_API_TOKEN is not set" in result.stderr

    def test_no_plan_errors(self, monkeypatch) -> None:
        factory = SharedDbAppFactory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        monkeypatch.setenv("GROWTH_TODOIST_API_TOKEN", "fake-token")

        result = runner.invoke(app, ["sync", "todoist"])

        assert result.exit_code == 1
        assert "No plan found" in result.stderr

    def test_dry_run_previews_changeset(self, monkeypatch) -> None:
        factory = SharedDbAppFactory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        monkeypatch.setenv("GROWTH_TODOIST_API_TOKEN", "fake-token")

        apply_plan(monkeypatch, factory, _PLAN)
        result = runner.invoke(app, ["sync", "todoist", "--dry-run"])

        assert result.exit_code == 0
        assert "operation(s)" in result.stdout
        assert "create_project" in result.stdout
        assert "[DRY-RUN]" in result.stdout

    def test_apply_failure_errors(self, monkeypatch) -> None:
        class _BoomAdapter:
            provider = "todoist"

            def __init__(self, token: str) -> None:
                pass

            def fetch_current(self, root_id: str | None):
                return None

            def apply(self, changeset):
                raise RuntimeError("auth failed")

        monkeypatch.setattr(todoist_module, "TodoistAdapter", _BoomAdapter)
        factory = SharedDbAppFactory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        monkeypatch.setenv("GROWTH_TODOIST_API_TOKEN", "fake-token")

        apply_plan(monkeypatch, factory, _PLAN)
        result = runner.invoke(app, ["sync", "todoist"])

        assert result.exit_code == 1
        assert "[ERROR] Sync failed" in result.stderr

    def test_apply_success_reports_mappings_and_errors(self, monkeypatch) -> None:
        class _GoodAdapter:
            provider = "todoist"

            def __init__(self, token: str) -> None:
                pass

            def fetch_current(self, root_id: str | None):
                return None

            def apply(self, changeset):
                return ApplyResult(
                    applied=1,
                    failed=1,
                    provider_ids={"123e4567-e89b-12d3-a456-426614174000": "proj-9"},
                    errors=["op=create_section id=? : boom"],
                )

        monkeypatch.setattr(todoist_module, "TodoistAdapter", _GoodAdapter)
        factory = SharedDbAppFactory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        monkeypatch.setenv("GROWTH_TODOIST_API_TOKEN", "fake-token")

        apply_plan(monkeypatch, factory, _PLAN)
        result = runner.invoke(app, ["sync", "todoist"])

        assert result.exit_code == 0
        assert "[OK] Applied: 1, Failed: 1" in result.stdout
        assert "Provider ids: 1 new mapping(s)" in result.stdout
        assert "boom" in result.stderr

    def test_sync_no_engine_available(self, monkeypatch) -> None:
        monkeypatch.setattr(App, "sync_engine", property(lambda _self: None))
        factory = SharedDbAppFactory()
        monkeypatch.setattr("growth.presentation.cli.app.build_app", factory)
        monkeypatch.setenv("GROWTH_TODOIST_API_TOKEN", "fake-token")

        apply_plan(monkeypatch, factory, _PLAN)
        result = runner.invoke(app, ["sync", "todoist", "--dry-run"])

        assert result.exit_code == 1
        assert "No sync engine available" in result.stderr
