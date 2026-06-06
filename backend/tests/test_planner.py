from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from app.agents.planner import PlannerAgent, render_prd_markdown
from app.core.config import get_settings
from app.llm.types import LLMResult, TokenUsage
from app.schemas import PRD, Critique
from tests.fixtures import make_critique, make_prd


class _StubLLM:
    """Programmable LLM stub. Each call pops the next scripted response."""

    def __init__(self, responses: list[LLMResult[Any]]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.model = "stub-model"

    async def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        schema: type[BaseModel] | None = None,
        temperature: float = 0.7,
        max_output_tokens: int | None = None,
    ) -> LLMResult[Any]:
        self.calls.append(
            {
                "prompt": prompt,
                "system": system,
                "schema": schema,
                "temperature": temperature,
            }
        )
        if not self._responses:
            raise AssertionError("No more scripted responses")
        return self._responses.pop(0)


def _make_result(parsed: Any) -> LLMResult[Any]:
    return LLMResult(
        text=parsed.model_dump_json() if hasattr(parsed, "model_dump_json") else "",
        parsed=parsed,
        usage=TokenUsage(prompt=50, completion=200, total=250),
        latency_ms=120,
        model="stub-model",
        finish_reason="STOP",
    )


@pytest.fixture(autouse=True)
def _stub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    get_settings.cache_clear()


async def test_draft_returns_prd_and_telemetry() -> None:
    expected_prd = make_prd()
    llm = _StubLLM([_make_result(expected_prd)])
    agent = PlannerAgent(llm=llm)  # type: ignore[arg-type]

    out = await agent.draft("build a habit tracker")

    assert out.prd is not None
    assert out.prd.title == "Habit Tracker"
    assert out.usage.completion == 200
    assert out.latency_ms == 120
    assert llm.calls[0]["schema"] is PRD
    assert llm.calls[0]["temperature"] == PlannerAgent.DRAFT_TEMPERATURE
    assert "User request" in llm.calls[0]["prompt"]


async def test_draft_includes_context_when_provided() -> None:
    llm = _StubLLM([_make_result(make_prd())])
    agent = PlannerAgent(llm=llm)  # type: ignore[arg-type]

    await agent.draft("build a habit tracker", context="research: people lapse in 2 weeks")

    user_prompt = llm.calls[0]["prompt"]
    assert "Additional context" in user_prompt
    assert "lapse in 2 weeks" in user_prompt


async def test_critique_returns_score() -> None:
    expected = make_critique(score=88, should_revise=True)
    llm = _StubLLM([_make_result(expected)])
    agent = PlannerAgent(llm=llm)  # type: ignore[arg-type]

    out = await agent.critique(make_prd())

    assert out.critique is not None
    assert out.critique.score == 88
    assert out.critique.should_revise is True
    assert llm.calls[0]["schema"] is Critique
    assert llm.calls[0]["temperature"] == PlannerAgent.CRITIQUE_TEMPERATURE


async def test_revise_passes_prd_and_critique_to_llm() -> None:
    revised = make_prd(title="Habit Tracker v2")
    llm = _StubLLM([_make_result(revised)])
    agent = PlannerAgent(llm=llm)  # type: ignore[arg-type]

    out = await agent.revise(make_prd(), make_critique())

    assert out.prd is not None
    assert out.prd.title == "Habit Tracker v2"
    prompt = llm.calls[0]["prompt"]
    assert "Existing PRD" in prompt
    assert "Critique to address" in prompt
    assert llm.calls[0]["schema"] is PRD


async def test_render_markdown_includes_key_sections() -> None:
    md = render_prd_markdown(make_prd())
    for header in (
        "# Habit Tracker",
        "## Problem Statement",
        "## Goals",
        "## Non-Goals",
        "## User Stories",
        "### US-01",
        "## Success Metrics",
    ):
        assert header in md, f"missing section: {header!r}\n\n{md}"


async def test_full_loop_draft_then_critique_then_revise() -> None:
    initial = make_prd()
    revised = make_prd(title="Habit Tracker Pro")
    critique = make_critique(score=75, should_revise=True)
    llm = _StubLLM(
        [_make_result(initial), _make_result(critique), _make_result(revised)]
    )
    agent = PlannerAgent(llm=llm)  # type: ignore[arg-type]

    draft_out = await agent.draft("habits")
    crit_out = await agent.critique(draft_out.prd)  # type: ignore[arg-type]
    rev_out = await agent.revise(draft_out.prd, crit_out.critique)  # type: ignore[arg-type]

    assert draft_out.prd is not None
    assert crit_out.critique is not None
    assert crit_out.critique.should_revise is True
    assert rev_out.prd is not None
    assert rev_out.prd.title == "Habit Tracker Pro"
    assert len(llm.calls) == 3
