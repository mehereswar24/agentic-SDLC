import pytest

from app.agents.tester import TesterAgent
from app.llm.types import TokenUsage
from app.schemas.test_suite import TestSuite
from tests.fixtures import make_code, make_test_suite


class StubTesterLLM:
    """Mock LLM for TesterAgent."""

    async def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        schema: type[TestSuite] | None = None,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
    ):
        class Result:
            parsed = make_test_suite()
            usage = TokenUsage(prompt=10, completion=20, total=30)
            latency_ms = 100
            model = "stub"
            finish_reason = "STOP"
        return Result()


@pytest.mark.asyncio
async def test_tester_agent() -> None:
    code = make_code()
    agent = TesterAgent(llm=StubTesterLLM())  # type: ignore
    
    result = await agent.generate_tests(code)
    
    assert result.test_suite is not None
    assert len(result.test_suite.test_files) >= 1
    assert result.test_suite.test_files[0].test_type == "unit"
    assert result.usage.total == 30
    assert result.model == "stub"
