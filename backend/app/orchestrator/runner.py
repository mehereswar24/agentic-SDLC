"""Orchestrator — drives the SDLC pipeline for a single Run.

Pipeline (default):

    plan → [approval] → design → [approval] → build → done

The **plan** stage runs the planner's own loop:

    draft → critique → [revise → critique]*  → (PRD)

Approval gates pause the run at `AWAITING_HUMAN` between stages (unless the run
was created with `auto_approve`). A paused run is resumable: the background task
exits, and `POST /api/runs/{id}/decision` spawns a fresh task that calls
`run()` again — which reads `meta.stage_index` and continues from the next
stage. Each stage reloads its inputs from persisted artifacts, so resumption is
stateless.

Backward-compatibility: constructing the orchestrator with a single
`agent_factory` (and no designer/coder) yields a **planner-only** pipeline that
runs straight to completion with no approval gate — the original behavior.

Each step:
  1. Publishes `step.started`.
  2. Calls the agent.
  3. Persists an `AgentStep` row (input/output/latency/tokens).
  4. Persists an `Artifact` row when the step produces one.
  5. Publishes `step.completed` (or `step.failed`).

The orchestrator never lets an exception escape `run()` — failures are
persisted to the AgentStep + Run, the right event is published, and it returns.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.agents.coder import CoderAgent
from app.agents.designer import DesignerAgent
from app.agents.planner import PlannerAgent, PlannerOutput
from app.agents.sprint_planner import SprintPlannerAgent
from app.agents.tester import TesterAgent
from app.core.logging import get_logger
from app.llm.errors import LLMError
from app.models import ArtifactKind, RunStatus
from app.orchestrator.events import Event, EventBus, EventType, get_event_bus
from app.orchestrator.repository import RunRepository
from app.schemas import PRD, Critique, SystemDesign, SprintPlan
from app.schemas.code import CodeBundle

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class WorkflowConfig:
    """Tunables for the planning stage.

    Defaults err on the side of cost/latency containment for the free-tier
    Gemini key. Bump `max_revisions` when running with a paid plan.
    """

    max_revisions: int = 1
    revision_score_threshold: int = 80


@dataclass(frozen=True, slots=True)
class StageSpec:
    """One stage in the pipeline plus whether it requires human approval before
    the pipeline may advance to the next stage."""

    name: str
    requires_approval: bool


# Maps a stage name to the agent name persisted on AgentStep.agent / event payloads.
_STAGE_AGENT = {
    "plan": "planner",
    "design": "designer",
    "sprint_plan": "sprint_planner",
    "build": "coder",
    "test": "tester",
}


class _StageAborted(Exception):
    """Internal signal: a stage failed and already recorded its failure.

    Raised after `_fail_step`/`_fail` have persisted state and published events,
    so `run()` simply stops without double-reporting.
    """


class Orchestrator:
    def __init__(
        self,
        *,
        repo: RunRepository | None = None,
        bus: EventBus | None = None,
        agent_factory: Callable[[], Any] | None = None,
        designer: Any | None = None,
        coder: Any | None = None,
        config: WorkflowConfig | None = None,
        **kwargs: Any,
    ) -> None:
        self._repo = repo or RunRepository()
        self._bus = bus or get_event_bus()
        self._planner_factory: Callable[[], Any] = agent_factory or PlannerAgent
        self._designer = designer
        self._sprint_planner = kwargs.get("sprint_planner")
        self._coder = coder
        self._tester = kwargs.get("tester")
        self._config = config or WorkflowConfig()

        # Planner-only (legacy) mode when only a planner factory is supplied:
        # one stage, no approval gate, runs straight to completion.
        plan_only = (
            agent_factory is not None and designer is None and coder is None
            and not self._sprint_planner and not self._tester
        )
        if plan_only:
            self._stages: list[StageSpec] = [StageSpec("plan", requires_approval=False)]
        else:
            self._stages = [
                StageSpec("plan", requires_approval=True),
                StageSpec("design", requires_approval=True),
                StageSpec("sprint_plan", requires_approval=True),
                StageSpec("build", requires_approval=False),
                StageSpec("test", requires_approval=False),
            ]

    # -------------------------------------------------------------- entrypoint

    async def run(self, run_id: str) -> None:
        """Execute (or resume) the pipeline for `run_id`.

        Safe to call as a fire-and-forget background task — never raises.
        """
        log = logger.bind(run_id=run_id)
        run = await self._repo.get_run(run_id)
        if run is None:
            log.error("orchestrator_run_not_found")
            return

        meta = dict(run.meta or {})
        auto_approve = bool(meta.get("auto_approve", False))
        start_index = int(meta.get("stage_index", 0))

        await self._repo.set_status(run_id, RunStatus.RUNNING)
        if start_index == 0:
            await self._publish(
                EventType.RUN_STARTED,
                run_id,
                {"prompt": run.prompt, "pipeline": [s.name for s in self._stages]},
            )
        else:
            await self._publish(
                EventType.RUN_RESUMED,
                run_id,
                {"stage": self._stages[start_index].name},
            )

        for i in range(start_index, len(self._stages)):
            stage = self._stages[i]
            try:
                await self._run_stage(stage.name, run_id, run.prompt)
            except _StageAborted:
                return  # failure already persisted + published

            next_index = i + 1
            has_next = next_index < len(self._stages)
            if has_next and stage.requires_approval and not auto_approve:
                next_stage = self._stages[next_index].name
                # Persist resume point + pending-approval state, then pause.
                await self._repo.update_meta(
                    run_id,
                    {
                        "stage_index": next_index,
                        "awaiting_stage": next_stage,
                        "last_completed_stage": stage.name,
                    },
                )
                await self._repo.set_status(run_id, RunStatus.AWAITING_HUMAN)
                await self._publish(
                    EventType.RUN_AWAITING_APPROVAL,
                    run_id,
                    {"completed_stage": stage.name, "next_stage": next_stage},
                )
                log.info("orchestrator_awaiting_approval", completed_stage=stage.name)
                return

        # All stages done. Only touch meta if an earlier pause left state to
        # clear — keeps the common straight-through path free of extra writes.
        if start_index > 0 or meta.get("awaiting_stage"):
            await self._repo.update_meta(
                run_id,
                {
                    "stage_index": len(self._stages),
                    "awaiting_stage": None,
                    "last_completed_stage": self._stages[-1].name,
                },
            )
        await self._repo.set_status(run_id, RunStatus.COMPLETED)
        await self._publish(
            EventType.RUN_COMPLETED,
            run_id,
            {"stages": [s.name for s in self._stages]},
        )
        log.info("orchestrator_run_completed")

    async def _run_stage(self, name: str, run_id: str, prompt: str) -> None:
        if name == "plan":
            await self._stage_plan(run_id, prompt)
        elif name == "design":
            await self._stage_design(run_id)
        elif name == "sprint_plan":
            await self._stage_sprint_plan(run_id)
        elif name == "build":
            await self._stage_build(run_id)
        elif name == "test":
            await self._stage_test(run_id)
        else:  # pragma: no cover — guarded by StageSpec construction
            raise ValueError(f"Unknown stage '{name}'")

    # ------------------------------------------------------------- plan stage

    async def _stage_plan(self, run_id: str, prompt: str) -> None:
        try:
            agent = self._planner_factory()
        except Exception as exc:  # pragma: no cover — defensive
            await self._fail(run_id, f"Failed to initialize planner: {exc}")
            raise _StageAborted from exc

        prd = await self._step_draft(run_id, agent, prompt)
        for iteration in range(self._config.max_revisions + 1):
            critique = await self._step_critique(run_id, agent, prd, iteration)
            if not self._should_revise(critique, iteration):
                break
            prd = await self._step_revise(run_id, agent, prd, critique, iteration)

    async def _step_draft(
        self, run_id: str, agent: Any, prompt: str
    ) -> PRD:
        await self._publish(EventType.STEP_STARTED, run_id, {"node": "draft"})
        try:
            out = await agent.draft(prompt)
        except LLMError as exc:
            await self._fail_step(run_id, "draft", agent.name, exc)
            raise _StageAborted from exc

        assert out.prd is not None
        await self._persist_step(run_id, "draft", agent.name, out, {"prompt": prompt})
        await self._persist_artifact(
            run_id, ArtifactKind.PRD, out.prd.model_dump(mode="json")
        )
        await self._publish(
            EventType.STEP_COMPLETED, run_id, self._step_payload("draft", out)
        )
        return out.prd

    async def _step_critique(
        self, run_id: str, agent: Any, prd: PRD, iteration: int
    ) -> Critique:
        await self._publish(
            EventType.STEP_STARTED,
            run_id,
            {"node": "critique", "iteration": iteration},
        )
        try:
            out = await agent.critique(prd)
        except LLMError as exc:
            await self._fail_step(run_id, "critique", agent.name, exc)
            raise _StageAborted from exc

        assert out.critique is not None
        await self._persist_step(
            run_id, "critique", agent.name, out, {"iteration": iteration}
        )
        await self._persist_artifact(
            run_id,
            ArtifactKind.CRITIQUE,
            {**out.critique.model_dump(mode="json"), "iteration": iteration},
        )
        await self._publish(
            EventType.STEP_COMPLETED,
            run_id,
            {
                **self._step_payload("critique", out),
                "iteration": iteration,
                "score": out.critique.score,
                "should_revise": out.critique.should_revise,
            },
        )
        return out.critique

    async def _step_revise(
        self, run_id: str, agent: Any, prd: PRD, critique: Critique, iteration: int
    ) -> PRD:
        await self._publish(
            EventType.STEP_STARTED,
            run_id,
            {"node": "revise", "iteration": iteration},
        )
        try:
            out = await agent.revise(prd, critique)
        except LLMError as exc:
            await self._fail_step(run_id, "revise", agent.name, exc)
            raise _StageAborted from exc

        assert out.prd is not None
        await self._persist_step(
            run_id,
            "revise",
            agent.name,
            out,
            {"iteration": iteration, "from_score": critique.score},
        )
        await self._persist_artifact(
            run_id, ArtifactKind.PRD, out.prd.model_dump(mode="json")
        )
        await self._publish(
            EventType.STEP_COMPLETED,
            run_id,
            {**self._step_payload("revise", out), "iteration": iteration},
        )
        return out.prd

    # ----------------------------------------------------------- design stage

    async def _stage_design(self, run_id: str) -> None:
        prd = await self._load_prd(run_id, stage="design")
        designer = self._designer if self._designer is not None else DesignerAgent()

        await self._publish(EventType.STEP_STARTED, run_id, {"node": "design"})
        try:
            out = await designer.design(prd)
        except LLMError as exc:
            await self._fail_step(run_id, "design", "designer", exc)
            raise _StageAborted from exc

        await self._persist_stage_step(
            run_id,
            "design",
            "designer",
            output={
                "title": out.design.title,
                "components": len(out.design.components),
                "data_models": len(out.design.data_models),
            },
            out=out,
        )
        await self._persist_artifact(
            run_id, ArtifactKind.SYSTEM_DESIGN, out.design.model_dump(mode="json")
        )
        await self._publish(
            EventType.STEP_COMPLETED, run_id, self._step_payload("design", out)
        )

    # ------------------------------------------------------------ build stage

    async def _stage_build(self, run_id: str) -> None:
        prd = await self._load_prd(run_id, stage="build")
        design = await self._load_design(run_id)
        coder = self._coder if self._coder is not None else CoderAgent()

        await self._publish(EventType.STEP_STARTED, run_id, {"node": "build"})
        try:
            out = await coder.build(prd, design)
        except LLMError as exc:
            await self._fail_step(run_id, "build", "coder", exc)
            raise _StageAborted from exc

        await self._persist_stage_step(
            run_id,
            "build",
            "coder",
            output={
                "project_name": out.code.project_name,
                "files": len(out.code.files),
                "tech_stack": out.code.tech_stack,
            },
            out=out,
        )
        await self._persist_artifact(
            run_id, ArtifactKind.CODE, out.code.model_dump(mode="json")
        )
        await self._publish(
            EventType.STEP_COMPLETED, run_id, self._step_payload("build", out)
        )

    # ------------------------------------------------------- sprint plan stage

    async def _stage_sprint_plan(self, run_id: str) -> None:
        prd = await self._load_prd(run_id, stage="sprint_plan")
        design = await self._load_design(run_id)
        sprint_planner = self._sprint_planner if self._sprint_planner is not None else SprintPlannerAgent()

        await self._publish(EventType.STEP_STARTED, run_id, {"node": "sprint_plan"})
        try:
            out = await sprint_planner.plan(prd, design)
        except LLMError as exc:
            await self._fail_step(run_id, "sprint_plan", "sprint_planner", exc)
            raise _StageAborted from exc

        await self._persist_stage_step(
            run_id,
            "sprint_plan",
            "sprint_planner",
            output={
                "sprints": len(out.plan.sprints),
            },
            out=out,
        )
        await self._persist_artifact(
            run_id, ArtifactKind.SPRINT_PLAN, out.plan.model_dump(mode="json")
        )
        await self._publish(
            EventType.STEP_COMPLETED, run_id, self._step_payload("sprint_plan", out)
        )

    # ------------------------------------------------------------- test stage

    async def _stage_test(self, run_id: str) -> None:
        code = await self._load_code(run_id)
        tester = self._tester if self._tester is not None else TesterAgent()

        await self._publish(EventType.STEP_STARTED, run_id, {"node": "test"})
        try:
            out = await tester.generate_tests(code)
        except LLMError as exc:
            await self._fail_step(run_id, "test", "tester", exc)
            raise _StageAborted from exc

        await self._persist_stage_step(
            run_id,
            "test",
            "tester",
            output={
                "test_files": len(out.test_suite.test_files),
            },
            out=out,
        )
        await self._persist_artifact(
            run_id, ArtifactKind.TEST_SUITE, out.test_suite.model_dump(mode="json")
        )
        await self._publish(
            EventType.STEP_COMPLETED, run_id, self._step_payload("test", out)
        )

    # ------------------------------------------------------------- prerequisites

    async def _load_prd(self, run_id: str, *, stage: str) -> PRD:
        art = await self._repo.latest_artifact(run_id, ArtifactKind.PRD)
        if art is None:
            await self._fail_missing_input(run_id, stage, "PRD")
            raise _StageAborted
        return PRD.model_validate(art.content)

    async def _load_design(self, run_id: str) -> SystemDesign:
        art = await self._repo.latest_artifact(run_id, ArtifactKind.SYSTEM_DESIGN)
        if art is None:
            await self._fail_missing_input(run_id, "build", "system design")
            raise _StageAborted
        return SystemDesign.model_validate(art.content)

    async def _load_sprint_plan(self, run_id: str) -> SprintPlan:
        art = await self._repo.latest_artifact(run_id, ArtifactKind.SPRINT_PLAN)
        if art is None:
            await self._fail_missing_input(run_id, "build", "sprint plan")
            raise _StageAborted
        return SprintPlan.model_validate(art.content)

    async def _load_code(self, run_id: str) -> CodeBundle:
        art = await self._repo.latest_artifact(run_id, ArtifactKind.CODE)
        if art is None:
            await self._fail_missing_input(run_id, "test", "code bundle")
            raise _StageAborted
        return CodeBundle.model_validate(art.content)

    # ------------------------------------------------------------- helpers

    def _should_revise(self, critique: Critique, iteration: int) -> bool:
        if iteration >= self._config.max_revisions:
            return False
        # Trust the critic's explicit decision; the threshold is a safety net.
        return (
            critique.should_revise
            or critique.score < self._config.revision_score_threshold
        )

    async def _persist_step(
        self,
        run_id: str,
        node: str,
        agent_name: str,
        out: PlannerOutput,
        extra_input: dict[str, object] | None = None,
    ) -> None:
        output: dict[str, object] = {}
        if out.prd is not None:
            output["prd_title"] = out.prd.title
            output["user_stories"] = len(out.prd.user_stories)
        if out.critique is not None:
            output["score"] = out.critique.score
            output["should_revise"] = out.critique.should_revise
        await self._repo.append_step(
            run_id,
            node=node,
            agent=agent_name,
            input=extra_input or {},
            output=output,
            latency_ms=out.latency_ms,
            tokens_in=out.usage.prompt,
            tokens_out=out.usage.completion,
        )

    async def _persist_stage_step(
        self,
        run_id: str,
        node: str,
        agent_name: str,
        *,
        output: dict[str, object],
        out: Any,
    ) -> None:
        await self._repo.append_step(
            run_id,
            node=node,
            agent=agent_name,
            input={},
            output=output,
            latency_ms=out.latency_ms,
            tokens_in=out.usage.prompt,
            tokens_out=out.usage.completion,
        )

    async def _persist_artifact(
        self, run_id: str, kind: ArtifactKind, content: dict[str, object]
    ) -> None:
        art = await self._repo.save_artifact(run_id, kind=kind, content=content)
        await self._publish(
            EventType.ARTIFACT_CREATED,
            run_id,
            {"kind": kind.value, "version": art.version, "artifact_id": art.id},
        )

    async def _fail_step(
        self, run_id: str, node: str, agent_name: str, exc: Exception
    ) -> None:
        message = f"{exc.__class__.__name__}: {exc}"
        logger.error(
            "orchestrator_step_failed", run_id=run_id, node=node, error=message
        )
        await self._repo.append_step(
            run_id, node=node, agent=agent_name, error=message
        )
        await self._publish(
            EventType.STEP_FAILED, run_id, {"node": node, "error": message}
        )
        await self._fail(run_id, message)

    async def _fail_missing_input(
        self, run_id: str, stage: str, missing: str
    ) -> None:
        message = f"Cannot run '{stage}' stage: no {missing} artifact found."
        logger.error("orchestrator_missing_input", run_id=run_id, stage=stage)
        await self._repo.append_step(
            run_id, node=stage, agent=_STAGE_AGENT.get(stage), error=message
        )
        await self._publish(
            EventType.STEP_FAILED, run_id, {"node": stage, "error": message}
        )
        await self._fail(run_id, message)

    async def _fail(self, run_id: str, message: str) -> None:
        await self._repo.set_status(run_id, RunStatus.FAILED, error=message)
        await self._publish(EventType.RUN_FAILED, run_id, {"error": message})

    @staticmethod
    def _step_payload(node: str, out: Any) -> dict[str, object]:
        return {
            "node": node,
            "latency_ms": out.latency_ms,
            "tokens_in": out.usage.prompt,
            "tokens_out": out.usage.completion,
            "model": out.model,
        }

    async def _publish(
        self, event_type: EventType, run_id: str, payload: dict[str, object]
    ) -> None:
        # Ensure payload is JSON-safe before it leaves the orchestrator.
        json.dumps(payload, default=str)
        await self._bus.publish(
            Event(type=event_type, run_id=run_id, payload=payload)
        )
