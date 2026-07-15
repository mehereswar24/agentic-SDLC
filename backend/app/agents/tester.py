"""TesterAgent — turns CodeBundle into a TestSuite."""
from __future__ import annotations

from dataclasses import dataclass

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.prompts.tester import TESTER_SYSTEM_PROMPT
from app.llm.client import get_tester_llm_client
from app.llm.types import LLMClient, TokenUsage
from app.models import ArtifactKind
from app.schemas import TestSuite
from app.schemas.code import CodeBundle


@dataclass(slots=True)
class TesterOutput:
    test_suite: TestSuite
    usage: TokenUsage
    latency_ms: int
    model: str
    finish_reason: str | None


def _format_prompt(code: CodeBundle) -> str:
    return (
        "Code Bundle (JSON):\n"
        f"{code.model_dump_json(indent=2)}\n\n"
        "Generate a comprehensive test suite for this code."
    )


@AgentRegistry.register
class TesterAgent(BaseAgent):
    name = "tester"
    produces = ArtifactKind.TEST_SUITE
    TEMPERATURE = 0.2

    MAX_OUTPUT_TOKENS = 32768

    def __init__(self, llm: LLMClient | None = None) -> None:
        super().__init__(llm=llm if llm is not None else get_tester_llm_client())

    async def generate_tests(self, code: CodeBundle) -> TesterOutput:
        user = _format_prompt(code)
        self.logger.info("tester_start", code_files=len(code.files))
        
        result = await self._llm.chat(
            user,
            system=TESTER_SYSTEM_PROMPT,
            schema=TestSuite,
            temperature=self.TEMPERATURE,
            max_output_tokens=self.MAX_OUTPUT_TOKENS,
        )
        assert result.parsed is not None
        self.logger.info(
            "tester_done",
            test_files=len(result.parsed.test_files),
            latency_ms=result.latency_ms,
        )
        return TesterOutput(
            test_suite=result.parsed,
            usage=result.usage,
            latency_ms=result.latency_ms,
            model=result.model,
            finish_reason=result.finish_reason,
        )
