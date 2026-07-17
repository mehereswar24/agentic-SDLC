"""ArchitectureReviewerAgent — reviews a SystemDesign for completeness and scalability."""
from __future__ import annotations

from dataclasses import dataclass

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.prompts.architecture_reviewer import ARCHITECTURE_REVIEWER_SYSTEM_PROMPT
from app.llm.client import get_llm_client
from app.llm.types import LLMClient, TokenUsage
from app.models import ArtifactKind
from app.schemas import SystemDesign
from app.schemas.review import ReviewReport


@dataclass(slots=True)
class ArchitectureReviewerOutput:
    report: ReviewReport
    usage: TokenUsage
    latency_ms: int
    model: str
    finish_reason: str | None


@AgentRegistry.register
class ArchitectureReviewerAgent(BaseAgent):
    name = "architecture_reviewer"
    produces = ArtifactKind.REVIEW_REPORT
    TEMPERATURE = 0.1

    def __init__(self, llm: LLMClient | None = None) -> None:
        super().__init__(llm=llm if llm is not None else get_llm_client())

    async def review(self, design: SystemDesign) -> ArchitectureReviewerOutput:
        user = (
            "Review this system design and produce a ReviewReport.\n\n"
            f"System Design (JSON):\n{design.model_dump_json(indent=2)}"
        )
        self.logger.info("architecture_reviewer_start", title=design.title)
        result = await self._llm.chat(
            user, system=ARCHITECTURE_REVIEWER_SYSTEM_PROMPT,
            schema=ReviewReport, temperature=self.TEMPERATURE,
        )
        assert result.parsed is not None
        self.logger.info(
            "architecture_reviewer_done",
            score=result.parsed.score,
            passed=result.parsed.passed,
        )
        return ArchitectureReviewerOutput(
            report=result.parsed, usage=result.usage,
            latency_ms=result.latency_ms, model=result.model,
            finish_reason=result.finish_reason,
        )
