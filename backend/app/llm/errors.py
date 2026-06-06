"""LLM-layer exceptions.

Distinct from `app.core.errors.LLMUnavailableError` (the user-facing 503).
These are internal — wrap them in `LLMUnavailableError` at the API boundary.
"""
from __future__ import annotations


class LLMError(Exception):
    """Base class for LLM-layer failures."""


class LLMConfigError(LLMError):
    """Missing or invalid configuration (e.g. API key not set)."""


class LLMRateLimitError(LLMError):
    """Provider returned 429 — backoff & retry exhausted."""


class LLMTimeoutError(LLMError):
    """Provider call timed out."""


class LLMAPIError(LLMError):
    """Provider returned a non-retryable error (4xx other than 429, 5xx after retries)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMParseError(LLMError):
    """Provider returned content that failed schema validation."""
