"""GeminiClient unit tests.

We mock the underlying `google-genai` async client so tests stay hermetic:
no network, no API key required. The retry logic is validated by raising an
APIError(code=429) on the first call and a clean response on the second.

A live integration test (`test_gemini_ping_live`) runs only when
`GOOGLE_API_KEY` is present in the env — useful as a manual smoke test, but
skipped in CI by default.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from app.core.config import get_settings
from app.llm.errors import LLMConfigError, LLMParseError, LLMRateLimitError
from app.llm.gemini import GeminiClient


class _Greeting(BaseModel):
    greeting: str
    language: str


def _make_response(
    *,
    text: str = "",
    parsed: Any = None,
    prompt_tokens: int = 12,
    completion_tokens: int = 7,
    finish_reason: str = "STOP",
) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        parsed=parsed,
        usage_metadata=SimpleNamespace(
            prompt_token_count=prompt_tokens,
            candidates_token_count=completion_tokens,
            total_token_count=prompt_tokens + completion_tokens,
        ),
        candidates=[SimpleNamespace(finish_reason=finish_reason)],
    )


def _make_client(monkeypatch: pytest.MonkeyPatch) -> GeminiClient:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
    get_settings.cache_clear()
    client = GeminiClient(backoff_initial=0.01, backoff_max=0.05, max_attempts=4)
    return client


async def test_missing_api_key_raises_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(LLMConfigError):
        GeminiClient()


async def test_chat_returns_text_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client(monkeypatch)
    mock_generate = AsyncMock(return_value=_make_response(text="hello world"))
    client._client = MagicMock()
    client._client.aio.models.generate_content = mock_generate

    result = await client.chat("say hello", temperature=0.0)

    assert result.text == "hello world"
    assert result.usage.prompt == 12
    assert result.usage.completion == 7
    assert result.usage.total == 19
    assert result.model == "gemini-2.0-flash-exp"
    assert result.latency_ms >= 0
    assert result.finish_reason == "STOP"
    mock_generate.assert_awaited_once()


async def test_chat_structured_output_returns_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client(monkeypatch)
    parsed = _Greeting(greeting="hello", language="en")
    response = _make_response(
        text='{"greeting": "hello", "language": "en"}', parsed=parsed
    )
    client._client = MagicMock()
    client._client.aio.models.generate_content = AsyncMock(return_value=response)

    result = await client.chat("greet me", schema=_Greeting)

    assert result.parsed is not None
    assert isinstance(result.parsed, _Greeting)
    assert result.parsed.greeting == "hello"
    assert result.parsed.language == "en"


async def test_chat_structured_falls_back_to_json_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If SDK doesn't pre-parse, we validate the raw text against the schema."""
    client = _make_client(monkeypatch)
    response = _make_response(
        text='{"greeting": "hi", "language": "fr"}', parsed=None
    )
    client._client = MagicMock()
    client._client.aio.models.generate_content = AsyncMock(return_value=response)

    result = await client.chat("greet me", schema=_Greeting)

    assert isinstance(result.parsed, _Greeting)
    assert result.parsed.language == "fr"


async def test_chat_structured_raises_parse_error_on_garbage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _make_client(monkeypatch)
    response = _make_response(text="not json at all", parsed=None)
    client._client = MagicMock()
    client._client.aio.models.generate_content = AsyncMock(return_value=response)

    with pytest.raises(LLMParseError):
        await client.chat("greet me", schema=_Greeting)


class _WithMapField(BaseModel):
    """Pydantic dict fields emit additionalProperties, which Gemini rejects."""

    title: str
    section_confidence: dict[str, int]


async def test_chat_map_schema_falls_back_to_prompt_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Schemas with dict fields must NOT be passed as native response_schema
    (the Gemini API raises `additionalProperties is not supported`). Instead
    the JSON schema rides in the system instruction and the raw text is
    validated locally. Regression test for the PRD.section_confidence crash.
    """
    client = _make_client(monkeypatch)
    response = _make_response(
        text='{"title": "x", "section_confidence": {"goals": 90}}', parsed=None
    )
    mock_generate = AsyncMock(return_value=response)
    client._client = MagicMock()
    client._client.aio.models.generate_content = mock_generate

    result = await client.chat("plan it", system="be terse", schema=_WithMapField)

    assert isinstance(result.parsed, _WithMapField)
    assert result.parsed.section_confidence == {"goals": 90}

    config = mock_generate.await_args.kwargs["config"]
    assert config.response_schema is None  # never sent natively
    assert config.response_mime_type == "application/json"
    assert "JSON Schema" in config.system_instruction
    assert "be terse" in config.system_instruction


async def test_chat_safe_schema_stays_native(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client(monkeypatch)
    parsed = _Greeting(greeting="hello", language="en")
    response = _make_response(
        text='{"greeting": "hello", "language": "en"}', parsed=parsed
    )
    mock_generate = AsyncMock(return_value=response)
    client._client = MagicMock()
    client._client.aio.models.generate_content = mock_generate

    await client.chat("greet me", schema=_Greeting)

    config = mock_generate.await_args.kwargs["config"]
    assert config.response_schema is _Greeting


async def test_chat_retries_on_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    from google.genai import errors as genai_errors

    client = _make_client(monkeypatch)
    rate_limit = genai_errors.APIError.__new__(genai_errors.APIError)
    rate_limit.args = ("rate limited",)
    rate_limit.code = 429
    rate_limit.message = "rate limited"

    success = _make_response(text="recovered")
    call = AsyncMock(side_effect=[rate_limit, success])
    client._client = MagicMock()
    client._client.aio.models.generate_content = call

    result = await client.chat("hi")

    assert result.text == "recovered"
    assert call.await_count == 2


async def test_chat_gives_up_after_max_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    from google.genai import errors as genai_errors

    client = _make_client(monkeypatch)
    rate_limit = genai_errors.APIError.__new__(genai_errors.APIError)
    rate_limit.args = ("rate limited",)
    rate_limit.code = 429
    rate_limit.message = "rate limited"

    call = AsyncMock(side_effect=rate_limit)
    client._client = MagicMock()
    client._client.aio.models.generate_content = call

    with pytest.raises(LLMRateLimitError):
        await client.chat("hi")
    assert call.await_count == 4  # max_attempts


async def test_stream_yields_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client(monkeypatch)

    async def fake_stream() -> AsyncIterator[Any]:
        for piece in ["hello ", "world", "!"]:
            yield SimpleNamespace(text=piece)

    client._client = MagicMock()
    client._client.aio.models.generate_content_stream = AsyncMock(
        return_value=fake_stream()
    )

    chunks: list[str] = []
    async for chunk in client.stream("hi"):
        chunks.append(chunk)

    assert chunks == ["hello ", "world", "!"]


# ---------------------------------------------------------------- live test

LIVE_KEY_PRESENT = bool(os.environ.get("GOOGLE_API_KEY", "").strip())


@pytest.mark.skipif(
    not LIVE_KEY_PRESENT,
    reason="GOOGLE_API_KEY not set — skipping live Gemini call",
)
async def test_gemini_ping_live() -> None:
    get_settings.cache_clear()
    client = GeminiClient()
    result = await client.chat(
        "Reply with exactly the word: pong",
        temperature=0.0,
        max_output_tokens=8,
    )
    assert "pong" in result.text.lower()
    assert result.usage.prompt > 0
    assert result.usage.completion > 0
