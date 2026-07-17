"""API tests for POST /api/runs/{id}/clarifications.

The clarify stage pauses the run; this endpoint stores the user's answers in
Run.meta and resumes the pipeline, which forwards them to the planner.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.core.config import get_settings
from app.orchestrator import runtime as runtime_module
from app.orchestrator.events import _reset_event_bus, get_event_bus
from app.orchestrator.repository import RunRepository
from app.orchestrator.runner import Orchestrator
from app.orchestrator.runtime import OrchestratorRuntime
from tests.fixtures import (
    FastPlanner,
    StubCoder,
    StubDesigner,
    StubDesignReviewer,
    StubPlannerReviewer,
    StubRequirementAnalyzer,
    StubSemanticValidator,
    StubSprintPlanner,
    StubTester,
)

CAPTURED: dict[str, Any] = {}


class _CapturingPlanner(FastPlanner):
    async def draft(self, prompt: str, *, context: str | None = None):
        CAPTURED["context"] = context
        return await super().draft(prompt, context=context)


@pytest_asyncio.fixture
async def configured_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> OrchestratorRuntime:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    get_settings.cache_clear()
    _reset_event_bus()
    CAPTURED.clear()
    bus = get_event_bus()

    def factory() -> Orchestrator:
        return Orchestrator(
            repo=RunRepository(),
            bus=bus,
            agent_factory=lambda: _CapturingPlanner(),
            designer=StubDesigner(),
            sprint_planner=StubSprintPlanner(),
            coder=StubCoder(),
            tester=StubTester(),
            requirement_analyzer=StubRequirementAnalyzer(),
            planner_reviewer=StubPlannerReviewer(),
            architecture_reviewer=StubDesignReviewer("architecture_reviewer"),
            security_reviewer=StubDesignReviewer("security_reviewer"),
            semantic_validator=StubSemanticValidator(),
        )

    runtime = OrchestratorRuntime(orchestrator_factory=factory)
    runtime_module.set_runtime(runtime)
    try:
        yield runtime
    finally:
        await runtime.shutdown(timeout=5.0)
        runtime_module._reset_runtime()


async def _wait_for_status(
    client: AsyncClient,
    run_id: str,
    targets: set[str],
    *,
    timeout: float = 5.0,
) -> dict[str, Any]:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        res = await client.get(f"/api/runs/{run_id}")
        assert res.status_code == 200
        body = res.json()
        if body["status"] in targets:
            return body
        await asyncio.sleep(0.05)
    raise AssertionError(f"Run {run_id} never reached {targets} within {timeout}s")


_PAUSE = {"awaiting_human", "completed", "failed", "cancelled"}


async def test_answers_resume_run_and_reach_planner(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    run_id = (
        await client.post("/api/runs", json={"prompt": "habit tracker"})
    ).json()["id"]

    body = await _wait_for_status(client, run_id, _PAUSE)
    assert body["meta"]["last_completed_stage"] == "clarify"

    res = await client.post(
        f"/api/runs/{run_id}/clarifications",
        json={"answers": {"q-1": "Web only", "q-2": "SQLite"}},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "running"

    body = await _wait_for_status(client, run_id, _PAUSE)
    assert body["meta"]["last_completed_stage"] == "plan"
    assert body["meta"]["clarification_answers"] == {
        "q-1": "Web only",
        "q-2": "SQLite",
    }
    assert "q-1: Web only" in (CAPTURED["context"] or "")


async def test_conflicts_at_non_clarify_gate(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    run_id = (
        await client.post("/api/runs", json={"prompt": "habit tracker"})
    ).json()["id"]
    await _wait_for_status(client, run_id, _PAUSE)

    # Approve past clarify → now paused at the plan gate.
    res = await client.post(f"/api/runs/{run_id}/decision", json={"decision": "approve"})
    assert res.status_code == 200
    body = await _wait_for_status(client, run_id, _PAUSE)
    assert body["meta"]["last_completed_stage"] == "plan"

    res = await client.post(
        f"/api/runs/{run_id}/clarifications", json={"answers": {"q-1": "Web"}}
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "conflict"


async def test_conflicts_while_running(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    # auto_approve run never pauses; catching it mid-run is racy, so instead
    # submit twice at the clarify gate: the second hits the RUNNING guard.
    run_id = (
        await client.post("/api/runs", json={"prompt": "habit tracker"})
    ).json()["id"]
    await _wait_for_status(client, run_id, _PAUSE)

    first = await client.post(
        f"/api/runs/{run_id}/clarifications", json={"answers": {"q-1": "Web"}}
    )
    assert first.status_code == 200
    second = await client.post(
        f"/api/runs/{run_id}/clarifications", json={"answers": {"q-1": "iOS"}}
    )
    # The run is either still RUNNING (409) or already re-paused past clarify (409).
    assert second.status_code == 409


async def test_unknown_run_returns_404(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    res = await client.post(
        "/api/runs/does-not-exist/clarifications", json={"answers": {"q-1": "x"}}
    )
    assert res.status_code == 404


async def test_empty_answers_rejected(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    run_id = (
        await client.post("/api/runs", json={"prompt": "habit tracker"})
    ).json()["id"]
    await _wait_for_status(client, run_id, _PAUSE)

    res = await client.post(
        f"/api/runs/{run_id}/clarifications", json={"answers": {}}
    )
    assert res.status_code == 422
