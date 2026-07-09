"""Tests for the local Ollama client and hybrid coder routing."""
from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from app.core.config import get_settings
from app.llm import client as client_module
from app.llm import ollama as ollama_module
from app.llm.errors import LLMAPIError, LLMParseError
from app.llm.ollama import OllamaClient


class _Answer(BaseModel):
    answer: str


def _mock_async_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Make OllamaClient's httpx.AsyncClient use a MockTransport."""

    real_async_client = httpx.AsyncClient  # capture before patching

    def factory(*_args, **_kwargs):
        return real_async_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(ollama_module.httpx, "AsyncClient", factory)


async def test_ollama_structured_output_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "qwen2.5-coder:7b",
                "message": {"role": "assistant", "content": '{"answer": "42"}'},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 11,
                "eval_count": 7,
            },
        )

    _mock_async_client(monkeypatch, handler)

    result = await OllamaClient().chat(
        "What is the answer?", system="be terse", schema=_Answer, temperature=0.1
    )

    assert result.parsed == _Answer(answer="42")
    assert result.text == '{"answer": "42"}'
    assert result.usage.prompt == 11 and result.usage.completion == 7
    assert result.model == "qwen2.5-coder:7b"
    # The JSON schema was forwarded as Ollama's structured-output `format`.
    assert captured["body"]["format"]["properties"]["answer"]["type"] == "string"
    assert captured["body"]["messages"][0] == {"role": "system", "content": "be terse"}


async def test_ollama_invalid_json_raises_parse_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": {"content": "not json at all"}, "done": True},
        )

    _mock_async_client(monkeypatch, handler)
    with pytest.raises(LLMParseError):
        await OllamaClient().chat("x", schema=_Answer)


async def test_ollama_http_error_raises_api_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    _mock_async_client(monkeypatch, handler)
    with pytest.raises(LLMAPIError):
        await OllamaClient().chat("x")


def test_each_stage_routes_to_its_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    # Requirements/design on local Ollama, code on Gemini — the reverse hybrid.
    monkeypatch.setenv("PLANNER_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("DESIGNER_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("CODER_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")  # so the Gemini coder client builds
    get_settings.cache_clear()
    client_module._reset_llm_client()

    assert isinstance(client_module.get_planner_llm_client(), OllamaClient)
    assert isinstance(client_module.get_designer_llm_client(), OllamaClient)
    assert not isinstance(client_module.get_coder_llm_client(), OllamaClient)

    from app.agents.coder import CoderAgent
    from app.agents.designer import DesignerAgent
    from app.agents.planner import PlannerAgent

    assert isinstance(PlannerAgent().llm, OllamaClient)
    assert isinstance(DesignerAgent().llm, OllamaClient)
    assert not isinstance(CoderAgent().llm, OllamaClient)
