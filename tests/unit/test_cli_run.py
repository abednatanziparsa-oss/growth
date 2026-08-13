"""Unit tests for the CLI console-safety entry point."""

from __future__ import annotations

import pytest

from growth.presentation.cli.app import _make_console_encoding_safe, run


class TestMakeConsoleEncodingSafe:
    def test_reconfigures_streams_with_replace(self, monkeypatch) -> None:
        calls: list[dict[str, str]] = []

        class FakeStream:
            def reconfigure(self, **kwargs: str) -> None:
                calls.append(kwargs)

        fake = FakeStream()
        monkeypatch.setattr("growth.presentation.cli.app.sys.stdout", fake)
        monkeypatch.setattr("growth.presentation.cli.app.sys.stderr", fake)

        _make_console_encoding_safe()

        assert calls == [{"errors": "replace"}, {"errors": "replace"}]

    def test_skips_streams_without_reconfigure(self, monkeypatch) -> None:
        class Plain:
            pass

        monkeypatch.setattr("growth.presentation.cli.app.sys.stdout", Plain())

        _make_console_encoding_safe()  # must not raise

    def test_swallows_reconfigure_errors(self, monkeypatch) -> None:
        class Bad:
            def reconfigure(self, **kwargs: str) -> None:
                raise ValueError("nope")

        monkeypatch.setattr("growth.presentation.cli.app.sys.stdout", Bad())

        _make_console_encoding_safe()  # must not raise


class TestRun:
    def test_run_invokes_app_and_exits(self, monkeypatch) -> None:
        called: dict[str, object] = {}

        def fake_app(*, standalone_mode: bool) -> None:
            called["standalone_mode"] = standalone_mode

        monkeypatch.setattr("growth.presentation.cli.app.app", fake_app)

        with pytest.raises(SystemExit) as exc_info:
            run()

        assert exc_info.value.code == 0
        assert called == {"standalone_mode": False}
