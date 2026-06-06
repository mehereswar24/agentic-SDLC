"""Typed application settings loaded from environment / .env.

The Settings object is the single source of truth for runtime configuration.
Access it via `get_settings()` which caches a singleton — never instantiate
Settings() directly in feature code, so tests can override the cache.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Project root = directory containing pyproject.toml. We anchor relative SQLite
# paths here so the DB location does NOT depend on which working directory the
# process was launched from. Without this, `alembic upgrade` from `backend/`
# and `uvicorn` from the project root end up touching different files.
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    google_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Google AI Studio API key. Required before LLM features are enabled.",
    )
    gemini_model: str = Field(default="gemini-2.5-flash")
    tavily_api_key: SecretStr = Field(default=SecretStr(""))

    # Optional API key gating /api/* and /ws/*. When empty, the API is open
    # (suitable for local dev). When set, callers must present this exact
    # string as `Authorization: Bearer <key>` (REST) or `?token=<key>` (WS).
    api_key: SecretStr = Field(default=SecretStr(""))

    database_url: str = Field(default="sqlite+aiosqlite:///./agentic_sdlc.db")

    log_level: LogLevel = Field(default="INFO")

    # NoDecode prevents pydantic-settings from JSON-decoding the env value;
    # we parse the comma-separated string in the validator below.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    app_name: str = Field(default="agentic-sdlc")
    environment: Literal["dev", "test", "prod"] = Field(default="dev")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("database_url", mode="before")
    @classmethod
    def _anchor_relative_sqlite(cls, v: object) -> object:
        """Resolve relative SQLite paths against PROJECT_ROOT, not CWD."""
        if not isinstance(v, str) or not v.startswith("sqlite"):
            return v
        # Format: sqlite[+driver]:///<path>. We only rewrite when the path is
        # relative (starts with `./` or `.\`). Absolute paths and `:memory:`
        # are left untouched.
        marker = ":///"
        if marker not in v:
            return v
        scheme, path = v.split(marker, 1)
        if path in {":memory:", ""}:
            return v
        p = Path(path)
        if p.is_absolute():
            return v
        # Strip a leading "./" or ".\" so we don't end up with project_root/./file.
        if path.startswith(("./", ".\\")):
            path = path[2:]
        absolute = (PROJECT_ROOT / path).resolve().as_posix()
        return f"{scheme}:///{absolute}"

    @property
    def llm_configured(self) -> bool:
        """True when an LLM API key is present. Lets /health degrade gracefully."""
        return bool(self.google_api_key.get_secret_value())

    @property
    def auth_required(self) -> bool:
        """True when an API key is configured — callers must authenticate."""
        return bool(self.api_key.get_secret_value())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
