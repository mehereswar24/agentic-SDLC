"""Provider-agnostic LLM types.

Keeping these decoupled from `google-genai` so we can swap providers (or add
LiteLLM) without touching agents downstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(slots=True)
class TokenUsage:
    prompt: int = 0
    completion: int = 0
    total: int = 0

    @classmethod
    def zero(cls) -> "TokenUsage":
        return cls()


@dataclass(slots=True)
class LLMResult(Generic[T]):
    """The result of a non-streaming LLM call.

    `parsed` is populated only when a Pydantic schema was passed to `chat()`.
    """

    text: str
    parsed: T | None = None
    usage: TokenUsage = field(default_factory=TokenUsage.zero)
    latency_ms: int = 0
    model: str = ""
    finish_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
