"""Unit tests for Settings validation, logging setup, and domain identity types."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import pytest

from growth.application.errors import ApplicationError, ConflictDetectedError
from growth.application.ports.clock import utc_now
from growth.domain.shared import InternalId, SpaceId
from growth.infrastructure.config.settings import Environment, Settings
from growth.infrastructure.logging.setup import (
    configure_logging,
    get_logger,
    reset_logging,
)


class TestSettings:
    def test_defaults(self) -> None:
        settings = Settings(_env_file=None)
        assert settings.environment is Environment.DEVELOPMENT
        assert settings.log_level == "INFO"
        assert settings.todoist_api_token is None
        assert settings.is_testing is False
        assert settings.is_production is False

    def test_environment_tiers(self) -> None:
        assert Settings(_env_file=None, environment="testing").is_testing
        assert Settings(
            _env_file=None, environment="production", data_dir="C:/tmp/growth-data"
        ).is_production

    def test_production_rejects_default_data_dir(self) -> None:
        with pytest.raises(ValueError, match="GROWTH_DATA_DIR must be set explicitly"):
            Settings(_env_file=None, environment="production")

    def test_invalid_log_level_rejected(self) -> None:
        with pytest.raises(ValueError, match="GROWTH_LOG_LEVEL"):
            Settings(_env_file=None, log_level="chatty")

    def test_log_level_uppercased(self) -> None:
        settings = Settings(_env_file=None, log_level="warning")
        assert settings.log_level == "WARNING"

    def test_accepts_all_valid_log_levels(self) -> None:
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            assert Settings(_env_file=None, log_level=level).log_level == level

    def test_env_prefix_loading(self, monkeypatch) -> None:
        monkeypatch.setenv("GROWTH_LOG_LEVEL", "debug")
        monkeypatch.setenv("GROWTH_ENVIRONMENT", "testing")
        monkeypatch.setenv("GROWTH_TODOIST_API_TOKEN", "tok-123")

        settings = Settings(_env_file=None)

        assert settings.log_level == "DEBUG"
        assert settings.environment is Environment.TESTING
        assert settings.todoist_api_token == "tok-123"


class TestLoggingSetup:
    def test_configure_with_file_handler(self, tmp_path) -> None:
        reset_logging()
        try:
            log_file = tmp_path / "growth.jsonl"
            settings = Settings(
                _env_file=None,
                data_dir=tmp_path,
                environment="testing",
                log_level="debug",
                log_file=log_file,
            )
            configure_logging(settings)

            log = get_logger("growth.test")
            log.info("hello", key="value")

            assert log_file.exists()
            content = log_file.read_text(encoding="utf-8")
            assert "hello" in content
            assert "value" in content
        finally:
            reset_logging()

    def test_configure_without_file_no_file_created(self, tmp_path) -> None:
        reset_logging()
        try:
            settings = Settings(
                _env_file=None,
                data_dir=tmp_path,
                environment="testing",
                log_file=None,
            )
            configure_logging(settings)
            log = get_logger("growth.test")
            log.info("console only")
            assert not list(tmp_path.glob("*.log"))
        finally:
            reset_logging()

    def test_configure_idempotent(self, tmp_path) -> None:
        reset_logging()
        try:
            settings = Settings(
                _env_file=None,
                data_dir=tmp_path,
                environment="testing",
                log_file=tmp_path / "one.jsonl",
            )
            configure_logging(settings)
            configure_logging(settings)  # second call is a no-op
            get_logger("growth.test").info("idempotent")
            assert (tmp_path / "one.jsonl").exists()
        finally:
            reset_logging()


class TestConflictDetectedError:
    def test_carries_conflict_paths(self) -> None:
        err = ConflictDetectedError("conflict", conflicts=["task.title"])
        assert err.conflicts == ["task.title"]
        assert str(err) == "conflict"
        assert isinstance(err, ApplicationError)

    def test_default_conflicts_empty(self) -> None:
        err = ConflictDetectedError("plain")
        assert err.conflicts == []


class TestUtcNow:
    def test_returns_aware_utc_datetime(self) -> None:
        now = utc_now()
        assert now.tzinfo is not None
        assert now.utcoffset() == timedelta(0)


class TestInternalId:
    def test_from_string_roundtrip(self) -> None:
        raw = "123e4567-e89b-12d3-a456-426614174000"
        parsed = InternalId.from_string(raw)
        assert str(parsed) == raw
        assert parsed.value == UUID(raw)

    def test_from_string_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            InternalId.from_string("not-a-uuid")

    def test_equality_and_hash(self) -> None:
        a = InternalId.from_string("123e4567-e89b-12d3-a456-426614174000")
        b = InternalId.from_string("123e4567-e89b-12d3-a456-426614174000")
        c = InternalId()
        assert a == b
        assert hash(a) == hash(b)
        assert a != c
        assert len({a, b, c}) == 2

    def test_repr(self) -> None:
        iid = InternalId()
        assert repr(iid).startswith("InternalId(")

    def test_eq_with_non_internal_id_is_false(self) -> None:
        assert InternalId() != "not-an-id"
        assert InternalId() != 42


class TestSpaceId:
    def test_equality_and_hash(self) -> None:
        a = SpaceId(UUID("123e4567-e89b-12d3-a456-426614174000"))
        b = SpaceId(UUID("123e4567-e89b-12d3-a456-426614174000"))
        c = SpaceId()
        assert a == b
        assert a != c
        assert hash(a) == hash(b)

    def test_str_and_repr(self) -> None:
        raw = UUID("123e4567-e89b-12d3-a456-426614174000")
        sid = SpaceId(raw)
        assert str(sid) == str(raw)
        assert repr(sid) == f"SpaceId({raw!r})"

    def test_default_generates_fresh(self) -> None:
        assert SpaceId() != SpaceId()

    def test_eq_with_non_space_id_is_false(self) -> None:
        assert SpaceId() != "not-a-space"
