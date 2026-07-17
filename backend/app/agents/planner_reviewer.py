"""PlannerReviewerAgent — reviews a PRD for completeness and quality."""
from __future__ import annotations

from dataclasses import dataclass

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.prompts.planner_reviewer import PLANNER_REVIEWER_SYSTEM_PROMPT
from app.llm.client import get_llm_client
from app.llm.types import LLMClient, TokenUsage
from app.models import ArtifactKind
from app.schemas import PRD
from app.schemas.review import ReviewReport


@dataclass(slots=True)
class ReviewerOutput:
    report: ReviewReport
    usage: TokenUsage
    latency_ms: int
    model: str
    finish_reason: str | None


@AgentRegistry.register
class PlannerReviewerAgent(BaseAgent):
    name = "planner_reviewer"
    produces = ArtifactKind.REVIEW_REPORT
    TEMPERATURE = 0.1

    def __init__(self, llm: LLMClient | None = None) -> None:
        super().__init__(llm=llm if llm is not None else get_llm_client())

    async def review(self, prd: PRD) -> ReviewerOutput:
        user = (
            "Review this PRD and produce a ReviewReport.\n\n"
            f"PRD (JSON):\n{prd.model_dump_json(indent=2)}"
        )
        self.logger.info("planner_reviewer_start", prd_title=prd.title)
        result = await self._llm.chat(
            user, system=PLANNER_REVIEWER_SYSTEM_PROMPT,
            schema=ReviewReport, temperature=self.TEMPERATURE,
        )
        assert result.parsed is not None
        self.logger.info(
            "planner_reviewer_done",
            score=result.parsed.score,
            passed=result.parsed.passed,
            findings=len(result.parsed.findings),
        )
        return ReviewerOutput(
            report=result.parsed, usage=result.usage,
            latency_ms=result.latency_ms, model=result.model,
            finish_reason=result.finish_reason,
        )
