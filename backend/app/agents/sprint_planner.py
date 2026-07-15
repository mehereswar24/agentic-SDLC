"""SprintPlannerAgent — turns PRD and SystemDesign into a SprintPlan."""
from __future__ import annotations

from dataclasses import dataclass

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.prompts.sprint_planner import SPRINT_PLANNER_SYSTEM_PROMPT
from app.llm.client import get_sprint_planner_llm_client
from app.llm.types import LLMClient, TokenUsage
from app.models import ArtifactKind
from app.schemas import PRD, SystemDesign, SprintPlan


@dataclass(slots=True)
class SprintPlannerOutput:
    plan: SprintPlan
    usage: TokenUsage
    latency_ms: int
    model: str
    finish_reason: str | None


def _format_prompt(prd: PRD, design: SystemDesign) -> str:
    return (
        "Product Requirements Document (JSON):\n"
        f"{prd.model_dump_json(indent=2)}\n\n"
        "System Design (JSON):\n"
        f"{design.model_dump_json(indent=2)}\n\n"
        "Based on these, generate a sprint plan."
    )


@AgentRegistry.register
class SprintPlannerAgent(BaseAgent):
    name = "sprint_planner"
    produces = ArtifactKind.SPRINT_PLAN
    TEMPERATURE = 0.2

    def __init__(self, llm: LLMClient | None = None) -> None:
        super().__init__(llm=llm if llm is not None else get_sprint_planner_llm_client())

    async def plan(self, prd: PRD, design: SystemDesign) -> SprintPlannerOutput:
        user = _format_prompt(prd, design)
        self.logger.info("sprint_planner_start", user_stories=len(prd.user_stories))
        result = await self._llm.chat(
            user,
            system=SPRINT_PLANNER_SYSTEM_PROMPT,
            schema=SprintPlan,
            temperature=self.TEMPERATURE,
        )
        assert result.parsed is not None
        self.logger.info(
            "sprint_planner_done",
            sprints=len(result.parsed.sprints),
            latency_ms=result.latency_ms,
        )
        return SprintPlannerOutput(
            plan=result.parsed,
            usage=result.usage,
            latency_ms=result.latency_ms,
            model=result.model,
            finish_reason=result.finish_reason,
        )
