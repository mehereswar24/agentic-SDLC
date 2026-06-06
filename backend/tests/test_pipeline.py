"""Multi-stage SDLC pipeline: plan → design → build, with approval gates.

Drives the Orchestrator directly with stub agents (no LLM). Resuming after an
approval gate is modeled by calling `run()` again — exactly what the decision
endpoint does when it re-spawns the run.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.models import RunStatus
from app.orchestrator.events import Event, EventBus, EventType
from app.orchestrator.repository import RunRepository
from app.orchestrator.runner import Orchestrator
from tests.fixtures import FastPlanner, StubCoder, StubDesigner


@pytest.fixture
async def setup(engine: None) -> dict[str, Any]:
    return {"repo": RunRepository(), "bus": EventBus()}


def _full_orch(repo: RunRepository, bus: EventBus) -> Orchestrator:
    return Orchestrator(
        repo=repo,
        bus=bus,
        agent_factory=lambda: FastPlanner(),
        designer=StubDesigner(),
        coder=StubCoder(),
    )


async def test_auto_approve_runs_full_pipeline(setup: dict[str, Any]) -> None:
    repo: RunRepository = setup["repo"]
    run = await repo.create_run("habit tracker", meta={"auto_approve": True})

    await _full_orch(repo, setup["bus"]).run(run.id)

    final = await repo.get_run(run.id)
    assert final is not None
    assert final.status == RunStatus.COMPLETED
    assert [s.node for s in final.steps] == ["draft", "critique", "design", "build"]
    assert sorted(a.kind.value for a in final.artifacts) == [
        "code",
        "critique",
        "prd",
        "system_design",
    ]
    code_art = next(a for a in final.artifacts if a.kind.value == "code")
    assert code_art.content["project_name"] == "habit-tracker"


async def test_approval_gates_pause_then_resume(setup: dict[str, Any]) -> None:
    repo: RunRepository = setup["repo"]
    bus: EventBus = setup["bus"]
    run = await repo.create_run("habit tracker")  # auto_approve defaults to False
    orch = _full_orch(repo, bus)

    # 1. Plan stage runs, then pauses before design.
    await orch.run(run.id)
    r1 = await repo.get_run(run.id)
    assert r1 is not None
    assert r1.status == RunStatus.AWAITING_HUMAN
    assert r1.meta["awaiting_stage"] == "design"
    assert r1.meta["stage_index"] == 1
    assert sorted(a.kind.value for a in r1.artifacts) == ["critique", "prd"]

    # 2. Approve (re-run) → design stage runs, pauses before build.
    await orch.run(run.id)
    r2 = await repo.get_run(run.id)
    assert r2 is not None
    assert r2.status == RunStatus.AWAITING_HUMAN
    assert r2.meta["awaiting_stage"] == "build"
    assert r2.meta["stage_index"] == 2
    kinds2 = [a.kind.value for a in r2.artifacts]
    assert "system_design" in kinds2
    assert "code" not in kinds2

    # 3. Approve (re-run) → build stage runs, run completes.
    await orch.run(run.id)
    r3 = await repo.get_run(run.id)
    assert r3 is not None
    assert r3.status == RunStatus.COMPLETED
    assert r3.meta["awaiting_stage"] is None
    assert "code" in [a.kind.value for a in r3.artifacts]
    assert [s.node for s in r3.steps] == ["draft", "critique", "design", "build"]


async def test_awaiting_approval_event_is_published(setup: dict[str, Any]) -> None:
    repo: RunRepository = setup["repo"]
    bus: EventBus = setup["bus"]
    run = await repo.create_run("habit tracker")

    received: list[Event] = []

    async def consumer() -> None:
        async with bus.subscribe(run.id) as q:
            try:
                while True:
                    received.append(await asyncio.wait_for(q.get(), timeout=0.5))
            except TimeoutError:
                return

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0)
    await _full_orch(repo, bus).run(run.id)
    await task

    awaiting = [e for e in received if e.type == EventType.RUN_AWAITING_APPROVAL]
    assert len(awaiting) == 1
    assert awaiting[0].payload == {"completed_stage": "plan", "next_stage": "design"}
    # The run paused — it has not completed.
    assert EventType.RUN_COMPLETED not in [e.type for e in received]
