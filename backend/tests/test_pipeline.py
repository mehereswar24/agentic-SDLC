"""Multi-stage SDLC pipeline: clarify → plan → design → sprint_plan → build → test.

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
from app.schemas import PRD, Critique
from tests.fixtures import (
    FastPlanner,
    RaisingReviewer,
    StubCoder,
    StubDesigner,
    StubDesignReviewer,
    StubPlannerReviewer,
    StubRequirementAnalyzer,
    StubSemanticValidator,
    StubSprintPlanner,
    StubTester,
    make_critique,
)

FULL_STEP_NODES = [
    "clarify",
    "draft",
    "semantic_validate",
    "review_prd",
    "critique",
    "design",
    "semantic_validate",
    "review_architecture_reviewer",
    "review_security_reviewer",
    "sprint_plan",
    "build",
    "test",
]

FULL_ARTIFACT_KINDS = sorted(
    [
        "clarifying_questions",
        "code",
        "critique",
        "prd",
        "review_report",  # planner_reviewer
        "review_report",  # architecture_reviewer
        "review_report",  # security_reviewer
        "sprint_plan",
        "system_design",
        "test_suite",
        "validation_report",  # prd
        "validation_report",  # system_design
    ]
)


@pytest.fixture
async def setup(engine: None) -> dict[str, Any]:
    return {"repo": RunRepository(), "bus": EventBus()}


def _full_orch(
    repo: RunRepository,
    bus: EventBus,
    *,
    planner_factory: Any = None,
    coder: StubCoder | None = None,
    designer: StubDesigner | None = None,
    architecture_reviewer: Any = None,
    **overrides: Any,
) -> Orchestrator:
    return Orchestrator(
        repo=repo,
        bus=bus,
        agent_factory=planner_factory or (lambda: FastPlanner()),
        designer=designer or StubDesigner(),
        sprint_planner=overrides.get("sprint_planner") or StubSprintPlanner(),
        coder=coder or StubCoder(),
        tester=StubTester(),
        requirement_analyzer=StubRequirementAnalyzer(),
        planner_reviewer=StubPlannerReviewer(),
        architecture_reviewer=architecture_reviewer
        or StubDesignReviewer("architecture_reviewer"),
        security_reviewer=StubDesignReviewer("security_reviewer"),
        semantic_validator=StubSemanticValidator(),
    )


async def test_auto_approve_runs_full_pipeline(setup: dict[str, Any]) -> None:
    repo: RunRepository = setup["repo"]
    run = await repo.create_run("habit tracker", meta={"auto_approve": True})

    await _full_orch(repo, setup["bus"]).run(run.id)

    final = await repo.get_run(run.id)
    assert final is not None
    assert final.status == RunStatus.COMPLETED
    assert [s.node for s in final.steps] == FULL_STEP_NODES
    assert sorted(a.kind.value for a in final.artifacts) == FULL_ARTIFACT_KINDS
    code_art = next(a for a in final.artifacts if a.kind.value == "code")
    assert code_art.content["project_name"] == "habit-tracker"


async def test_approval_gates_pause_then_resume(setup: dict[str, Any]) -> None:
    repo: RunRepository = setup["repo"]
    bus: EventBus = setup["bus"]
    run = await repo.create_run("habit tracker")  # auto_approve defaults to False
    orch = _full_orch(repo, bus)

    # 1. Clarify stage runs, then pauses before plan.
    await orch.run(run.id)
    r1 = await repo.get_run(run.id)
    assert r1 is not None
    assert r1.status == RunStatus.AWAITING_HUMAN
    assert r1.meta["awaiting_stage"] == "plan"
    assert r1.meta["stage_index"] == 1
    assert [a.kind.value for a in r1.artifacts] == ["clarifying_questions"]

    # 2. Approve (re-run) → plan stage runs, pauses before design.
    await orch.run(run.id)
    r2 = await repo.get_run(run.id)
    assert r2 is not None
    assert r2.status == RunStatus.AWAITING_HUMAN
    assert r2.meta["awaiting_stage"] == "design"
    assert r2.meta["stage_index"] == 2
    kinds2 = [a.kind.value for a in r2.artifacts]
    assert "prd" in kinds2 and "critique" in kinds2
    assert "system_design" not in kinds2

    # 3. Approve → design stage runs (with reviews), pauses before sprint_plan.
    await orch.run(run.id)
    r3 = await repo.get_run(run.id)
    assert r3 is not None
    assert r3.status == RunStatus.AWAITING_HUMAN
    assert r3.meta["awaiting_stage"] == "sprint_plan"
    assert r3.meta["stage_index"] == 3
    kinds3 = [a.kind.value for a in r3.artifacts]
    assert "system_design" in kinds3
    assert "code" not in kinds3

    # 4. Approve → sprint_plan stage runs, pauses before build.
    await orch.run(run.id)
    r4 = await repo.get_run(run.id)
    assert r4 is not None
    assert r4.status == RunStatus.AWAITING_HUMAN
    assert r4.meta["awaiting_stage"] == "build"
    assert r4.meta["stage_index"] == 4
    assert "sprint_plan" in [a.kind.value for a in r4.artifacts]

    # 5. Approve → build + test run back-to-back, completes.
    await orch.run(run.id)
    r5 = await repo.get_run(run.id)
    assert r5 is not None
    assert r5.status == RunStatus.COMPLETED
    assert r5.meta["awaiting_stage"] is None
    assert "code" in [a.kind.value for a in r5.artifacts]
    assert "test_suite" in [a.kind.value for a in r5.artifacts]
    assert [s.node for s in r5.steps] == FULL_STEP_NODES


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
    assert awaiting[0].payload == {"completed_stage": "clarify", "next_stage": "plan"}
    # The run paused — it has not completed.
    assert EventType.RUN_COMPLETED not in [e.type for e in received]


async def test_step_progress_events_are_published(setup: dict[str, Any]) -> None:
    repo: RunRepository = setup["repo"]
    bus: EventBus = setup["bus"]
    run = await repo.create_run("habit tracker", meta={"auto_approve": True})

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

    progress = [e for e in received if e.type == EventType.STEP_PROGRESS]
    assert progress, "expected step.progress events on the bus"
    # Every progress payload carries the contract fields.
    for e in progress:
        assert set(e.payload) == {"stage", "node", "message", "agent"}
        assert e.payload["message"]
    # Stage coverage: at least one progress message per pipeline stage.
    stages = {e.payload["stage"] for e in progress}
    assert {"clarify", "plan", "design", "sprint_plan", "build", "test"} <= stages
    # A progress event follows its step.started for the build node.
    types_for_build = [
        e.type for e in received
        if e.payload.get("node") == "build" and e.type in
        (EventType.STEP_STARTED, EventType.STEP_PROGRESS)
    ]
    assert types_for_build[:2] == [EventType.STEP_STARTED, EventType.STEP_PROGRESS]


async def test_design_reviews_are_persisted(setup: dict[str, Any]) -> None:
    repo: RunRepository = setup["repo"]
    run = await repo.create_run("habit tracker", meta={"auto_approve": True})

    await _full_orch(repo, setup["bus"]).run(run.id)

    final = await repo.get_run(run.id)
    assert final is not None
    reviews = [a for a in final.artifacts if a.kind.value == "review_report"]
    reviewers = {a.content["reviewer"] for a in reviews}
    assert {"planner_reviewer", "architecture_reviewer", "security_reviewer"} == reviewers


async def test_raising_design_reviewer_is_non_blocking(setup: dict[str, Any]) -> None:
    repo: RunRepository = setup["repo"]
    run = await repo.create_run("habit tracker", meta={"auto_approve": True})

    orch = _full_orch(
        repo, setup["bus"], architecture_reviewer=RaisingReviewer("architecture_reviewer")
    )
    await orch.run(run.id)

    final = await repo.get_run(run.id)
    assert final is not None
    assert final.status == RunStatus.COMPLETED  # reviewer crash never aborts
    reviewers = {
        a.content["reviewer"]
        for a in final.artifacts
        if a.kind.value == "review_report"
    }
    assert "security_reviewer" in reviewers
    assert "architecture_reviewer" not in reviewers


async def test_sprint_plan_reaches_coder(setup: dict[str, Any]) -> None:
    repo: RunRepository = setup["repo"]
    run = await repo.create_run("habit tracker", meta={"auto_approve": True})

    coder = StubCoder()
    await _full_orch(repo, setup["bus"], coder=coder).run(run.id)

    assert coder.last_sprint_plan is not None
    assert coder.last_sprint_plan.sprints[0].id == "sprint-1"


class _AlwaysRevisePlanner(FastPlanner):
    """Critique always demands revision — exercises the max_revisions budget."""

    def __init__(self) -> None:
        self.revise_calls = 0

    async def critique(self, prd: PRD):  # type: ignore[override]
        out = await super().critique(prd)
        out.critique = make_critique(score=10, should_revise=True)
        return out

    async def revise(self, prd: PRD, critique: Critique):  # type: ignore[override]
        self.revise_calls += 1
        return await super().revise(prd, critique)


async def test_max_revisions_zero_disables_revise(setup: dict[str, Any]) -> None:
    repo: RunRepository = setup["repo"]
    run = await repo.create_run(
        "habit tracker", meta={"auto_approve": True, "max_revisions": 0}
    )
    planner = _AlwaysRevisePlanner()
    await _full_orch(repo, setup["bus"], planner_factory=lambda: planner).run(run.id)

    final = await repo.get_run(run.id)
    assert final is not None
    assert final.status == RunStatus.COMPLETED
    assert planner.revise_calls == 0


async def test_max_revisions_two_revises_twice(setup: dict[str, Any]) -> None:
    repo: RunRepository = setup["repo"]
    run = await repo.create_run(
        "habit tracker", meta={"auto_approve": True, "max_revisions": 2}
    )
    planner = _AlwaysRevisePlanner()
    await _full_orch(repo, setup["bus"], planner_factory=lambda: planner).run(run.id)

    final = await repo.get_run(run.id)
    assert final is not None
    assert final.status == RunStatus.COMPLETED
    assert planner.revise_calls == 2


async def test_clarification_answers_reach_planner(setup: dict[str, Any]) -> None:
    repo: RunRepository = setup["repo"]
    bus: EventBus = setup["bus"]
    run = await repo.create_run("habit tracker")

    captured: dict[str, Any] = {}

    class _CapturingPlanner(FastPlanner):
        async def draft(self, prompt: str, *, context: str | None = None):
            captured["context"] = context
            return await super().draft(prompt, context=context)

    orch = _full_orch(repo, bus, planner_factory=lambda: _CapturingPlanner())

    # Pause at the clarify gate, answer, resume — what the endpoint does.
    await orch.run(run.id)
    await repo.update_meta(
        run.id, {"clarification_answers": {"q-1": "Web only", "q-2": "SQLite"}}
    )
    await orch.run(run.id)

    assert captured["context"] is not None
    assert "q-1: Web only" in captured["context"]
    assert "q-2: SQLite" in captured["context"]


async def test_revision_reruns_stage_and_repauses(setup: dict[str, Any]) -> None:
    repo: RunRepository = setup["repo"]
    bus: EventBus = setup["bus"]
    run = await repo.create_run("habit tracker")
    orch = _full_orch(repo, bus)

    # Reach the plan gate (clarify pause → approve → plan pause).
    await orch.run(run.id)
    await orch.run(run.id)
    paused = await repo.get_run(run.id)
    assert paused is not None
    assert paused.meta["last_completed_stage"] == "plan"
    prd_versions = [a for a in paused.artifacts if a.kind.value == "prd"]
    assert len(prd_versions) == 1

    # Request changes — what the decision endpoint's revise branch does.
    await repo.update_meta(
        run.id,
        {"pending_revision": {"stage": "plan", "feedback": "Add offline mode."}},
    )
    await orch.run(run.id)

    revised = await repo.get_run(run.id)
    assert revised is not None
    assert revised.status == RunStatus.AWAITING_HUMAN
    assert revised.meta["awaiting_stage"] == "design"  # same gate as before
    assert revised.meta["pending_revision"] is None
    assert len(revised.meta["feedback_history"]) == 1
    assert revised.meta["feedback_history"][0]["feedback"] == "Add offline mode."
    prds = sorted(
        (a for a in revised.artifacts if a.kind.value == "prd"),
        key=lambda a: a.version,
    )
    assert len(prds) == 2
    assert prds[1].content["title"].endswith("(revised)")

    # Approving afterwards resumes the normal loop from design.
    await orch.run(run.id)
    after = await repo.get_run(run.id)
    assert after is not None
    assert after.meta["awaiting_stage"] == "sprint_plan"


async def test_design_revision_uses_feedback_and_reruns_reviews(
    setup: dict[str, Any]
) -> None:
    repo: RunRepository = setup["repo"]
    bus: EventBus = setup["bus"]
    run = await repo.create_run("habit tracker")
    designer = StubDesigner()
    orch = _full_orch(repo, bus, designer=designer)

    # Reach the design gate: clarify → plan → design pauses.
    await orch.run(run.id)
    await orch.run(run.id)
    await orch.run(run.id)
    paused = await repo.get_run(run.id)
    assert paused is not None
    assert paused.meta["last_completed_stage"] == "design"
    reviews_before = len(
        [a for a in paused.artifacts if a.kind.value == "review_report"]
    )

    await repo.update_meta(
        run.id,
        {"pending_revision": {"stage": "design", "feedback": "Use Postgres, not SQLite."}},
    )
    await orch.run(run.id)

    revised = await repo.get_run(run.id)
    assert revised is not None
    assert revised.status == RunStatus.AWAITING_HUMAN
    assert designer.last_feedback == "Use Postgres, not SQLite."
    assert designer.last_previous is not None
    designs = [a for a in revised.artifacts if a.kind.value == "system_design"]
    assert len(designs) == 2
    reviews_after = len(
        [a for a in revised.artifacts if a.kind.value == "review_report"]
    )
    assert reviews_after == reviews_before + 2  # arch + security re-ran
