"""LLM client factory and FastAPI dependency.

Single shared `GeminiClient` per process (the underlying `genai.Client` reuses
HTTPX connections). Tests reset the cache via `_reset_llm_client()`.
"""
from __future__ import annotations

from app.core.errors import LLMUnavailableError
from app.llm.errors import LLMConfigError
from app.llm.gemini import GeminiClient

_client: GeminiClient | None = None


def get_llm_client() -> GeminiClient:
    global _client
    if _client is not None:
        return _client
    try:
        _client = GeminiClient()
    except LLMConfigError as exc:
        raise LLMUnavailableError(str(exc)) from exc
    return _client


def _reset_llm_client() -> None:
    """Test hook — drop the cached client so the next call rebuilds it."""
    global _client
    _client = None
