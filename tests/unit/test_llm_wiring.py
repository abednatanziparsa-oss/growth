"""Unit tests for LLM settings and container wiring.

Verifies the offline-first contract: the real LLM backend is wired
only when AI is explicitly enabled AND base URL AND key are present;
every other combination yields the Noop backend.
"""

from __future__ import annotations

from growth.infrastructure.config.settings import Settings
from growth.infrastructure.llm.openai_compatible import OpenAICompatibleChat
from growth.infrastructure.noop.llm import NoopLlmChat
from growth.kernel.container import Container


class TestSettings:
    def test_defaults_offline(self) -> None:
        settings = Settings(_env_file=None)
        assert settings.ai_enabled is False
        assert settings.llm_base_url is None
        assert settings.llm_api_key is None
        assert settings.llm_model == "gpt-4o-mini"
        assert settings.llm_timeout == 60.0

    def test_env_overrides(self, monkeypatch) -> None:
        monkeypatch.setenv("GROWTH_AI_ENABLED", "true")
        monkeypatch.setenv("GROWTH_LLM_BASE_URL", "https://models.github.ai/inference")
        monkeypatch.setenv("GROWTH_LLM_MODEL", "gpt-4.1-mini")
        monkeypatch.setenv("GROWTH_LLM_API_KEY", "ghp_secret")
        monkeypatch.setenv("GROWTH_LLM_TIMEOUT", "30")

        settings = Settings(_env_file=None)

        assert settings.ai_enabled is True
        assert settings.llm_base_url == "https://models.github.ai/inference"
        assert settings.llm_model == "gpt-4.1-mini"
        assert settings.llm_api_key == "ghp_secret"
        assert settings.llm_timeout == 30.0


class TestContainerWiring:
    def _settings(self, **overrides: object) -> Settings:
        return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]

    def test_disabled_defaults_to_noop(self) -> None:
        container = Container.from_settings(self._settings())
        assert isinstance(container.llm_chat, NoopLlmChat)

    def test_enabled_without_key_stays_noop(self) -> None:
        container = Container.from_settings(
            self._settings(
                ai_enabled=True,
                llm_base_url="https://models.github.ai/inference",
                llm_api_key=None,
            )
        )
        assert isinstance(container.llm_chat, NoopLlmChat)

    def test_enabled_without_base_url_stays_noop(self) -> None:
        container = Container.from_settings(
            self._settings(
                ai_enabled=True,
                llm_base_url=None,
                llm_api_key="ghp_secret",
            )
        )
        assert isinstance(container.llm_chat, NoopLlmChat)

    def test_key_presence_alone_does_not_enable(self) -> None:
        # Explicit flag wins over key presence: no surprise network calls.
        container = Container.from_settings(
            self._settings(ai_enabled=False, llm_api_key="ghp_secret")
        )
        assert isinstance(container.llm_chat, NoopLlmChat)

    def test_fully_configured_wires_real_backend(self) -> None:
        container = Container.from_settings(
            self._settings(
                ai_enabled=True,
                llm_base_url="https://models.github.ai/inference",
                llm_model="gpt-4o-mini",
                llm_api_key="ghp_secret",
                llm_timeout=15.0,
            )
        )
        assert isinstance(container.llm_chat, OpenAICompatibleChat)
