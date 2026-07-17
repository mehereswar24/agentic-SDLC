"""RequirementAnalyzerAgent — turns a product brief into clarifying questions.

The agent is the first stage of the full pipeline. It analyses the user's
prompt and produces a structured list of questions that a human reviewer
answers before the planner runs. The answers are then forwarded to the
PlannerAgent as additional context.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.prompts.requirement_analyzer import REQUIREMENT_ANALYZER_SYSTEM_PROMPT
from app.llm.client import get_stage_llm_client
from app.llm.types import LLMClient, TokenUsage
from app.models import ArtifactKind
from app.schemas.clarifying_questions import ClarifyingQuestions


@dataclass(slots=True)
class RequirementAnalyzerOutput:
    """Return type for RequirementAnalyzerAgent.analyze().

    Mirrors the Output pattern used by every other SDLC agent so the
    orchestrator can persist a consistent AgentStep row.
    """

    questions: ClarifyingQuestions
    usage: TokenUsage
    latency_ms: int
    model: str
    finish_reason: str | None


def _format_prompt(prompt: str) -> str:
    return (
        "Product Brief:\n"
        f"{prompt}\n\n"
        "Analyse the brief and produce clarifying questions as instructed."
    )


@AgentRegistry.register
class RequirementAnalyzerAgent(BaseAgent):
    name = "requirement_analyzer"
    produces = ArtifactKind.CLARIFYING_QUESTIONS

    TEMPERATURE = 0.3

    def __init__(self, llm: LLMClient | None = None) -> None:
        super().__init__(
            llm=llm if llm is not None else get_stage_llm_client("requirement_analyzer")
        )

    async def analyze(self, prompt: str) -> RequirementAnalyzerOutput:
        """Analyse `prompt` and return a structured list of clarifying questions."""
        user = _format_prompt(prompt)
        self.logger.info("requirement_analyzer_start", prompt_chars=len(prompt))

        result = await self._llm.chat(
            user,
            system=REQUIREMENT_ANALYZER_SYSTEM_PROMPT,
            schema=ClarifyingQuestions,
            temperature=self.TEMPERATURE,
        )
        assert result.parsed is not None, "schema=ClarifyingQuestions guarantees parsed is set"

        self.logger.info(
            "requirement_analyzer_done",
            questions=len(result.parsed.questions),
            latency_ms=result.latency_ms,
        )
        return RequirementAnalyzerOutput(
            questions=result.parsed,
            usage=result.usage,
            latency_ms=result.latency_ms,
            model=result.model,
            finish_reason=result.finish_reason,
        )


__all__ = ["RequirementAnalyzerAgent", "RequirementAnalyzerOutput"]
