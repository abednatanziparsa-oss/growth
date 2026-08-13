"""Integration tests for kernel bootstrap — build_app wiring."""

from __future__ import annotations

from datetime import UTC, datetime

from growth.application.dtos import CanonicalPlan
from growth.domain.planning import Workspace
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId, SpaceId
from growth.infrastructure.config.settings import Settings
from growth.infrastructure.embeddings.local import LocalNGramEmbedder
from growth.infrastructure.storage.plan_store import PlanStore
from growth.infrastructure.sync.engine import SyncEngine
from growth.kernel.bootstrap import App, build_app


def _settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=tmp_path,
        environment="testing",
        log_level="warning",
    )


class TestBuildApp:
    def test_build_app_wires_everything(self, tmp_path) -> None:
        settings = _settings(tmp_path)
        app = build_app(settings)

        assert isinstance(app, App)
        assert app.settings is settings
        assert app.workspace_repo is not None
        assert app.project_repo is not None
        assert app.goal_repo is not None
        assert app.milestone_repo is not None
        assert app.task_repo is not None
        assert app.plan_applier is not None
        assert app.identity_map is not None
        assert app.attachment_repo is not None
        assert app.knowledge_search is not None
        assert app.semantic_search is not None
        assert isinstance(app.plan_store, PlanStore)
        assert app.reminder_repo is not None
        assert app.event_dispatcher is not None
        assert app.scheduler is not None
        assert app.ollama_embedder is None  # offline by default
        assert (tmp_path / "growth.db").exists()

    def test_build_app_default_settings_path(self, tmp_path, monkeypatch) -> None:
        """build_app() with no explicit settings loads Settings() internally."""
        monkeypatch.setattr(
            "growth.kernel.bootstrap.Settings",
            lambda: Settings(_env_file=None, data_dir=tmp_path, environment="testing"),
        )

        app = build_app()

        assert isinstance(app, App)
        assert (tmp_path / "growth.db").exists()

    def test_build_app_reuses_existing_db_file(self, tmp_path) -> None:
        settings = _settings(tmp_path)
        app1 = build_app(settings)
        now = datetime.now(UTC)
        app1.workspace_repo.save(
            Workspace(
                id=InternalId(),
                title="First",
                space_id=SpaceId(),
                created_at=now,
                updated_at=now,
            )
        )

        app2 = build_app(settings)
        assert len(app2.workspace_repo.list_all()) == 1

    def test_sync_engine_none_without_token(self, tmp_path) -> None:
        settings = _settings(tmp_path)
        app = build_app(settings)

        assert app.sync_engine is None

    def test_sync_engine_built_with_token(self, tmp_path) -> None:
        settings = Settings(
            _env_file=None,
            data_dir=tmp_path,
            environment="testing",
            todoist_api_token="fake-token",
        )
        app = build_app(settings)

        engine = app.sync_engine
        assert engine is not None
        assert isinstance(engine, SyncEngine)

    def test_export_markdown(self, tmp_path) -> None:
        settings = _settings(tmp_path)
        app = build_app(settings)
        plan = CanonicalPlan(
            space_id=DEFAULT_SPACE_ID,
            created_at=datetime(2026, 8, 1, tzinfo=UTC),
            project_name="Bootstrap Plan",
            raw_payload={"project_name": "Bootstrap Plan", "subjects": []},
        )

        content = app.export_markdown(plan)

        assert content.startswith("# Bootstrap Plan\n")
        assert "*Exported by Growth OS*" in content

    def test_ollama_embedder_wired_when_configured(self, tmp_path) -> None:
        settings = Settings(
            _env_file=None,
            data_dir=tmp_path,
            ollama_base_url="http://127.0.0.1:11434",
            ollama_model="nomic-embed-text",
        )
        app = build_app(settings)

        assert app.ollama_embedder is not None
        assert app.ollama_embedder._base_url == "http://127.0.0.1:11434"
        assert app.ollama_embedder._model == "nomic-embed-text"
        # semantic search uses the configured embedder
        assert app.semantic_search._embedder is app.ollama_embedder

    def test_semantic_search_uses_local_embedder_by_default(self, tmp_path) -> None:
        app = build_app(Settings(_env_file=None, data_dir=tmp_path))

        assert isinstance(app.semantic_search._embedder, LocalNGramEmbedder)
