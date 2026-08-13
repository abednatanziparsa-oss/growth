"""Application settings — environment-based configuration via Pydantic.

Load order (later overrides earlier):
    1. Code defaults (declared below)
    2. .env file (loaded by python-dotenv; enabled by default)
    3. Process environment variables (GROWTH_*)
    4. CLI flags (where applicable, at the presentation layer)

Secrets (API tokens) are NEVER read from the YAML config files — only
from environment variables. The architecture review (doc 2, risk W8)
requires the multi-context seam (``space``) be reserved even at
bootstrap, so ``Settings`` exposes a ``space`` field defaulting to a
single value.

Three environment tiers: ``development`` (default), ``testing``,
``production``. The ``production`` tier refuses the default data_dir
to prevent accidental cross-machine contamination.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Environment", "Settings", "default_data_dir"]


class Environment(StrEnum):
    """Environment tier. Controls logging verbosity and config strictness."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


def default_data_dir() -> Path:
    """Return the default per-user data directory (~/.growth)."""

    return Path.home() / ".growth"


class Settings(BaseSettings):
    """Application configuration loaded from environment and .env.

    All fields have sensible defaults so the system runs out of the box
    in development. Production deployment overrides via environment
    variables (``GROWTH_*``).
    """

    model_config = SettingsConfigDict(
        env_prefix="GROWTH_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Core ----------------------------------------------------------------
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Environment tier: development | testing | production.",
    )

    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG | INFO | WARNING | ERROR.",
    )

    log_file: Path | None = Field(
        default=None,
        description="Optional log file path. If unset, only console logging is active.",
    )

    data_dir: Path = Field(
        default_factory=default_data_dir,
        description="Data directory for local storage (SQLite, sync state, etc.).",
    )

    # --- AI (all optional, all off by default) -------------------------------
    ai_enabled: bool = Field(
        default=False,
        description=(
            "Set to true to enable any AI features. When false (default), "
            "all AI ports use Noop implementations — no model calls, no "
            "network, no cost."
        ),
    )

    ollama_base_url: str | None = Field(
        default=None,
        description=(
            "Ollama server base URL (e.g. http://127.0.0.1:11434). "
            "When set, an Ollama embedder is wired at bootstrap; "
            "None (default) keeps the system fully offline."
        ),
    )

    ollama_model: str = Field(
        default="bge-m3",
        description="Embedding model served by Ollama (bge-m3 is multilingual).",
    )

    # --- Reserved provider token holders (loaded from env, never logged) ----
    # Declared as separate optional fields so the wiring in kernel/ can
    # detect presence without coupling to a provider subpackage.
    todoist_api_token: str | None = Field(
        default=None,
        description="Todoist API token (read from TODOIST_API_TOKEN env var).",
    )

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    @model_validator(mode="after")
    def _validate_production_data_dir(self) -> Settings:
        """Reject the default data_dir in production.

        Production deployments must set ``GROWTH_DATA_DIR`` explicitly so
        that there is no accidental collision with a developer's home
        directory.
        """

        if (
            self.environment is Environment.PRODUCTION
            and self.data_dir == default_data_dir()
        ):
            raise ValueError(
                "GROWTH_DATA_DIR must be set explicitly in production "
                "(it cannot default to ~/.growth)."
            )
        return self

    @model_validator(mode="after")
    def _validate_log_level(self) -> Settings:
        """Coerce log level to uppercase for the logging module."""

        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = self.log_level.upper()
        if upper not in valid:
            raise ValueError(
                f"GROWTH_LOG_LEVEL={self.log_level!r} is invalid; "
                f"expected one of {sorted(valid)}."
            )
        # Use object.__setattr__ to bypass Pydantic's frozenness if any.
        self.log_level = upper
        return self

    @property
    def is_testing(self) -> bool:
        """``True`` when running under the ``testing`` environment tier."""

        return self.environment is Environment.TESTING

    @property
    def is_production(self) -> bool:
        """``True`` when running under the ``production`` environment tier."""

        return self.environment is Environment.PRODUCTION
