"""API tests for /llm/ping with a mocked GeminiClient."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.llm import client as llm_client_module
from app.llm.types import LLMResult, TokenUsage


class _StubClient:
    model = "gemini-2.0-flash-exp"

    async def chat(self, prompt: str, **_: Any) -> LLMResult[Any]:
        return LLMResult(
            text="pong",
            usage=TokenUsage(prompt=5, completion=1, total=6),
            latency_ms=42,
            model=self.model,
            finish_reason="STOP",
        )


@pytest.fixture
def stub_llm(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    get_settings.cache_clear()
    llm_client_module._reset_llm_client()
    stub = _StubClient()
    monkeypatch.setattr(llm_client_module, "get_llm_client", lambda: stub)
    # Also patch the symbol already bound inside the API module.
    from app.api import llm as llm_api_module

    monkeypatch.setattr(llm_api_module, "get_llm_client", lambda: stub)
    return SimpleNamespace(stub=stub)


async def test_llm_ping_returns_pong(client: AsyncClient, stub_llm: SimpleNamespace) -> None:
    res = await client.get("/llm/ping")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["text"] == "pong"
    assert body["tokens_in"] == 5
    assert body["tokens_out"] == 1
    assert body["latency_ms"] == 42


async def test_llm_ping_blocked_outside_dev(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    get_settings.cache_clear()
    res = await client.get("/llm/ping")
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "llm_unavailable"
