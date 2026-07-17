"""DesignerAgent — turns a finalized PRD into a SystemDesign artifact.

This agent exists to prove the orchestrator's extensibility model: adding a
new SDLC stage requires only (1) a new Pydantic output schema, (2) a new
prompt, (3) a `BaseAgent` subclass registered via `@AgentRegistry.register`.
No changes to `BaseAgent`, `AgentRegistry`, or the orchestrator runner are
needed for the agent itself to exist.

The Phase 7 wiring of this into the run flow is a small next step — covered
by an integration test rather than the live `/api/runs` endpoint, which
remains PRD-only until a follow-up phase exposes design generation.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.prompts.designer import DESIGN_SYSTEM_PROMPT
from app.llm.client import get_designer_llm_client
from app.llm.types import LLMClient, TokenUsage
from app.models import ArtifactKind
from app.schemas import PRD, SystemDesign


@dataclass(slots=True)
class DesignerOutput:
    design: SystemDesign
    usage: TokenUsage
    latency_ms: int
    model: str
    finish_reason: str | None


@AgentRegistry.register
class DesignerAgent(BaseAgent):
    name = "designer"
    produces = ArtifactKind.SYSTEM_DESIGN

    DESIGN_TEMPERATURE = 0.3

    def __init__(self, llm: LLMClient | None = None) -> None:
        super().__init__(llm=llm if llm is not None else get_designer_llm_client())

    async def design(
        self,
        prd: PRD,
        *,
        previous: SystemDesign | None = None,
        feedback: str | None = None,
    ) -> DesignerOutput:
        user_prompt = (
            "Produce a lightweight architecture sketch for this PRD.\n\n"
            "PRD (JSON):\n"
            f"{prd.model_dump_json(indent=2)}"
        )
        if previous is not None and feedback:
            user_prompt += (
                "\n\nPrevious design (JSON):\n"
                f"{previous.model_dump_json(indent=2)}\n\n"
                f"A human reviewer rejected this design with the feedback below. "
                f"Produce a corrected design that addresses the feedback while "
                f"preserving every unaffected part of the previous design.\n"
                f"Reviewer feedback:\n{feedback}"
            )
        self.logger.info("designer_start", prd_title=prd.title, is_revision=bool(feedback))
        result = await self._llm.chat(
            user_prompt,
            system=DESIGN_SYSTEM_PROMPT,
            schema=SystemDesign,
            temperature=self.DESIGN_TEMPERATURE,
        )
        assert result.parsed is not None
        self.logger.info(
            "designer_done",
            components=len(result.parsed.components),
            data_models=len(result.parsed.data_models),
            latency_ms=result.latency_ms,
        )
        return DesignerOutput(
            design=result.parsed,
            usage=result.usage,
            latency_ms=result.latency_ms,
            model=result.model,
            finish_reason=result.finish_reason,
        )
