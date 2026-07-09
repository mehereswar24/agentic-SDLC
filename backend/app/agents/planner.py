"""PlannerAgent — turns a user prompt into a validated PRD, with self-critique.

Three operations:
  • `draft(prompt, context)` — produce an initial PRD.
  • `critique(prd)` — score the PRD and decide whether to revise.
  • `revise(prd, critique)` — apply suggested fixes, preserving stable IDs.

The orchestrator (Phase 4) wires these into a `draft → critique → revise?`
loop with a configurable budget. The agent itself is stateless across calls
so it's safe to share across concurrent runs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.prompts.planner import (
    CRITIQUE_SYSTEM_PROMPT,
    DRAFT_SYSTEM_PROMPT,
    REVISION_SYSTEM_PROMPT,
)
from app.llm.client import get_planner_llm_client
from app.llm.types import LLMClient, TokenUsage
from app.models import ArtifactKind
from app.schemas import PRD, Critique


@dataclass(slots=True)
class PlannerOutput:
    """Telemetry-rich return type for a single planner operation.

    Carries the model output plus everything the orchestrator needs to
    persist an AgentStep row (latency, tokens, finish reason).
    """

    prd: PRD | None
    critique: Critique | None
    usage: TokenUsage
    latency_ms: int
    model: str
    finish_reason: str | None


def _format_user_prompt(prompt: str, context: str | None) -> str:
    if context:
        return (
            "User request:\n"
            f"{prompt}\n\n"
            "Additional context (research notes, prior conversation, etc.):\n"
            f"{context}"
        )
    return f"User request:\n{prompt}"


def _format_revision_prompt(prd: PRD, critique: Critique) -> str:
    return (
        "Existing PRD (JSON):\n"
        f"{prd.model_dump_json(indent=2)}\n\n"
        "Critique to address (JSON):\n"
        f"{critique.model_dump_json(indent=2)}\n\n"
        "Apply the suggestions. Preserve all unaffected content and stable IDs."
    )


def _format_critique_prompt(prd: PRD) -> str:
    return (
        "Review this PRD and produce a critique in the required schema.\n\n"
        "PRD JSON:\n"
        f"{prd.model_dump_json(indent=2)}"
    )


@AgentRegistry.register
class PlannerAgent(BaseAgent):
    name = "planner"
    produces = ArtifactKind.PRD

    DRAFT_TEMPERATURE = 0.4
    REVISION_TEMPERATURE = 0.2
    CRITIQUE_TEMPERATURE = 0.1

    def __init__(self, llm: LLMClient | None = None) -> None:
        super().__init__(llm=llm if llm is not None else get_planner_llm_client())

    async def draft(self, prompt: str, *, context: str | None = None) -> PlannerOutput:
        """Produce an initial PRD for `prompt`."""
        user = _format_user_prompt(prompt, context)
        self.logger.info(
            "planner_draft_start", prompt_chars=len(prompt), has_context=bool(context)
        )
        result = await self._llm.chat(
            user,
            system=DRAFT_SYSTEM_PROMPT,
            schema=PRD,
            temperature=self.DRAFT_TEMPERATURE,
        )
        assert result.parsed is not None, "schema=PRD guarantees parsed is set"
        self.logger.info(
            "planner_draft_done",
            user_stories=len(result.parsed.user_stories),
            open_questions=len(result.parsed.open_questions),
            latency_ms=result.latency_ms,
        )
        return PlannerOutput(
            prd=result.parsed,
            critique=None,
            usage=result.usage,
            latency_ms=result.latency_ms,
            model=result.model,
            finish_reason=result.finish_reason,
        )

    async def critique(self, prd: PRD) -> PlannerOutput:
        """Score `prd` and decide whether revision is needed."""
        user = _format_critique_prompt(prd)
        self.logger.info("planner_critique_start", user_stories=len(prd.user_stories))
        result = await self._llm.chat(
            user,
            system=CRITIQUE_SYSTEM_PROMPT,
            schema=Critique,
            temperature=self.CRITIQUE_TEMPERATURE,
        )
        assert result.parsed is not None
        self.logger.info(
            "planner_critique_done",
            score=result.parsed.score,
            should_revise=result.parsed.should_revise,
            issues=len(result.parsed.issues),
            latency_ms=result.latency_ms,
        )
        return PlannerOutput(
            prd=None,
            critique=result.parsed,
            usage=result.usage,
            latency_ms=result.latency_ms,
            model=result.model,
            finish_reason=result.finish_reason,
        )

    async def revise(self, prd: PRD, critique: Critique) -> PlannerOutput:
        """Apply `critique` suggestions to `prd`, returning the revised PRD."""
        user = _format_revision_prompt(prd, critique)
        self.logger.info(
            "planner_revise_start",
            score=critique.score,
            issues=len(critique.issues),
        )
        result = await self._llm.chat(
            user,
            system=REVISION_SYSTEM_PROMPT,
            schema=PRD,
            temperature=self.REVISION_TEMPERATURE,
        )
        assert result.parsed is not None
        self.logger.info(
            "planner_revise_done",
            user_stories=len(result.parsed.user_stories),
            latency_ms=result.latency_ms,
        )
        return PlannerOutput(
            prd=result.parsed,
            critique=None,
            usage=result.usage,
            latency_ms=result.latency_ms,
            model=result.model,
            finish_reason=result.finish_reason,
        )


def render_prd_markdown(prd: PRD) -> str:
    """Render a PRD as human-readable Markdown.

    Used by the future frontend `PrdViewer` and as a download format. Lives
    here (not in a template) because the structure is small and the schema
    is the single source of truth — changes here track schema changes.
    """
    lines: list[str] = [f"# {prd.title}", "", prd.summary, ""]

    def section(title: str) -> None:
        lines.extend(["", f"## {title}", ""])

    def bullets(items: list[str]) -> None:
        for item in items:
            lines.append(f"- {item}")

    section("Problem Statement")
    lines.append(prd.problem_statement)

    section("Goals")
    bullets(prd.goals)

    section("Non-Goals")
    bullets(prd.non_goals)

    section("Target Users")
    for p in prd.target_users:
        lines.append(f"### {p.name}")
        lines.append(p.description)
        lines.append("**Key needs:**")
        bullets(p.key_needs)
        lines.append("")

    section("User Stories")
    for s in prd.user_stories:
        lines.append(f"### {s.id} ({s.priority.value})")
        lines.append(f"As a **{s.as_a}**, I want **{s.i_want}** so that **{s.so_that}**.")
        lines.append("")
        lines.append("**Acceptance criteria:**")
        for ac in s.acceptance_criteria:
            lines.append(f"- Given {ac.given}, when {ac.when}, then {ac.then}.")
        lines.append("")

    section("Functional Requirements")
    for fr in prd.functional_requirements:
        rationale = f" — _{fr.rationale}_" if fr.rationale else ""
        lines.append(f"- **{fr.id}**: {fr.statement}{rationale}")

    section("Non-Functional Requirements")
    for nfr in prd.non_functional_requirements:
        lines.append(f"- **{nfr.id}** ({nfr.category}): {nfr.statement}")

    if prd.constraints:
        section("Constraints")
        bullets(prd.constraints)
    if prd.assumptions:
        section("Assumptions")
        bullets(prd.assumptions)
    if prd.risks:
        section("Risks")
        for r in prd.risks:
            lines.append(
                f"- _{r.severity.value} / {r.likelihood.value}_ — {r.description}"
            )
            lines.append(f"  - **Mitigation:** {r.mitigation}")
    if prd.open_questions:
        section("Open Questions")
        bullets(prd.open_questions)

    section("Success Metrics")
    for m in prd.success_metrics:
        instr = f" _(measured via {m.instrumentation})_" if m.instrumentation else ""
        lines.append(f"- **{m.name}** → {m.target}{instr}")

    return "\n".join(lines).rstrip() + "\n"


__all__ = ["PlannerAgent", "PlannerOutput", "render_prd_markdown"]


# Re-export json for tests that want to round-trip schemas easily without
# pulling pydantic into their import block.
_ = json
