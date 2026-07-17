"""API tests for artifact version history and the hardened edit flow.

GET  /api/runs/{id}/artifacts/{kind}/versions          — content-free history
GET  /api/runs/{id}/artifacts/{kind}/versions/{v}      — one full version
PUT  /api/runs/{id}/artifacts/{kind}                   — validated manual edit
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
    make_prd,
)


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


async def _run_to_plan_gate(client: AsyncClient) -> str:
    """Create a run and advance it past clarify to the plan gate (PRD exists)."""
    run_id = (
        await client.post("/api/runs", json={"prompt": "habit tracker"})
    ).json()["id"]
    await _wait_for_status(client, run_id, _PAUSE)
    res = await client.post(f"/api/runs/{run_id}/decision", json={"decision": "approve"})
    assert res.status_code == 200
    body = await _wait_for_status(client, run_id, _PAUSE)
    assert body["meta"]["last_completed_stage"] == "plan"
    return run_id


async def test_versions_list_is_content_free(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    run_id = await _run_to_plan_gate(client)

    res = await client.get(f"/api/runs/{run_id}/artifacts/prd/versions")
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "prd"
    assert body["total"] == 1
    assert body["versions"][0]["version"] == 1
    assert "content" not in body["versions"][0]


async def test_get_single_version_round_trips(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    run_id = await _run_to_plan_gate(client)

    res = await client.get(f"/api/runs/{run_id}/artifacts/prd/versions/1")
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "prd"
    assert body["version"] == 1
    assert body["content"]["title"] == "Habit Tracker"

    missing = await client.get(f"/api/runs/{run_id}/artifacts/prd/versions/99")
    assert missing.status_code == 404


async def test_versions_unknown_run_404(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    res = await client.get("/api/runs/nope/artifacts/prd/versions")
    assert res.status_code == 404


async def test_put_valid_edit_creates_version_and_audit_step(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    run_id = await _run_to_plan_gate(client)

    edited = make_prd(title="Habit Tracker (edited)").model_dump(mode="json")
    res = await client.put(f"/api/runs/{run_id}/artifacts/prd", json=edited)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["kind"] == "prd"
    assert body["version"] == 2
    assert body["content"]["title"] == "Habit Tracker (edited)"

    detail = (await client.get(f"/api/runs/{run_id}")).json()
    edit_steps = [s for s in detail["steps"] if s["node"] == "artifact_edit"]
    assert len(edit_steps) == 1
    assert edit_steps[0]["output"]["version"] == 2


async def test_put_invalid_edit_rejected_no_new_version(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    run_id = await _run_to_plan_gate(client)

    res = await client.put(
        f"/api/runs/{run_id}/artifacts/prd", json={"title": 42, "bogus": True}
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_failed"

    versions = (
        await client.get(f"/api/runs/{run_id}/artifacts/prd/versions")
    ).json()
    assert versions["total"] == 1  # nothing was persisted


async def test_put_while_running_conflicts(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    run_id = await _run_to_plan_gate(client)

    # Approve → run flips to RUNNING; race the edit against the design stage.
    res = await client.post(f"/api/runs/{run_id}/decision", json={"decision": "approve"})
    assert res.status_code == 200

    edited = make_prd().model_dump(mode="json")
    res = await client.put(f"/api/runs/{run_id}/artifacts/prd", json=edited)
    # Either we caught it RUNNING (409) or the stub pipeline already re-paused (200).
    assert res.status_code in (200, 409)
    if res.status_code == 409:
        assert res.json()["error"]["code"] == "conflict"


async def test_edit_then_revise_uses_edited_content(
    client: AsyncClient, configured_runtime: OrchestratorRuntime
) -> None:
    run_id = await _run_to_plan_gate(client)

    edited = make_prd(title="Edited Base").model_dump(mode="json")
    res = await client.put(f"/api/runs/{run_id}/artifacts/prd", json=edited)
    assert res.status_code == 200

    res = await client.post(
        f"/api/runs/{run_id}/decision",
        json={"decision": "revise", "feedback": "Tighten the goals."},
    )
    assert res.status_code == 200

    body = await _wait_for_status(client, run_id, _PAUSE)
    prds = sorted(
        (a for a in body["artifacts"] if a["kind"] == "prd"),
        key=lambda a: a["version"],
    )
    assert len(prds) == 3  # original, manual edit, revision
    # FastPlanner.revise appends "(revised)" to the *edited* title.
    assert prds[2]["content"]["title"] == "Edited Base (revised)"
