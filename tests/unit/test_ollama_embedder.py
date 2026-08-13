"""Unit tests for the Ollama embedding provider (mocked httpx, no network)."""

from __future__ import annotations

import math
from unittest.mock import patch

import httpx
import pytest

from growth.application.errors import EmbeddingUnavailableError
from growth.application.ports.embeddings import Embeddings
from growth.infrastructure.config.settings import Settings
from growth.infrastructure.embeddings.ollama import OllamaEmbedder


def _mock_response(status: int = 200, payload: dict | None = None) -> httpx.Response:
    payload = payload if payload is not None else {"embeddings": [[0.5, 1.5, -2.0]]}
    return httpx.Response(
        status,
        json=payload,
        request=httpx.Request("POST", "http://127.0.0.1:11434/api/embed"),
    )


class TestOllamaEmbedder:
    def test_implements_port(self) -> None:
        assert isinstance(OllamaEmbedder(), Embeddings)

    def test_embed_returns_normalized_vector(self) -> None:
        with patch(
            "growth.infrastructure.embeddings.ollama.httpx.post",
            return_value=_mock_response(),
        ) as post:
            vector = OllamaEmbedder().embed("سلام دنیا")

        assert post.call_count == 1
        url = post.call_args.args[0]
        assert url == "http://127.0.0.1:11434/api/embed"
        sent = post.call_args.kwargs["json"]
        assert sent == {"model": "bge-m3", "input": ["سلام دنیا"]}
        norm = math.sqrt(sum(v * v for v in vector))
        assert norm == pytest.approx(1.0)

    def test_embed_hits_configured_server_and_model(self) -> None:
        with patch(
            "growth.infrastructure.embeddings.ollama.httpx.post",
            return_value=_mock_response(payload={"embeddings": [[1.0, 0.0]]}),
        ) as post:
            OllamaEmbedder(
                base_url="http://10.0.0.5:11434/", model="nomic-embed-text"
            ).embed("x")

        url = post.call_args.args[0]
        assert url == "http://10.0.0.5:11434/api/embed"
        assert post.call_args.kwargs["json"]["model"] == "nomic-embed-text"

    def test_embed_zero_vector_stays_zero(self) -> None:
        with patch(
            "growth.infrastructure.embeddings.ollama.httpx.post",
            return_value=_mock_response(payload={"embeddings": [[0.0, 0.0, 0.0]]}),
        ):
            vector = OllamaEmbedder().embed("x")

        assert vector == [0.0, 0.0, 0.0]

    def test_embed_connection_error_raises(self) -> None:
        with (
            patch(
                "growth.infrastructure.embeddings.ollama.httpx.post",
                side_effect=httpx.ConnectError("connection refused"),
            ),
            pytest.raises(EmbeddingUnavailableError, match="connection refused"),
        ):
            OllamaEmbedder().embed("x")

    def test_embed_timeout_raises(self) -> None:
        with (
            patch(
                "growth.infrastructure.embeddings.ollama.httpx.post",
                side_effect=httpx.TimeoutException("timed out"),
            ),
            pytest.raises(EmbeddingUnavailableError),
        ):
            OllamaEmbedder(timeout=1.0).embed("x")

    def test_embed_http_error_raises(self) -> None:
        with (
            patch(
                "growth.infrastructure.embeddings.ollama.httpx.post",
                return_value=httpx.Response(
                    500,
                    text="internal error",
                    request=httpx.Request("POST", "http://127.0.0.1:11434/api/embed"),
                ),
            ),
            pytest.raises(EmbeddingUnavailableError, match="500"),
        ):
            OllamaEmbedder().embed("x")

    def test_embed_malformed_payload_raises(self) -> None:
        for payload in ({}, {"embeddings": []}, {"embeddings": "nope"}):
            with (
                patch(
                    "growth.infrastructure.embeddings.ollama.httpx.post",
                    return_value=_mock_response(payload=payload),
                ),
                pytest.raises(EmbeddingUnavailableError),
            ):
                OllamaEmbedder().embed("x")


class TestSettings:
    def test_ollama_off_by_default(self) -> None:
        settings = Settings(_env_file=None)
        assert settings.ollama_base_url is None
        assert settings.ollama_model == "bge-m3"

    def test_ollama_env_overrides(self, monkeypatch) -> None:
        monkeypatch.setenv("GROWTH_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        monkeypatch.setenv("GROWTH_OLLAMA_MODEL", "mxbai-embed-large")
        settings = Settings(_env_file=None)
        assert settings.ollama_base_url == "http://127.0.0.1:11434"
        assert settings.ollama_model == "mxbai-embed-large"
