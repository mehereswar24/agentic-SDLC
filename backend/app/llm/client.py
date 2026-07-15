"""LLM client factory and FastAPI dependency.

Single shared `GeminiClient` per process (the underlying `genai.Client` reuses
HTTPX connections). Tests reset the cache via `_reset_llm_client()`.

Each SDLC stage resolves its own client via `get_stage_llm_client(stage)`, so
the hybrid setup can run, say, the planner/designer on a local Ollama model
while the coder uses Gemini (or any other mix).
"""
from __future__ import annotations

from app.core.config import get_settings
from app.core.errors import LLMUnavailableError
from app.llm.errors import LLMConfigError
from app.llm.gemini import GeminiClient
from app.llm.ollama import OllamaClient
from app.llm.groq import GroqClient
from app.llm.openrouter import OpenRouterClient
from app.llm.types import LLMClient

_client: GeminiClient | None = None
_stage_clients: dict[str, LLMClient] = {}


def get_llm_client() -> GeminiClient:
    """The shared Gemini client (also the default for any Gemini-backed stage)."""
    global _client
    if _client is not None:
        return _client
    try:
        _client = GeminiClient()
    except LLMConfigError as exc:
        raise LLMUnavailableError(str(exc)) from exc
    return _client


def _client_for_provider(provider: str) -> LLMClient:
    if provider == "ollama":
        return OllamaClient()
    if provider == "groq":
        return GroqClient()
    if provider == "openrouter":
        return OpenRouterClient()
    return get_llm_client()


def get_stage_llm_client(stage: str) -> LLMClient:
    """Client for an SDLC stage ('planner' | 'designer' | 'coder'), per config."""
    if stage in _stage_clients:
        return _stage_clients[stage]
    provider = getattr(get_settings(), f"{stage}_llm_provider", "gemini")
    client = _client_for_provider(provider)
    _stage_clients[stage] = client
    return client


def get_planner_llm_client() -> LLMClient:
    return get_stage_llm_client("planner")


def get_designer_llm_client() -> LLMClient:
    return get_stage_llm_client("designer")


def get_coder_llm_client() -> LLMClient:
    return get_stage_llm_client("coder")


def get_sprint_planner_llm_client() -> LLMClient:
    return get_stage_llm_client("sprint_planner")


def get_tester_llm_client() -> LLMClient:
    return get_stage_llm_client("tester")


def _reset_llm_client() -> None:
    """Test hook — drop the cached clients so the next call rebuilds them."""
    global _client
    _client = None
    _stage_clients.clear()
