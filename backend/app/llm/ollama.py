"""Ollama client — local LLM access with the same surface as GeminiClient.

Lets the orchestrator run a stage (the coder, in the hybrid setup) on a local
model served by Ollama instead of the cloud. Implements the `LLMClient`
protocol: `chat()` returns the same provider-agnostic `LLMResult`, including
Pydantic-validated structured output via Ollama's JSON-schema `format` param.

No new dependency: uses httpx (already present). The model runs locally, so
there are no quotas — but a small local model is weaker than Gemini and may
occasionally emit JSON that fails schema validation (surfaced as LLMParseError).
"""
from __future__ import annotations

import json
import time
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.llm.errors import LLMAPIError, LLMParseError, LLMTimeoutError
from app.llm.types import LLMResult, TokenUsage

logger = get_logger(__name__)


class OllamaClient:
    """Thin async wrapper around a local Ollama server's /api/chat endpoint."""

    def __init__(self, *, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._base = self._settings.ollama_base_url.rstrip("/")
        self._model = self._settings.ollama_model
        self._num_ctx = self._settings.ollama_num_ctx
        self._timeout = self._settings.ollama_timeout_sec

    @property
    def model(self) -> str:
        return self._model

    async def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        schema: type[BaseModel] | None = None,
        temperature: float = 0.7,
        max_output_tokens: int | None = None,
    ) -> LLMResult[Any]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        options: dict[str, Any] = {"temperature": temperature, "num_ctx": self._num_ctx}
        if max_output_tokens:
            options["num_predict"] = max_output_tokens

        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        # Ollama structured output: pass the JSON schema as `format`.
        if schema is not None:
            body["format"] = schema.model_json_schema()

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._base}/api/chat", json=body)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"Ollama call to {self._base} timed out after {self._timeout}s"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMAPIError(
                f"Ollama request to {self._base} failed: {exc}. "
                "Is the Ollama server running (`ollama serve`)?"
            ) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)

        if resp.status_code >= 400:
            raise LLMAPIError(
                f"Ollama returned {resp.status_code}: {resp.text[:300]}",
                status_code=resp.status_code,
            )

        data = resp.json()
        text = (data.get("message") or {}).get("content", "") or ""
        prompt_tokens = int(data.get("prompt_eval_count") or 0)
        completion_tokens = int(data.get("eval_count") or 0)
        usage = TokenUsage(
            prompt=prompt_tokens,
            completion=completion_tokens,
            total=prompt_tokens + completion_tokens,
        )
        finish_reason = data.get("done_reason") or ("stop" if data.get("done") else None)

        parsed: BaseModel | None = None
        if schema is not None:
            try:
                parsed = schema.model_validate_json(text)
            except (ValidationError, json.JSONDecodeError) as exc:
                raise LLMParseError(
                    f"Ollama output failed {schema.__name__} validation: {exc}"
                ) from exc

        logger.info(
            "ollama_chat",
            model=self._model,
            latency_ms=latency_ms,
            tokens_in=usage.prompt,
            tokens_out=usage.completion,
            structured=schema is not None,
            finish_reason=finish_reason,
        )
        return LLMResult(
            text=text,
            parsed=parsed,
            usage=usage,
            latency_ms=latency_ms,
            model=self._model,
            finish_reason=finish_reason,
            raw=data,
        )
