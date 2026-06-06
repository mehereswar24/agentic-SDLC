from __future__ import annotations

from typing import Any

import pytest

from app.agents.planner import PlannerOutput
from app.llm.errors import LLMRateLimitError
from app.llm.types import TokenUsage
from app.models import ArtifactKind, RunStatus
from app.orchestrator.events import Event, EventBus, EventType
from app.orchestrator.repository import RunRepository
from app.orchestrator.runner import Orchestrator, WorkflowConfig
from tests.fixtures import make_critique, make_prd


class _ScriptedPlanner:
    """Planner stub driven by a fixed sequence of method outcomes."""

    name = "planner"

    def __init__(
        self,
        *,
        draft_prd: Any = None,
        critiques: list[Any] | None = None,
        revised_prds: list[Any] | None = None,
        draft_raises: Exception | None = None,
        critique_raises_on: int | None = None,
    ) -> None:
        self._draft_prd = draft_prd or make_prd()
        self._critiques = list(critiques or [make_critique(should_revise=False)])
        self._revised_prds = list(revised_prds or [])
        self._draft_raises = draft_raises
        self._critique_raises_on = critique_raises_on
        self._critique_calls = 0
        self.calls: list[str] = []

    async def draft(self, prompt: str, *, context: str | None = None) -> PlannerOutput:
        self.calls.append("draft")
        if self._draft_raises is not None:
            raise self._draft_raises
        return PlannerOutput(
            prd=self._draft_prd,
            critique=None,
            usage=TokenUsage(prompt=10, completion=50, total=60),
            latency_ms=100,
            model="stub",
            finish_reason="STOP",
        )

    async def critique(self, prd: Any) -> PlannerOutput:
        self.calls.append("critique")
        idx = self._critique_calls
        self._critique_calls += 1
        if self._critique_raises_on == idx:
            raise LLMRateLimitError("rate limited")
        critique = (
            self._critiques[idx]
            if idx < len(self._critiques)
            else self._critiques[-1]
        )
        return PlannerOutput(
            prd=None,
            critique=critique,
            usage=TokenUsage(prompt=5, completion=30, total=35),
            latency_ms=60,
            model="stub",
            finish_reason="STOP",
        )

    async def revise(self, prd: Any, critique: Any) -> PlannerOutput:
        self.calls.append("revise")
        next_prd = (
            self._revised_prds[0] if self._revised_prds else make_prd(title="Revised")
        )
        if self._revised_prds:
            self._revised_prds.pop(0)
        return PlannerOutput(
            prd=next_prd,
            critique=None,
            usage=TokenUsage(prompt=20, completion=80, total=100),
            latency_ms=140,
            model="stub",
            finish_reason="STOP",
        )


async def _collect_events(bus: EventBus, run_id: str, expected: int) -> list[Event]:
    """Drain `expected` events from the bus."""
    import asyncio

    received: list[Event] = []

    async def consumer() -> None:
        async with bus.subscribe(run_id) as q:
            while len(received) < expected:
                received.append(await asyncio.wait_for(q.get(), timeout=2.0))

    return received  # noqa: SIM910 — populated by consumer task above (kept here for ref)


@pytest.fixture
async def setup(engine: None) -> dict[str, Any]:
    repo = RunRepository()
    bus = EventBus()
    return {"repo": repo, "bus": bus}


async def test_happy_path_draft_critique_no_revision(setup: dict[str, Any]) -> None:
    repo: RunRepository = setup["repo"]
    bus: EventBus = setup["bus"]
    run = await repo.create_run("habit tracker")

    planner = _ScriptedPlanner(critiques=[make_critique(score=90, should_revise=False)])
    orch = Orchestrator(
        repo=repo,
        bus=bus,
        agent_factory=lambda: planner,  # type: ignore[arg-type]
        config=WorkflowConfig(max_revisions=2),
    )
    await orch.run(run.id)

    final = await repo.get_run(run.id)
    assert final is not None
    assert final.status == RunStatus.COMPLETED
    assert planner.calls == ["draft", "critique"]
    # 1 PRD + 1 critique artifact
    artifact_kinds = sorted(a.kind.value for a in final.artifacts)
    assert artifact_kinds == [ArtifactKind.CRITIQUE.value, ArtifactKind.PRD.value]
    # Steps persisted
    nodes = [s.node for s in final.steps]
    assert nodes == ["draft", "critique"]
    # Telemetry was persisted
    assert final.steps[0].latency_ms == 100
    assert final.steps[0].tokens_out == 50


async def test_revise_loop_runs_when_critique_asks(setup: dict[str, Any]) -> None:
    repo: RunRepository = setup["repo"]
    bus: EventBus = setup["bus"]
    run = await repo.create_run("habit tracker")

    planner = _ScriptedPlanner(
        critiques=[
            make_critique(score=70, should_revise=True),
            make_critique(score=92, should_revise=False),
        ],
        revised_prds=[make_prd(title="Revised PRD")],
    )
    orch = Orchestrator(
        repo=repo,
        bus=bus,
        agent_factory=lambda: planner,  # type: ignore[arg-type]
        config=WorkflowConfig(max_revisions=1),
    )
    await orch.run(run.id)

    final = await repo.get_run(run.id)
    assert final is not None
    assert final.status == RunStatus.COMPLETED
    assert planner.calls == ["draft", "critique", "revise", "critique"]
    # 2 PRD versions + 2 critiques
    prd_versions = sorted(
        a.version for a in final.artifacts if a.kind == ArtifactKind.PRD
    )
    assert prd_versions == [1, 2]


async def test_failure_in_draft_marks_run_failed(setup: dict[str, Any]) -> None:
    repo: RunRepository = setup["repo"]
    bus: EventBus = setup["bus"]
    run = await repo.create_run("habit tracker")

    planner = _ScriptedPlanner(draft_raises=LLMRateLimitError("429 forever"))
    orch = Orchestrator(
        repo=repo,
        bus=bus,
        agent_factory=lambda: planner,  # type: ignore[arg-type]
    )
    await orch.run(run.id)

    final = await repo.get_run(run.id)
    assert final is not None
    assert final.status == RunStatus.FAILED
    assert "429 forever" in (final.error or "")
    # Single failed step persisted
    assert [s.node for s in final.steps] == ["draft"]
    assert final.steps[0].error is not None
    # No artifacts produced
    assert final.artifacts == []


async def test_events_are_published_in_order(setup: dict[str, Any]) -> None:
    import asyncio

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

    consumer_task = asyncio.create_task(consumer())
    await asyncio.sleep(0)

    planner = _ScriptedPlanner(critiques=[make_critique(should_revise=False)])
    orch = Orchestrator(
        repo=repo, bus=bus, agent_factory=lambda: planner  # type: ignore[arg-type]
    )
    await orch.run(run.id)
    await consumer_task

    types = [e.type for e in received]
    assert types[0] == EventType.RUN_STARTED
    assert EventType.STEP_STARTED in types
    assert EventType.STEP_COMPLETED in types
    assert EventType.ARTIFACT_CREATED in types
    assert types[-1] == EventType.RUN_COMPLETED


async def test_orchestrator_does_not_raise_on_unknown_run_id(
    setup: dict[str, Any],
) -> None:
    orch = Orchestrator(repo=setup["repo"], bus=setup["bus"])
    # Must not raise — runtime expects fire-and-forget semantics.
    await orch.run("non-existent-id")
