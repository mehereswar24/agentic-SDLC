"""API tests for POST /api/runs/{run_id}/chat with a mocked GeminiClient."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.llm import client as llm_client_module
from app.llm.types import LLMResult, TokenUsage
from app.orchestrator.repository import RunRepository


class _CapturingClient:
    model = "gemini-2.0-flash-exp"

    def __init__(self) -> None:
        self.last_prompt: str | None = None
        self.last_system: str | None = None

    async def chat(
        self, prompt: str, *, system: str | None = None, **_: Any
    ) -> LLMResult[Any]:
        self.last_prompt = prompt
        self.last_system = system
        return LLMResult(
            text="The run is pending and no artifacts exist yet.",
            usage=TokenUsage(prompt=20, completion=12, total=32),
            latency_ms=11,
            model=self.model,
            finish_reason="STOP",
        )


@pytest.fixture
def stub_llm(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    get_settings.cache_clear()
    llm_client_module._reset_llm_client()
    stub = _CapturingClient()
    # Patch the symbol bound inside the chat API module.
    from app.api import chat as chat_api_module

    monkeypatch.setattr(chat_api_module, "get_llm_client", lambda: stub)
    return SimpleNamespace(stub=stub)


async def test_chat_unknown_run_returns_404(
    client: AsyncClient, stub_llm: SimpleNamespace
) -> None:
    res = await client.post(
        "/api/runs/does-not-exist/chat",
        json={"message": "what's up?", "history": []},
    )
    assert res.status_code == 404, res.text
    assert res.json()["error"]["code"] == "not_found"


async def test_chat_grounds_reply_in_run_state(
    client: AsyncClient, stub_llm: SimpleNamespace
) -> None:
    run = await RunRepository().create_run(
        "Build a habit tracker", meta={"auto_approve": False}
    )

    res = await client.post(
        f"/api/runs/{run.id}/chat",
        json={"message": "What is the current progress?", "history": []},
    )

    assert res.status_code == 200, res.text
    assert res.json()["message"].startswith("The run is pending")

    # The model must be given the run's real state, not just the bare question.
    prompt = stub_llm.stub.last_prompt or ""
    assert "Build a habit tracker" in prompt
    assert "pending" in prompt
    assert "What is the current progress?" in prompt
    assert stub_llm.stub.last_system is not None


async def test_chat_replays_history(
    client: AsyncClient, stub_llm: SimpleNamespace
) -> None:
    run = await RunRepository().create_run("Build a CRM", meta={})

    res = await client.post(
        f"/api/runs/{run.id}/chat",
        json={
            "message": "And the design?",
            "history": [
                {"role": "user", "text": "Summarize the PRD"},
                {"role": "model", "text": "It targets sales teams."},
            ],
        },
    )

    assert res.status_code == 200, res.text
    prompt = stub_llm.stub.last_prompt or ""
    assert "It targets sales teams." in prompt


async def test_chat_requires_llm_configured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    get_settings.cache_clear()
    run = await RunRepository().create_run("Build a wiki", meta={})

    res = await client.post(
        f"/api/runs/{run.id}/chat",
        json={"message": "progress?", "history": []},
    )
    assert res.status_code == 503, res.text
    assert res.json()["error"]["code"] == "llm_unavailable"
