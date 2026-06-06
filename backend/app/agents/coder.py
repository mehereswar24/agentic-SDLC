"""CoderAgent — turns a PRD + SystemDesign into a runnable CodeBundle.

Third stage of the SDLC pipeline (plan → design → build). Follows the same
BaseAgent + AgentRegistry pattern as PlannerAgent and DesignerAgent, so the
orchestrator can drive it identically.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.prompts.coder import CODE_SYSTEM_PROMPT
from app.llm.types import TokenUsage
from app.models import ArtifactKind
from app.schemas import PRD, SystemDesign
from app.schemas.code import CodeBundle


@dataclass(slots=True)
class CoderOutput:
    code: CodeBundle
    usage: TokenUsage
    latency_ms: int
    model: str
    finish_reason: str | None


@AgentRegistry.register
class CoderAgent(BaseAgent):
    name = "coder"
    produces = ArtifactKind.CODE

    BUILD_TEMPERATURE = 0.2

    async def build(self, prd: PRD, design: SystemDesign) -> CoderOutput:
        user_prompt = (
            "Implement a minimal, runnable v1 of this project.\n\n"
            "PRD (JSON):\n"
            f"{prd.model_dump_json(indent=2)}\n\n"
            "System design (JSON):\n"
            f"{design.model_dump_json(indent=2)}"
        )
        self.logger.info(
            "coder_start",
            prd_title=prd.title,
            components=len(design.components),
        )
        result = await self._llm.chat(
            user_prompt,
            system=CODE_SYSTEM_PROMPT,
            schema=CodeBundle,
            temperature=self.BUILD_TEMPERATURE,
        )
        assert result.parsed is not None
        self.logger.info(
            "coder_done",
            files=len(result.parsed.files),
            latency_ms=result.latency_ms,
        )
        return CoderOutput(
            code=result.parsed,
            usage=result.usage,
            latency_ms=result.latency_ms,
            model=result.model,
            finish_reason=result.finish_reason,
        )
