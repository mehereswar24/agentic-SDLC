from __future__ import annotations

import asyncio
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.agents.planner import PlannerOutput
from app.core.config import get_settings
from app.llm.types import TokenUsage
from app.orchestrator import runtime as runtime_module
from app.orchestrator.events import _reset_event_bus, get_event_bus
from app.orchestrator.runner import Orchestrator
from app.orchestrator.runtime import OrchestratorRuntime
from tests.fixtures import make_critique, make_prd


class _FastPlanner:
    name = "planner"

    async def draft(self, prompt: str, *, context: str | None = None) -> PlannerOutput:
        return PlannerOutput(
            prd=make_prd(),
            critique=None,
            usage=TokenUsage(prompt=10, completion=50, total=60),
            latency_ms=10,
            model="stub",
            finish_reason="STOP",
        )

    async def critique(self, prd: Any) -> PlannerOutput:
        return PlannerOutput(
            prd=None,
            critique=make_critique(should_revise=False),
            usage=TokenUsage(prompt=5, completion=30, total=35),
            latency_ms=10,
            model="stub",
            finish_reason="STOP",
        )

    async def revise(self, prd: Any, critique: Any) -> PlannerOutput:  # pragma: no cover
        raise AssertionError("revise should not be called when should_revise=False")


@pytest_asyncio.fixture
async def configured_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> OrchestratorRuntime:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    get_settings.cache_clear()
    _reset_event_bus()

    bus = get_event_bus()

    def factory() -> Orchestrator:
        from app.orchestrator.repository import RunRepository

        return Orchestrator(
            repo=RunRepository(),
            bus=bus,
            agent_factory=lambda: _FastPlanner(),  # type: ignore[arg-type]
        )

    runtime = OrchestratorRuntime(orchestrator_factory=factory)
    runtime_module.set_runtime(runtime)
    try:
        yield runtime
    finally:
        await runtime.shutdown(timeout=5.0)
        runtime_module._reset_runtime()


async def _wait_for_run(
    client: AsyncClient, run_id: str, *, timeout: float = 5.0
) -> dict[str, Any]:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        res = await client.get(f"/api/runs/{run_id}")
        assert res.status_code == 200
        body = res.json()
        if body["status"] in {"completed", "failed", "cancelled"}:
            return body
        await asyncio.sleep(0.05)
    raise AssertionError(f"Run {run_id} did not finish within {timeout}s")


async def test_create_and_complete_run(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    res = await client.post("/api/runs", json={"prompt": "habit tracker"})
    assert res.status_code == 201, res.text
    run_id = res.json()["id"]

    final = await _wait_for_run(client, run_id)
    assert final["status"] == "completed"
    assert final["prompt"] == "habit tracker"

    nodes = [s["node"] for s in final["steps"]]
    assert nodes == ["draft", "critique"]
    artifact_kinds = sorted(a["kind"] for a in final["artifacts"])
    assert artifact_kinds == ["critique", "prd"]
    # PRD content survived the round-trip
    prd_artifact = next(a for a in final["artifacts"] if a["kind"] == "prd")
    assert prd_artifact["content"]["title"] == "Habit Tracker"


async def test_list_runs_includes_recent(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    r1 = (await client.post("/api/runs", json={"prompt": "alpha"})).json()
    r2 = (await client.post("/api/runs", json={"prompt": "bravo"})).json()
    await _wait_for_run(client, r1["id"])
    await _wait_for_run(client, r2["id"])

    res = await client.get("/api/runs?limit=10")
    assert res.status_code == 200
    body = res.json()
    ids = [r["id"] for r in body["runs"]]
    assert r2["id"] in ids
    assert r1["id"] in ids


async def test_get_unknown_run_returns_404(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    res = await client.get("/api/runs/does-not-exist")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


async def test_create_run_requires_api_key(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    get_settings.cache_clear()
    res = await client.post("/api/runs", json={"prompt": "habit tracker"})
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "llm_unavailable"
