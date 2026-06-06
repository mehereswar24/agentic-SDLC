from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.agents.planner import PlannerAgent
from app.core.config import get_settings
from tests.fixtures import make_critique, make_prd


class _RecordingPlannerAgent:
    """Stand-in for PlannerAgent that doesn't need an LLM."""

    def __init__(self, *, critique_should_revise: bool = False) -> None:
        self._critique_should_revise = critique_should_revise
        self.calls: list[str] = []

    async def draft(self, prompt: str, *, context: str | None = None) -> Any:
        self.calls.append("draft")
        from app.agents.planner import PlannerOutput
        from app.llm.types import TokenUsage

        return PlannerOutput(
            prd=make_prd(),
            critique=None,
            usage=TokenUsage(prompt=10, completion=50, total=60),
            latency_ms=100,
            model="stub",
            finish_reason="STOP",
        )

    async def critique(self, prd: Any) -> Any:
        self.calls.append("critique")
        from app.agents.planner import PlannerOutput
        from app.llm.types import TokenUsage

        return PlannerOutput(
            prd=None,
            critique=make_critique(should_revise=self._critique_should_revise),
            usage=TokenUsage(prompt=10, completion=30, total=40),
            latency_ms=80,
            model="stub",
            finish_reason="STOP",
        )

    async def revise(self, prd: Any, critique: Any) -> Any:
        self.calls.append("revise")
        from app.agents.planner import PlannerOutput
        from app.llm.types import TokenUsage

        return PlannerOutput(
            prd=make_prd(title="Habit Tracker Revised"),
            critique=None,
            usage=TokenUsage(prompt=20, completion=80, total=100),
            latency_ms=150,
            model="stub",
            finish_reason="STOP",
        )


@pytest.fixture
def stub_planner(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    get_settings.cache_clear()

    state: dict[str, Any] = {}

    def _factory(*args: Any, **kwargs: Any) -> Any:
        agent = _RecordingPlannerAgent(
            critique_should_revise=state.get("should_revise", False)
        )
        state["agent"] = agent
        return agent

    from app.api import planner as planner_api

    monkeypatch.setattr(planner_api, "PlannerAgent", _factory)
    return state


async def test_planner_draft_endpoint(
    client: AsyncClient, stub_planner: dict[str, Any]
) -> None:
    res = await client.post("/planner/draft", json={"prompt": "habit tracker"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["prd"]["title"] == "Habit Tracker"
    assert "# Habit Tracker" in body["markdown"]
    assert body["telemetry"]["tokens_out"] == 50
    assert stub_planner["agent"].calls == ["draft"]


async def test_planner_run_no_revision_when_critique_clears(
    client: AsyncClient, stub_planner: dict[str, Any]
) -> None:
    stub_planner["should_revise"] = False
    res = await client.post(
        "/planner/run", json={"prompt": "habit tracker", "max_revisions": 2}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["prd"]["title"] == "Habit Tracker"
    assert stub_planner["agent"].calls == ["draft", "critique"]


async def test_planner_run_revises_when_critique_demands(
    client: AsyncClient, stub_planner: dict[str, Any]
) -> None:
    stub_planner["should_revise"] = True
    res = await client.post(
        "/planner/run", json={"prompt": "habit tracker", "max_revisions": 1}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["prd"]["title"] == "Habit Tracker Revised"
    # Loop: draft -> critique -> revise -> critique (final, since max_revisions=1)
    assert stub_planner["agent"].calls == ["draft", "critique", "revise", "critique"]


async def test_planner_endpoints_blocked_in_prod(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    get_settings.cache_clear()
    res = await client.post("/planner/draft", json={"prompt": "test"})
    assert res.status_code == 503
