"""Groq client — incredibly fast cloud inference via HTTPX.

Implements the `LLMClient` protocol for Groq, connecting to `api.groq.com/openai/v1/chat/completions`.
Groq exposes an OpenAI-compatible endpoint, making integration easy via raw `httpx`.
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

class GroqClient:
    def __init__(self, *, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        # Groq uses an API key, we will store this in a new groq_api_key env variable
        self._api_key = self._settings.groq_api_key.get_secret_value() if hasattr(self._settings, "groq_api_key") else ""
        self._model = getattr(self._settings, "groq_model", "llama-3.3-70b-versatile")
        self._timeout = 600.0
        
        if not self._api_key:
            raise LLMAPIError("GROQ_API_KEY is not configured in .env")

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

        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_output_tokens:
            # Groq's free tier has a strict 12000 TPM limit. 
            # We dynamically cap max_tokens so `prompt + max_tokens` stays under the limit.
            prompt_len = len(system or "") + len(prompt)
            estimated_prompt_tokens = prompt_len // 3.5  # rough overestimate
            remaining = max(1000, 11800 - int(estimated_prompt_tokens))
            body["max_tokens"] = min(max_output_tokens, remaining)
            
        # For Groq structured output, we use `response_format: {"type": "json_object"}`
        # Groq currently does not support strict JSON schema validation automatically on their end,
        # but standard json_object forcing works well.
        if schema is not None:
            body["response_format"] = {"type": "json_object"}
            
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post("https://api.groq.com/openai/v1/chat/completions", json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Groq API timed out after {self._timeout}s") from exc
        except httpx.HTTPError as exc:
            raise LLMAPIError(f"Groq API request failed: {exc}") from exc

        latency_ms = int((time.perf_counter() - start) * 1000)

        if resp.status_code >= 400:
            raise LLMAPIError(
                f"Groq API returned {resp.status_code}: {resp.text[:300]}",
                status_code=resp.status_code,
            )

        data = resp.json()
        choices = data.get("choices", [])
        text = choices[0].get("message", {}).get("content", "") if choices else ""
        
        usage_data = data.get("usage", {})
        usage = TokenUsage(
            prompt=usage_data.get("prompt_tokens", 0),
            completion=usage_data.get("completion_tokens", 0),
            total=usage_data.get("total_tokens", 0),
        )
        finish_reason = choices[0].get("finish_reason") if choices else None

        parsed: BaseModel | None = None
        if schema is not None:
            try:
                parsed = schema.model_validate_json(text)
            except (ValidationError, json.JSONDecodeError) as exc:
                raise LLMParseError(
                    f"Groq output failed {schema.__name__} validation: {exc}\nText was: {text[:100]}"
                ) from exc

        logger.info(
            "groq_chat",
            model=self._model,
            latency_ms=latency_ms,
            tokens_in=usage.prompt,
            tokens_out=usage.completion,
            structured=schema is not None,
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
