"""Tests for the CoderAgent — third SDLC stage (build)."""
from __future__ import annotations

from typing import Any

from app.agents.base import AgentRegistry
from app.agents.coder import CoderAgent
from app.llm.types import LLMResult, TokenUsage
from app.schemas.code import CodeBundle
from tests.fixtures import make_code, make_design, make_prd


class _StubLLM:
    model = "stub-model"

    def __init__(self, code: CodeBundle) -> None:
        self._code = code
        self.last_kwargs: dict[str, Any] | None = None

    async def chat(self, prompt: str, **kwargs: Any) -> LLMResult[CodeBundle]:
        self.last_kwargs = {"prompt": prompt, **kwargs}
        return LLMResult(
            text=self._code.model_dump_json(),
            parsed=self._code,
            usage=TokenUsage(prompt=30, completion=200, total=230),
            latency_ms=80,
            model=self.model,
            finish_reason="STOP",
        )


def test_coder_auto_registers() -> None:
    assert "coder" in AgentRegistry.names()
    assert AgentRegistry.get("coder") is CoderAgent


async def test_coder_produces_codebundle() -> None:
    expected = make_code()
    llm = _StubLLM(expected)
    agent = CoderAgent(llm=llm)  # type: ignore[arg-type]

    out = await agent.build(make_prd(), make_design())

    assert out.code.project_name == expected.project_name
    assert len(out.code.files) == 1
    assert llm.last_kwargs is not None
    assert llm.last_kwargs["schema"] is CodeBundle
    # Both prior-stage artifacts are threaded into the prompt.
    assert "PRD (JSON)" in llm.last_kwargs["prompt"]
    assert "System design (JSON)" in llm.last_kwargs["prompt"]
    assert out.latency_ms == 80
    assert out.usage.completion == 200
