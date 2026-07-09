"""CoderAgent — turns a PRD + SystemDesign into a runnable CodeBundle.

Third stage of the SDLC pipeline (plan → design → build). Follows the same
BaseAgent + AgentRegistry pattern as PlannerAgent and DesignerAgent, so the
orchestrator can drive it identically.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.prompts.coder import CODE_SYSTEM_PROMPT
from app.llm.client import get_coder_llm_client
from app.llm.types import LLMClient, TokenUsage
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
    # A polished single-page UI is large; give the model plenty of output budget
    # so the index.html isn't truncated mid-string (which fails JSON parsing).
    BUILD_MAX_OUTPUT_TOKENS = 32768

    def __init__(self, llm: LLMClient | None = None) -> None:
        # Default to the coder-stage client (local Ollama in the hybrid setup);
        # an explicit client (e.g. a test stub) still wins.
        super().__init__(llm=llm if llm is not None else get_coder_llm_client())

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
            max_output_tokens=self.BUILD_MAX_OUTPUT_TOKENS,
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
