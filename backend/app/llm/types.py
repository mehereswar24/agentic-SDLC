"""Provider-agnostic LLM types.

Keeping these decoupled from `google-genai` so we can swap providers (or add
LiteLLM) without touching agents downstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

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


@runtime_checkable
class LLMClient(Protocol):
    """Structural interface shared by every provider client (Gemini, Ollama…).

    Agents depend on this protocol rather than a concrete class, so the coder
    stage can run on a different provider than the planner/designer.
    """

    @property
    def model(self) -> str: ...

    async def chat(
        self,
        prompt: str,
        *,
        system: str | None = ...,
        schema: type[BaseModel] | None = ...,
        temperature: float = ...,
        max_output_tokens: int | None = ...,
    ) -> "LLMResult[Any]": ...
