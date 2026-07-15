import pytest

from app.agents.sprint_planner import SprintPlannerAgent
from app.llm.types import TokenUsage
from app.schemas.sprint_plan import SprintPlan
from tests.fixtures import make_design, make_prd, make_sprint_plan


class StubSprintPlannerLLM:
    """Mock LLM for SprintPlannerAgent."""

    async def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        schema: type[SprintPlan] | None = None,
        temperature: float = 0.0,
    ):
        class Result:
            parsed = make_sprint_plan()
            usage = TokenUsage(prompt=10, completion=20, total=30)
            latency_ms = 100
            model = "stub"
            finish_reason = "STOP"
        return Result()


@pytest.mark.asyncio
async def test_sprint_planner_agent() -> None:
    prd = make_prd()
    design = make_design()
    agent = SprintPlannerAgent(llm=StubSprintPlannerLLM())  # type: ignore
    
    result = await agent.plan(prd, design)
    
    assert result.plan is not None
    assert len(result.plan.sprints) >= 1
    assert result.plan.sprints[0].id == "sprint-1"
    assert result.usage.total == 30
    assert result.model == "stub"
