"""SecurityReviewerAgent — reviews a SystemDesign for security vulnerabilities."""
from __future__ import annotations

from dataclasses import dataclass

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.prompts.security_reviewer import SECURITY_REVIEWER_SYSTEM_PROMPT
from app.llm.client import get_llm_client
from app.llm.types import LLMClient, TokenUsage
from app.models import ArtifactKind
from app.schemas import SystemDesign
from app.schemas.review import ReviewReport


@dataclass(slots=True)
class SecurityReviewerOutput:
    report: ReviewReport
    usage: TokenUsage
    latency_ms: int
    model: str
    finish_reason: str | None


@AgentRegistry.register
class SecurityReviewerAgent(BaseAgent):
    name = "security_reviewer"
    produces = ArtifactKind.REVIEW_REPORT
    TEMPERATURE = 0.1

    def __init__(self, llm: LLMClient | None = None) -> None:
        super().__init__(llm=llm if llm is not None else get_llm_client())

    async def review(self, design: SystemDesign) -> SecurityReviewerOutput:
        user = (
            "Review this system design for security issues and produce a ReviewReport.\n\n"
            f"System Design (JSON):\n{design.model_dump_json(indent=2)}"
        )
        self.logger.info("security_reviewer_start", title=design.title)
        result = await self._llm.chat(
            user, system=SECURITY_REVIEWER_SYSTEM_PROMPT,
            schema=ReviewReport, temperature=self.TEMPERATURE,
        )
        assert result.parsed is not None
        self.logger.info(
            "security_reviewer_done",
            score=result.parsed.score,
            passed=result.parsed.passed,
            critical_findings=sum(
                1 for f in result.parsed.findings if f.severity == "critical"
            ),
        )
        return SecurityReviewerOutput(
            report=result.parsed, usage=result.usage,
            latency_ms=result.latency_ms, model=result.model,
            finish_reason=result.finish_reason,
        )
