"""API tests for the approval-gate decision endpoint.

POST /api/runs/{id}/decision  — approve (resume) or reject (cancel) a paused run.
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
from tests.fixtures import FastPlanner, StubCoder, StubDesigner


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
        return Orchestrator(
            repo=RunRepository(),
            bus=bus,
            agent_factory=lambda: FastPlanner(),
            designer=StubDesigner(),
            coder=StubCoder(),
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


_PAUSE_OR_DONE = {"awaiting_human", "completed", "failed", "cancelled"}
_TERMINAL = {"completed", "failed", "cancelled"}


async def test_approve_advances_pipeline_to_completion(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    run_id = (
        await client.post("/api/runs", json={"prompt": "habit tracker"})
    ).json()["id"]

    body = await _wait_for_status(client, run_id, _PAUSE_OR_DONE)
    assert body["status"] == "awaiting_human"
    assert body["meta"]["awaiting_stage"] == "design"

    res = await client.post(f"/api/runs/{run_id}/decision", json={"decision": "approve"})
    assert res.status_code == 200, res.text

    body = await _wait_for_status(client, run_id, _PAUSE_OR_DONE)
    assert body["status"] == "awaiting_human"
    assert body["meta"]["awaiting_stage"] == "build"

    res = await client.post(f"/api/runs/{run_id}/decision", json={"decision": "approve"})
    assert res.status_code == 200, res.text

    body = await _wait_for_status(client, run_id, _TERMINAL)
    assert body["status"] == "completed"
    assert sorted(a["kind"] for a in body["artifacts"]) == [
        "code",
        "critique",
        "prd",
        "system_design",
    ]


async def test_reject_cancels_run(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    run_id = (
        await client.post("/api/runs", json={"prompt": "habit tracker"})
    ).json()["id"]
    await _wait_for_status(client, run_id, _PAUSE_OR_DONE)

    res = await client.post(
        f"/api/runs/{run_id}/decision",
        json={"decision": "reject", "feedback": "not good enough"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "cancelled"

    body = (await client.get(f"/api/runs/{run_id}")).json()
    assert body["status"] == "cancelled"
    assert "not good enough" in (body["error"] or "")


async def test_decision_conflicts_when_not_awaiting(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    # auto_approve run runs straight to completion, so it never awaits approval.
    run_id = (
        await client.post(
            "/api/runs", json={"prompt": "habit tracker", "auto_approve": True}
        )
    ).json()["id"]
    await _wait_for_status(client, run_id, _TERMINAL)

    res = await client.post(f"/api/runs/{run_id}/decision", json={"decision": "approve"})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "conflict"


async def test_decision_unknown_run_returns_404(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    res = await client.post(
        "/api/runs/does-not-exist/decision", json={"decision": "approve"}
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"
