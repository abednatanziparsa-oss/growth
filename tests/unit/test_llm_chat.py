"""Unit tests for the OpenAI-compatible LLM backend.

Uses httpx ``MockTransport`` so no network is touched: the transport
handles the request/response cycle entirely in-memory.
"""

from __future__ import annotations

import json

import httpx
import pytest

from growth.application.errors import LLMUnavailableError
from growth.application.ports.llm import LLMChat
from growth.infrastructure.llm.openai_compatible import OpenAICompatibleChat

BASE_URL = "https://models.github.ai/inference"
MODEL = "gpt-4o-mini"
API_KEY = "ghp_test_token"


def _chat(transport: httpx.MockTransport, **kwargs: object) -> OpenAICompatibleChat:
    client = httpx.Client(transport=transport)
    return OpenAICompatibleChat(
        base_url=BASE_URL,
        model=MODEL,
        api_key=API_KEY,
        timeout=5.0,
        client=client,
        **kwargs,  # type: ignore[arg-type]
    )


def _ok_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"role": "assistant", "content": "hello"}}]},
    )


class TestHappyPath:
    def test_returns_content(self) -> None:
        chat = _chat(httpx.MockTransport(_ok_handler))
        assert chat.chat("sys", "user") == "hello"

    def test_request_shape(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["headers"] = dict(request.headers)
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200, json={"choices": [{"message": {"content": "ok"}}]}
            )

        chat = _chat(httpx.MockTransport(handler))
        chat.chat("be nice", "plan this", temperature=0.7)

        assert captured["url"] == f"{BASE_URL}/chat/completions"
        headers = captured["headers"]
        assert headers["authorization"] == f"Bearer {API_KEY}"
        assert headers["content-type"] == "application/json"
        body = captured["body"]
        assert body["model"] == MODEL
        assert body["temperature"] == 0.7
        # Non-streaming is explicit: some gateways (9Router/Kiro) stream
        # by default and would otherwise return unparseable SSE chunks.
        assert body["stream"] is False
        assert body["messages"] == [
            {"role": "system", "content": "be nice"},
            {"role": "user", "content": "plan this"},
        ]

    def test_trailing_slash_base_url(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            return httpx.Response(
                200, json={"choices": [{"message": {"content": "x"}}]}
            )

        chat = OpenAICompatibleChat(
            base_url=f"{BASE_URL}/",
            model=MODEL,
            api_key=API_KEY,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        chat.chat("s", "u")
        assert captured["url"] == f"{BASE_URL}/chat/completions"


class TestPortConformance:
    def test_is_llm_chat_protocol(self) -> None:
        assert isinstance(_chat(httpx.MockTransport(_ok_handler)), LLMChat)


class TestFailures:
    @pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
    def test_http_error_maps_to_unavailable(self, status: int) -> None:
        chat = _chat(
            httpx.MockTransport(lambda _request: httpx.Response(status, json={}))
        )
        with pytest.raises(LLMUnavailableError):
            chat.chat("s", "u")

    def test_timeout_maps_to_unavailable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out", request=request)

        chat = _chat(httpx.MockTransport(handler))
        with pytest.raises(LLMUnavailableError):
            chat.chat("s", "u")

    def test_connection_error_maps_to_unavailable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        chat = _chat(httpx.MockTransport(handler))
        with pytest.raises(LLMUnavailableError):
            chat.chat("s", "u")

    def test_malformed_json_maps_to_unavailable(self) -> None:
        chat = _chat(
            httpx.MockTransport(lambda _request: httpx.Response(200, text="not json"))
        )
        with pytest.raises(LLMUnavailableError):
            chat.chat("s", "u")

    def test_missing_choices_maps_to_unavailable(self) -> None:
        chat = _chat(
            httpx.MockTransport(lambda _request: httpx.Response(200, json={"nope": 1}))
        )
        with pytest.raises(LLMUnavailableError):
            chat.chat("s", "u")

    def test_empty_content_maps_to_unavailable(self) -> None:
        chat = _chat(
            httpx.MockTransport(
                lambda _request: httpx.Response(
                    200, json={"choices": [{"message": {"content": "  "}}]}
                )
            )
        )
        with pytest.raises(LLMUnavailableError):
            chat.chat("s", "u")

    def test_null_content_maps_to_unavailable(self) -> None:
        chat = _chat(
            httpx.MockTransport(
                lambda _request: httpx.Response(
                    200, json={"choices": [{"message": {"content": None}}]}
                )
            )
        )
        with pytest.raises(LLMUnavailableError):
            chat.chat("s", "u")
