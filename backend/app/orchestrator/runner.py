"""Orchestrator — drives the SDLC pipeline for a single Run.

Pipeline (default):

    clarify → [approval] → plan → [approval] → design → [approval]
    → sprint_plan → [approval] → build → test → done

The **clarify** stage runs the RequirementAnalyzerAgent and pauses for the
user to answer questions. Answers are forwarded to the planner as context.

The **plan** stage runs the planner's own loop:
    draft → semantic_validate → critique → [revise → critique]*  → (PRD)

Approval gates pause the run at `AWAITING_HUMAN` between stages (unless the
run was created with `auto_approve`). A paused run is resumable.

Backward-compatibility: constructing the orchestrator with a single
`agent_factory` (and no designer/coder) yields a **planner-only** pipeline that
runs straight to completion with no approval gate.
"""
from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.agents.coder import CoderAgent
from app.agents.designer import DesignerAgent
from app.agents.planner import PlannerAgent, PlannerOutput
from app.agents.planner_reviewer import PlannerReviewerAgent
from app.agents.architecture_reviewer import ArchitectureReviewerAgent
from app.agents.security_reviewer import SecurityReviewerAgent
from app.agents.requirement_analyzer import RequirementAnalyzerAgent
from app.agents.semantic_validator import SemanticValidatorAgent
from app.agents.sprint_planner import SprintPlannerAgent
from app.agents.tester import TesterAgent
from app.core.logging import get_logger
from app.llm.errors import LLMError
from app.models import ArtifactKind, Run, RunStatus
from app.orchestrator.events import Event, EventBus, EventType, get_event_bus
from app.orchestrator.repository import RunRepository
from app.schemas import PRD, Critique, SystemDesign, SprintPlan
from app.schemas.clarifying_questions import ClarifyingQuestions
from app.schemas.code import CodeBundle

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class WorkflowConfig:
    """Tunables for the planning stage."""
    max_revisions: int = 1
    revision_score_threshold: int = 80


@dataclass(frozen=True, slots=True)
class StageSpec:
    """One stage in the pipeline plus whether it requires human approval."""
    name: str
    requires_approval: bool


_STAGE_AGENT = {
    "clarify": "requirement_analyzer",
    "plan": "planner",
    "semantic_validate": "semantic_validator",
    "design": "designer",
    "sprint_plan": "sprint_planner",
    "build": "coder",
    "test": "tester",
}

#: Stages whose output can be regenerated from human feedback via the
#: "revise" decision. Clarify is answered (not revised); build/test never gate.
REVISABLE_STAGES = frozenset({"plan", "design", "sprint_plan"})


class _StageAborted(Exception):
    """Internal signal: a stage failed and already recorded its failure."""


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
        self._requirement_analyzer = kwargs.get("requirement_analyzer")
        self._planner_reviewer = kwargs.get("planner_reviewer")
        self._architecture_reviewer = kwargs.get("architecture_reviewer")
        self._security_reviewer = kwargs.get("security_reviewer")
        self._semantic_validator = kwargs.get("semantic_validator")
        self._config = config or WorkflowConfig()

        plan_only = (
            agent_factory is not None and designer is None and coder is None
            and not self._sprint_planner and not self._tester
        )
        if plan_only:
            self._stages: list[StageSpec] = [StageSpec("plan", requires_approval=False)]
        else:
            self._stages = [
                StageSpec("clarify", requires_approval=True),
                StageSpec("plan", requires_approval=True),
                StageSpec("design", requires_approval=True),
                StageSpec("sprint_plan", requires_approval=True),
                StageSpec("build", requires_approval=False),
                StageSpec("test", requires_approval=False),
            ]

    # -------------------------------------------------------------- entrypoint

    async def run(self, run_id: str) -> None:
        """Execute (or resume) the pipeline for `run_id`. Never raises."""
        log = logger.bind(run_id=run_id)
        run = await self._repo.get_run(run_id)
        if run is None:
            log.error("orchestrator_run_not_found")
            return

        meta = dict(run.meta or {})
        auto_approve = bool(meta.get("auto_approve", False))
        start_index = int(meta.get("stage_index", 0))
        self._config = self._effective_config(meta)

        if meta.get("pending_revision"):
            await self._run_revision(run_id, run, meta)
            return

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
                return

            next_index = i + 1
            has_next = next_index < len(self._stages)
            if has_next and stage.requires_approval and not auto_approve:
                next_stage = self._stages[next_index].name
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
        if name == "clarify":
            await self._stage_clarify(run_id, prompt)
        elif name == "plan":
            await self._stage_plan(run_id, prompt)
        elif name == "design":
            await self._stage_design(run_id)
        elif name == "sprint_plan":
            await self._stage_sprint_plan(run_id)
        elif name == "build":
            await self._stage_build(run_id)
        elif name == "test":
            await self._stage_test(run_id)
        else:
            raise ValueError(f"Unknown stage '{name}'")

    # ---------------------------------------------------------- clarify stage

    async def _stage_clarify(self, run_id: str, prompt: str) -> None:
        agent = self._requirement_analyzer or RequirementAnalyzerAgent()
        await self._publish(EventType.STEP_STARTED, run_id, {"node": "clarify"})
        await self._progress(
            run_id, stage="clarify", node="clarify", agent=agent.name,
            message="Analyzing the brief and drafting clarifying questions…",
        )
        try:
            out = await agent.analyze(prompt)
        except LLMError as exc:
            await self._fail_step(run_id, "clarify", agent.name, exc)
            raise _StageAborted from exc

        await self._repo.append_step(
            run_id,
            node="clarify",
            agent=agent.name,
            input={"prompt": prompt},
            output={"questions": len(out.questions.questions)},
            latency_ms=out.latency_ms,
            tokens_in=out.usage.prompt,
            tokens_out=out.usage.completion,
        )
        await self._persist_artifact(
            run_id,
            ArtifactKind.CLARIFYING_QUESTIONS,
            out.questions.model_dump(mode="json"),
        )
        await self._publish(
            EventType.STEP_COMPLETED,
            run_id,
            {
                "node": "clarify",
                "latency_ms": out.latency_ms,
                "tokens_in": out.usage.prompt,
                "tokens_out": out.usage.completion,
                "model": out.model,
                "questions": len(out.questions.questions),
            },
        )

    # ------------------------------------------------------------- plan stage

    async def _stage_plan(self, run_id: str, prompt: str) -> None:
        # Pull clarification answers from meta if present
        run = await self._repo.get_run(run_id)
        meta = dict(run.meta or {}) if run else {}
        clarification_answers: dict[str, Any] = meta.get("clarification_answers", {})
        context: str | None = None
        if clarification_answers:
            lines = ["User answered the following clarifying questions:"]
            for q_id, answer in clarification_answers.items():
                lines.append(f"  {q_id}: {answer}")
            context = "\n".join(lines)

        try:
            agent = self._planner_factory()
        except Exception as exc:
            await self._fail(run_id, f"Failed to initialize planner: {exc}")
            raise _StageAborted from exc

        prd = await self._step_draft(run_id, agent, prompt, context=context)

        # Non-blocking semantic validation after draft
        await self._step_semantic_validate(run_id, prompt, "prd", prd.model_dump(mode="json"))

        # Non-blocking planner review after draft
        await self._step_review_prd(run_id, prd)

        for iteration in range(self._config.max_revisions + 1):
            critique = await self._step_critique(run_id, agent, prd, iteration)
            if not self._should_revise(critique, iteration):
                break
            prd = await self._step_revise(run_id, agent, prd, critique, iteration)

    async def _step_draft(self, run_id: str, agent: Any, prompt: str, *, context: str | None = None) -> PRD:
        await self._publish(EventType.STEP_STARTED, run_id, {"node": "draft"})
        await self._progress(
            run_id, stage="plan", node="draft", agent=agent.name,
            message="Drafting the PRD…",
        )
        try:
            out = await agent.draft(prompt, context=context)
        except LLMError as exc:
            await self._fail_step(run_id, "draft", agent.name, exc)
            raise _StageAborted from exc

        assert out.prd is not None
        await self._persist_step(run_id, "draft", agent.name, out, {"prompt": prompt})
        await self._persist_artifact(run_id, ArtifactKind.PRD, out.prd.model_dump(mode="json"))
        await self._publish(EventType.STEP_COMPLETED, run_id, self._step_payload("draft", out))
        return out.prd

    async def _step_review_prd(self, run_id: str, prd: PRD) -> None:
        """Non-blocking PRD review — never aborts the pipeline."""
        try:
            reviewer = self._planner_reviewer or PlannerReviewerAgent()
            await self._progress(
                run_id, stage="plan", node="review_prd", agent="planner_reviewer",
                message="Reviewing PRD quality…",
            )
            out = await reviewer.review(prd)
            await self._repo.append_step(
                run_id, node="review_prd", agent="planner_reviewer",
                input={}, output={"score": out.report.score, "passed": out.report.passed,
                                  "findings": len(out.report.findings)},
                latency_ms=out.latency_ms, tokens_in=out.usage.prompt,
                tokens_out=out.usage.completion,
            )
            await self._persist_artifact(
                run_id, ArtifactKind.REVIEW_REPORT,
                {**out.report.model_dump(mode="json"), "reviewer": "planner_reviewer"},
            )
        except Exception as exc:
            logger.warning("prd_review_failed", run_id=run_id, error=str(exc))

    async def _step_review_design(self, run_id: str, design: SystemDesign) -> None:
        """Non-blocking architecture + security review — never aborts the pipeline."""
        for injected, ReviewerCls, label, message in [
            (self._architecture_reviewer, ArchitectureReviewerAgent,
             "architecture_reviewer", "Reviewing the architecture…"),
            (self._security_reviewer, SecurityReviewerAgent,
             "security_reviewer", "Reviewing the security posture…"),
        ]:
            try:
                reviewer = injected or ReviewerCls()  # type: ignore[operator]
                await self._progress(
                    run_id, stage="design", node=f"review_{label}", agent=label,
                    message=message,
                )
                out = await reviewer.review(design)
                await self._repo.append_step(
                    run_id, node=f"review_{label}", agent=label,
                    input={}, output={"score": out.report.score, "passed": out.report.passed},
                    latency_ms=out.latency_ms, tokens_in=out.usage.prompt,
                    tokens_out=out.usage.completion,
                )
                await self._persist_artifact(
                    run_id, ArtifactKind.REVIEW_REPORT,
                    {**out.report.model_dump(mode="json"), "reviewer": label},
                )
            except Exception as exc:
                logger.warning("design_review_failed", run_id=run_id, reviewer=label, error=str(exc))

    async def _step_semantic_validate(
        self, run_id: str, prompt: str, artifact_kind: str, content: dict[str, Any]
    ) -> None:
        """Non-blocking semantic validation — never aborts the pipeline."""
        try:
            validator = self._semantic_validator or SemanticValidatorAgent()
            await self._progress(
                run_id,
                stage="plan" if artifact_kind == "prd" else "design",
                node="semantic_validate",
                agent="semantic_validator",
                message=f"Validating the {artifact_kind.replace('_', ' ')} against the original brief…",
            )
            out = await validator.validate(prompt, artifact_kind, content)
            await self._repo.append_step(
                run_id,
                node="semantic_validate",
                agent="semantic_validator",
                input={"artifact_kind": artifact_kind},
                output={
                    "passed": out.report.passed,
                    "score": out.report.score,
                    "issues": len(out.report.issues),
                },
                latency_ms=out.latency_ms,
                tokens_in=out.usage.prompt,
                tokens_out=out.usage.completion,
            )
            await self._persist_artifact(
                run_id,
                ArtifactKind.VALIDATION_REPORT,
                {**out.report.model_dump(mode="json"), "artifact_kind": artifact_kind},
            )
        except Exception as exc:
            logger.warning(
                "semantic_validation_failed",
                run_id=run_id,
                artifact_kind=artifact_kind,
                error=str(exc),
            )

    async def _step_critique(self, run_id: str, agent: Any, prd: PRD, iteration: int) -> Critique:
        await self._publish(
            EventType.STEP_STARTED, run_id, {"node": "critique", "iteration": iteration}
        )
        await self._progress(
            run_id, stage="plan", node="critique", agent=agent.name,
            message=f"Critiquing the PRD (pass {iteration + 1})…",
        )
        try:
            out = await agent.critique(prd)
        except LLMError as exc:
            await self._fail_step(run_id, "critique", agent.name, exc)
            raise _StageAborted from exc

        assert out.critique is not None
        await self._persist_step(run_id, "critique", agent.name, out, {"iteration": iteration})
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

    async def _step_revise(self, run_id: str, agent: Any, prd: PRD, critique: Critique, iteration: int) -> PRD:
        await self._publish(
            EventType.STEP_STARTED, run_id, {"node": "revise", "iteration": iteration}
        )
        await self._progress(
            run_id, stage="plan", node="revise", agent=agent.name,
            message="Revising the PRD from critique feedback…",
        )
        try:
            out = await agent.revise(prd, critique)
        except LLMError as exc:
            await self._fail_step(run_id, "revise", agent.name, exc)
            raise _StageAborted from exc

        assert out.prd is not None
        await self._persist_step(
            run_id, "revise", agent.name, out,
            {"iteration": iteration, "from_score": critique.score},
        )
        await self._persist_artifact(run_id, ArtifactKind.PRD, out.prd.model_dump(mode="json"))
        await self._publish(
            EventType.STEP_COMPLETED,
            run_id,
            {**self._step_payload("revise", out), "iteration": iteration},
        )
        return out.prd

    # ----------------------------------------------------------- design stage

    async def _stage_design(self, run_id: str) -> None:
        prd = await self._load_prd(run_id, stage="design")
        run = await self._repo.get_run(run_id)
        prompt = run.prompt if run else ""
        designer = self._designer if self._designer is not None else DesignerAgent()

        await self._publish(EventType.STEP_STARTED, run_id, {"node": "design"})
        await self._progress(
            run_id, stage="design", node="design", agent="designer",
            message="Designing the system architecture…",
        )
        try:
            out = await designer.design(prd)
        except LLMError as exc:
            await self._fail_step(run_id, "design", "designer", exc)
            raise _StageAborted from exc

        await self._persist_stage_step(
            run_id, "design", "designer",
            output={
                "title": out.design.title,
                "components": len(out.design.components),
                "data_models": len(out.design.data_models),
            },
            out=out,
        )
        design_content = out.design.model_dump(mode="json")
        await self._persist_artifact(run_id, ArtifactKind.SYSTEM_DESIGN, design_content)
        await self._publish(EventType.STEP_COMPLETED, run_id, self._step_payload("design", out))

        # Non-blocking semantic validation + architecture/security reviews of design
        await self._step_semantic_validate(run_id, prompt, "system_design", design_content)
        await self._step_review_design(run_id, out.design)

    # ------------------------------------------------------- sprint plan stage

    async def _stage_sprint_plan(self, run_id: str) -> None:
        prd = await self._load_prd(run_id, stage="sprint_plan")
        design = await self._load_design(run_id)
        sprint_planner = self._sprint_planner if self._sprint_planner is not None else SprintPlannerAgent()

        await self._publish(EventType.STEP_STARTED, run_id, {"node": "sprint_plan"})
        await self._progress(
            run_id, stage="sprint_plan", node="sprint_plan", agent="sprint_planner",
            message="Breaking the design into sprints and tasks…",
        )
        try:
            out = await sprint_planner.plan(prd, design)
        except LLMError as exc:
            await self._fail_step(run_id, "sprint_plan", "sprint_planner", exc)
            raise _StageAborted from exc

        await self._persist_stage_step(
            run_id, "sprint_plan", "sprint_planner",
            output={"sprints": len(out.plan.sprints)},
            out=out,
        )
        await self._persist_artifact(run_id, ArtifactKind.SPRINT_PLAN, out.plan.model_dump(mode="json"))
        await self._publish(EventType.STEP_COMPLETED, run_id, self._step_payload("sprint_plan", out))

    # ------------------------------------------------------------ build stage

    async def _stage_build(self, run_id: str) -> None:
        prd = await self._load_prd(run_id, stage="build")
        design = await self._load_design(run_id)
        sprint_plan = await self._load_sprint_plan(run_id)
        coder = self._coder if self._coder is not None else CoderAgent()

        await self._publish(EventType.STEP_STARTED, run_id, {"node": "build"})
        await self._progress(
            run_id, stage="build", node="build", agent="coder",
            message="Generating the application code…",
        )
        try:
            out = await coder.build(prd, design, sprint_plan)
        except LLMError as exc:
            await self._fail_step(run_id, "build", "coder", exc)
            raise _StageAborted from exc

        await self._persist_stage_step(
            run_id, "build", "coder",
            output={
                "project_name": out.code.project_name,
                "files": len(out.code.files),
                "tech_stack": out.code.tech_stack,
            },
            out=out,
        )
        await self._persist_artifact(run_id, ArtifactKind.CODE, out.code.model_dump(mode="json"))
        await self._publish(EventType.STEP_COMPLETED, run_id, self._step_payload("build", out))

    # ------------------------------------------------------------- test stage

    async def _stage_test(self, run_id: str) -> None:
        code = await self._load_code(run_id)
        tester = self._tester if self._tester is not None else TesterAgent()

        await self._publish(EventType.STEP_STARTED, run_id, {"node": "test"})
        await self._progress(
            run_id, stage="test", node="test", agent="tester",
            message="Writing the test suite…",
        )
        try:
            out = await tester.generate_tests(code)
        except LLMError as exc:
            await self._fail_step(run_id, "test", "tester", exc)
            raise _StageAborted from exc

        await self._persist_stage_step(
            run_id, "test", "tester",
            output={"test_files": len(out.test_suite.test_files)},
            out=out,
        )
        await self._persist_artifact(run_id, ArtifactKind.TEST_SUITE, out.test_suite.model_dump(mode="json"))
        await self._publish(EventType.STEP_COMPLETED, run_id, self._step_payload("test", out))

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

    # ------------------------------------------------------- feedback revision

    async def _run_revision(self, run_id: str, run: Run, meta: dict[str, Any]) -> None:
        """Re-run a single completed stage with human feedback, then re-pause.

        `stage_index` is never touched, so a later approve resumes the normal
        loop exactly where it left off. `pending_revision` is cleared only on
        success — a crash leaves it in place and `/retry` re-attempts it.
        """
        pending = dict(meta.get("pending_revision") or {})
        stage = str(pending.get("stage") or "")
        feedback = str(pending.get("feedback") or "").strip()
        log = logger.bind(run_id=run_id, stage=stage)

        if stage not in REVISABLE_STAGES or not feedback:
            await self._fail(run_id, f"Invalid revision request for stage '{stage}'.")
            return

        await self._repo.set_status(run_id, RunStatus.RUNNING)
        await self._publish(
            EventType.RUN_RESUMED, run_id, {"stage": stage, "mode": "revision"}
        )
        try:
            if stage == "plan":
                await self._revise_plan(run_id, feedback)
            elif stage == "design":
                await self._revise_design(run_id, run.prompt, feedback)
            else:
                await self._revise_sprint_plan(run_id, feedback)
        except _StageAborted:
            return

        history = list(meta.get("feedback_history") or [])
        history.append(
            {
                "stage": stage,
                "feedback": feedback,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )
        await self._repo.update_meta(
            run_id, {"pending_revision": None, "feedback_history": history}
        )
        await self._repo.set_status(run_id, RunStatus.AWAITING_HUMAN)
        await self._publish(
            EventType.RUN_AWAITING_APPROVAL,
            run_id,
            {
                "completed_stage": stage,
                "next_stage": meta.get("awaiting_stage"),
                "revision": True,
            },
        )
        log.info("orchestrator_revision_completed")

    async def _revise_plan(self, run_id: str, feedback: str) -> None:
        prd = await self._load_prd(run_id, stage="plan")
        try:
            agent = self._planner_factory()
        except Exception as exc:
            await self._fail(run_id, f"Failed to initialize planner: {exc}")
            raise _StageAborted from exc

        # Wrap the human feedback in a synthetic critique so the planner's
        # existing ID-preserving revision path does the work unchanged.
        critique = Critique(
            score=0,
            summary=feedback,
            issues=[feedback],
            suggestions=[],
            should_revise=True,
        )
        await self._publish(
            EventType.STEP_STARTED, run_id, {"node": "revise", "reason": "human_feedback"}
        )
        await self._progress(
            run_id, stage="plan", node="revise", agent=agent.name,
            message="Revising the PRD from reviewer feedback…",
        )
        try:
            out = await agent.revise(prd, critique)
        except LLMError as exc:
            await self._fail_step(run_id, "revise", agent.name, exc)
            raise _StageAborted from exc

        assert out.prd is not None
        await self._persist_step(run_id, "revise", agent.name, out, {"feedback": feedback})
        await self._persist_artifact(run_id, ArtifactKind.PRD, out.prd.model_dump(mode="json"))
        await self._publish(EventType.STEP_COMPLETED, run_id, self._step_payload("revise", out))

    async def _revise_design(self, run_id: str, prompt: str, feedback: str) -> None:
        prd = await self._load_prd(run_id, stage="design")
        previous = await self._load_design(run_id)
        designer = self._designer if self._designer is not None else DesignerAgent()

        await self._publish(
            EventType.STEP_STARTED,
            run_id,
            {"node": "revise_design", "reason": "human_feedback"},
        )
        await self._progress(
            run_id, stage="design", node="revise_design", agent="designer",
            message="Revising the system design from reviewer feedback…",
        )
        try:
            out = await designer.design(prd, previous=previous, feedback=feedback)
        except LLMError as exc:
            await self._fail_step(run_id, "revise_design", "designer", exc)
            raise _StageAborted from exc

        await self._persist_stage_step(
            run_id, "revise_design", "designer",
            output={
                "title": out.design.title,
                "components": len(out.design.components),
            },
            out=out,
            input_={"feedback": feedback},
        )
        design_content = out.design.model_dump(mode="json")
        await self._persist_artifact(run_id, ArtifactKind.SYSTEM_DESIGN, design_content)
        await self._publish(
            EventType.STEP_COMPLETED, run_id, self._step_payload("revise_design", out)
        )
        await self._step_semantic_validate(run_id, prompt, "system_design", design_content)
        await self._step_review_design(run_id, out.design)

    async def _revise_sprint_plan(self, run_id: str, feedback: str) -> None:
        prd = await self._load_prd(run_id, stage="sprint_plan")
        design = await self._load_design(run_id)
        previous = await self._load_sprint_plan(run_id)
        sprint_planner = (
            self._sprint_planner if self._sprint_planner is not None else SprintPlannerAgent()
        )

        await self._publish(
            EventType.STEP_STARTED,
            run_id,
            {"node": "revise_sprint_plan", "reason": "human_feedback"},
        )
        await self._progress(
            run_id, stage="sprint_plan", node="revise_sprint_plan", agent="sprint_planner",
            message="Revising the sprint plan from reviewer feedback…",
        )
        try:
            out = await sprint_planner.plan(prd, design, previous=previous, feedback=feedback)
        except LLMError as exc:
            await self._fail_step(run_id, "revise_sprint_plan", "sprint_planner", exc)
            raise _StageAborted from exc

        await self._persist_stage_step(
            run_id, "revise_sprint_plan", "sprint_planner",
            output={"sprints": len(out.plan.sprints)},
            out=out,
            input_={"feedback": feedback},
        )
        await self._persist_artifact(
            run_id, ArtifactKind.SPRINT_PLAN, out.plan.model_dump(mode="json")
        )
        await self._publish(
            EventType.STEP_COMPLETED, run_id, self._step_payload("revise_sprint_plan", out)
        )

    # ------------------------------------------------------------- helpers

    def _effective_config(self, meta: dict[str, Any]) -> WorkflowConfig:
        """Apply per-run overrides from Run.meta onto the constructed config."""
        raw = meta.get("max_revisions")
        if raw is None:
            return self._config
        try:
            max_revisions = max(0, int(raw))
        except (TypeError, ValueError):
            return self._config
        return dataclasses.replace(self._config, max_revisions=max_revisions)

    def _should_revise(self, critique: Critique, iteration: int) -> bool:
        if iteration >= self._config.max_revisions:
            return False
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
        input_: dict[str, object] | None = None,
    ) -> None:
        await self._repo.append_step(
            run_id,
            node=node,
            agent=agent_name,
            input=input_ or {},
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

    async def _fail_step(self, run_id: str, node: str, agent_name: str, exc: Exception) -> None:
        message = f"{exc.__class__.__name__}: {exc}"
        logger.error("orchestrator_step_failed", run_id=run_id, node=node, error=message)
        await self._repo.append_step(run_id, node=node, agent=agent_name, error=message)
        await self._publish(EventType.STEP_FAILED, run_id, {"node": node, "error": message})
        await self._fail(run_id, message)

    async def _fail_missing_input(self, run_id: str, stage: str, missing: str) -> None:
        message = f"Cannot run '{stage}' stage: no {missing} artifact found."
        logger.error("orchestrator_missing_input", run_id=run_id, stage=stage)
        await self._repo.append_step(
            run_id, node=stage, agent=_STAGE_AGENT.get(stage), error=message
        )
        await self._publish(EventType.STEP_FAILED, run_id, {"node": stage, "error": message})
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

    async def _progress(
        self,
        run_id: str,
        *,
        stage: str,
        node: str,
        message: str,
        agent: str | None = None,
    ) -> None:
        """Publish a human-readable live-activity event (never persisted)."""
        await self._publish(
            EventType.STEP_PROGRESS,
            run_id,
            {"stage": stage, "node": node, "message": message, "agent": agent},
        )

    async def _publish(
        self, event_type: EventType, run_id: str, payload: dict[str, object]
    ) -> None:
        json.dumps(payload, default=str)
        await self._bus.publish(Event(type=event_type, run_id=run_id, payload=payload))
