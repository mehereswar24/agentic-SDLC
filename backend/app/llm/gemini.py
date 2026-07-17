"""Gemini client wrapper — production-grade async LLM access.

Design choices:
- Single entry point per concern: `chat()` for one-shot calls, `stream()` for
  incremental tokens. No "smart" routing — callers pick the right method.
- Structured output via Pydantic: pass a model class, get a typed result back.
- Retries handled with tenacity (exponential backoff w/ jitter) for the few
  provider failures that are actually transient: 429, 500, 502, 503, 504, and
  network errors. All other failures bubble up immediately so bugs surface.
- All calls emit a structured log line with latency + token usage — those map
  one-to-one onto `AgentStep.latency_ms / tokens_in / tokens_out`.
"""
from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any, cast, overload

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import BaseModel, ValidationError
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.llm.errors import (
    LLMAPIError,
    LLMConfigError,
    LLMParseError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.llm.types import LLMResult, TokenUsage

logger = get_logger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, genai_errors.APIError):
        return getattr(exc, "code", None) in _RETRYABLE_STATUS
    # Network-ish errors from the underlying transport
    return isinstance(exc, (TimeoutError, ConnectionError))


def _map_api_error(exc: genai_errors.APIError) -> LLMAPIError | LLMRateLimitError:
    code = getattr(exc, "code", None)
    if code == 429:
        return LLMRateLimitError(str(exc))
    return LLMAPIError(str(exc), status_code=code)


_SCHEMA_SAFETY_CACHE: dict[type[BaseModel], bool] = {}


def _schema_is_gemini_safe(schema: type[BaseModel]) -> bool:
    """Whether Gemini's native `response_schema` can express this model.

    The Gemini API rejects JSON schemas containing `additionalProperties`
    (pydantic emits it for `dict[str, X]` map fields, e.g. PRD.section_confidence).
    Unsafe schemas fall back to schema-in-prompt structured output.
    """
    cached = _SCHEMA_SAFETY_CACHE.get(schema)
    if cached is not None:
        return cached

    def walk(node: Any) -> bool:
        if isinstance(node, dict):
            if node.get("additionalProperties") not in (None, False):
                return False
            return all(walk(v) for v in node.values())
        if isinstance(node, list):
            return all(walk(v) for v in node)
        return True

    safe = walk(schema.model_json_schema())
    _SCHEMA_SAFETY_CACHE[schema] = safe
    return safe


class GeminiClient:
    """Thin, opinionated wrapper around the official `google-genai` SDK.

    The client is safe to share across asyncio tasks — the underlying
    `genai.Client` is stateless beyond auth and configuration.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        max_attempts: int = 4,
        backoff_initial: float = 1.0,
        backoff_max: float = 30.0,
    ) -> None:
        self._settings = settings or get_settings()
        self._max_attempts = max_attempts
        self._backoff_initial = backoff_initial
        self._backoff_max = backoff_max

        api_key = self._settings.google_api_key.get_secret_value()
        if not api_key:
            raise LLMConfigError(
                "GOOGLE_API_KEY is not configured. Set it in .env or your environment."
            )
        self._client = genai.Client(api_key=api_key)
        self._model = self._settings.gemini_model

    @property
    def model(self) -> str:
        return self._model

    # ------------------------------------------------------------------ chat

    @overload
    async def chat(
        self,
        prompt: str,
        *,
        system: str | None = ...,
        schema: None = ...,
        temperature: float = ...,
        max_output_tokens: int | None = ...,
    ) -> LLMResult[BaseModel]: ...

    @overload
    async def chat[T: BaseModel](
        self,
        prompt: str,
        *,
        system: str | None = ...,
        schema: type[T],
        temperature: float = ...,
        max_output_tokens: int | None = ...,
    ) -> LLMResult[T]: ...

    async def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        schema: type[BaseModel] | None = None,
        temperature: float = 0.7,
        max_output_tokens: int | None = None,
    ) -> LLMResult[Any]:
        native_schema = schema is not None and _schema_is_gemini_safe(schema)
        if schema is not None and not native_schema:
            # Map-typed fields can't ride Gemini's response_schema — embed the
            # JSON schema in the instructions and validate the raw text instead.
            schema_doc = json.dumps(schema.model_json_schema())
            instruction = (
                "Respond with ONLY a single JSON object that conforms to this "
                f"JSON Schema (no prose, no markdown fences):\n{schema_doc}"
            )
            system = f"{system}\n\n{instruction}" if system else instruction

        config = self._build_config(
            system=system,
            schema=schema if native_schema else None,
            force_json=schema is not None,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        start = time.perf_counter()
        response = await self._call_with_retry(prompt, config)
        latency_ms = int((time.perf_counter() - start) * 1000)

        text = response.text or ""
        usage = self._extract_usage(response)
        finish_reason = self._extract_finish_reason(response)

        parsed: BaseModel | None = None
        if schema is not None:
            parsed = self._parse_structured(response, schema, text)

        logger.info(
            "gemini_chat",
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
        )

    # ---------------------------------------------------------------- stream

    async def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Yield text deltas as they arrive.

        Streaming intentionally does NOT retry — once the first chunk has been
        delivered to the caller, retrying would produce duplicates. Callers
        that need resilience should use `chat()` for the initial draft and
        stream only when responsiveness matters more than reliability.
        """
        config = self._build_config(
            system=system,
            schema=None,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        start = time.perf_counter()
        total_chars = 0
        try:
            stream = await self._client.aio.models.generate_content_stream(
                model=self._model, contents=prompt, config=config
            )
            async for chunk in stream:
                if chunk.text:
                    total_chars += len(chunk.text)
                    yield chunk.text
        except genai_errors.APIError as exc:
            raise _map_api_error(exc) from exc
        except TimeoutError as exc:
            raise LLMTimeoutError(str(exc)) from exc
        finally:
            logger.info(
                "gemini_stream",
                model=self._model,
                latency_ms=int((time.perf_counter() - start) * 1000),
                chars=total_chars,
            )

    # ---------------------------------------------------------------- internals

    def _build_config(
        self,
        *,
        system: str | None,
        schema: type[BaseModel] | None,
        temperature: float,
        max_output_tokens: int | None,
        force_json: bool = False,
    ) -> genai_types.GenerateContentConfig:
        kwargs: dict[str, Any] = {"temperature": temperature}
        if system:
            kwargs["system_instruction"] = system
        if max_output_tokens is not None:
            kwargs["max_output_tokens"] = max_output_tokens
        if schema is not None:
            kwargs["response_mime_type"] = "application/json"
            kwargs["response_schema"] = schema
        elif force_json:
            # Schema-in-prompt fallback: constrain output to JSON without a
            # native response_schema.
            kwargs["response_mime_type"] = "application/json"
        return genai_types.GenerateContentConfig(**kwargs)

    async def _call_with_retry(
        self, prompt: str, config: genai_types.GenerateContentConfig
    ) -> genai_types.GenerateContentResponse:
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._max_attempts),
                wait=wait_exponential_jitter(
                    initial=self._backoff_initial, max=self._backoff_max
                ),
                retry=retry_if_exception(_is_retryable),
                reraise=True,
            ):
                with attempt:
                    return await self._client.aio.models.generate_content(
                        model=self._model, contents=prompt, config=config
                    )
        except genai_errors.APIError as exc:
            raise _map_api_error(exc) from exc
        except TimeoutError as exc:
            raise LLMTimeoutError(str(exc)) from exc
        except ValueError as exc:
            # The SDK raises ValueError on unsupported schema/config shapes —
            # surface as an LLM error so the orchestrator fails the run cleanly.
            raise LLMAPIError(f"Gemini SDK rejected the request: {exc}") from exc
        except RetryError as exc:  # pragma: no cover — reraise=True bypasses this
            raise LLMAPIError(f"Retry budget exhausted: {exc}") from exc
        # Unreachable — AsyncRetrying with reraise=True always returns or raises.
        raise LLMAPIError("Gemini call returned no response")

    @staticmethod
    def _extract_usage(response: genai_types.GenerateContentResponse) -> TokenUsage:
        meta = getattr(response, "usage_metadata", None)
        if not meta:
            return TokenUsage.zero()
        prompt = int(getattr(meta, "prompt_token_count", 0) or 0)
        completion = int(getattr(meta, "candidates_token_count", 0) or 0)
        total = int(getattr(meta, "total_token_count", prompt + completion) or 0)
        return TokenUsage(prompt=prompt, completion=completion, total=total)

    @staticmethod
    def _extract_finish_reason(
        response: genai_types.GenerateContentResponse,
    ) -> str | None:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return None
        reason = getattr(candidates[0], "finish_reason", None)
        return str(reason) if reason is not None else None

    @staticmethod
    def _parse_structured(
        response: genai_types.GenerateContentResponse,
        schema: type[BaseModel],
        fallback_text: str,
    ) -> BaseModel:
        # The SDK already validates against `response_schema` and exposes `.parsed`.
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, schema):
            return parsed
        # Fall back to manual JSON validation when the SDK didn't pre-parse.
        try:
            return cast(BaseModel, schema.model_validate_json(fallback_text))
        except ValidationError as exc:
            raise LLMParseError(
                f"Gemini response did not match {schema.__name__}: {exc}"
            ) from exc
