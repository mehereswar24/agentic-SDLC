"""LLM diagnostic endpoints — small, cheap calls used to verify provider health.

The `/llm/ping` route issues a trivial generation to confirm that the API key
works and to surface real latency/token metrics. It is intentionally restricted
to dev environments so it can't be abused as a free LLM proxy in production.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.errors import LLMUnavailableError
from app.llm.client import get_llm_client
from app.llm.errors import LLMError

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/ping")
async def llm_ping(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    if settings.environment != "dev":
        raise LLMUnavailableError("/llm/ping is only available in dev environment.")
    if not settings.llm_configured:
        raise LLMUnavailableError("GOOGLE_API_KEY not configured.")

    client = get_llm_client()
    try:
        result = await client.chat(
            "Reply with exactly the word: pong",
            temperature=0.0,
            max_output_tokens=8,
        )
    except LLMError as exc:
        raise LLMUnavailableError(str(exc)) from exc

    return {
        "model": result.model,
        "text": result.text.strip(),
        "latency_ms": result.latency_ms,
        "tokens_in": result.usage.prompt,
        "tokens_out": result.usage.completion,
        "finish_reason": result.finish_reason,
    }
