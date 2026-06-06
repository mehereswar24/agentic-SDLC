"""Extensibility proof: the DesignerAgent registers correctly and runs end-to-end
against a stubbed LLM. If this passes without changes to `BaseAgent`,
`AgentRegistry`, or the orchestrator core, the extensibility seam works.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.agents.base import AgentRegistry
from app.agents.designer import DesignerAgent
from app.core.config import get_settings
from app.llm.types import LLMResult, TokenUsage
from app.schemas import Component, DataModel, SystemDesign
from tests.fixtures import make_prd


class _StubLLM:
    model = "stub-model"

    def __init__(self, design: SystemDesign) -> None:
        self._design = design
        self.last_kwargs: dict[str, Any] | None = None

    async def chat(self, prompt: str, **kwargs: Any) -> LLMResult[SystemDesign]:
        self.last_kwargs = {"prompt": prompt, **kwargs}
        return LLMResult(
            text=self._design.model_dump_json(),
            parsed=self._design,
            usage=TokenUsage(prompt=120, completion=400, total=520),
            latency_ms=300,
            model=self.model,
            finish_reason="STOP",
        )


def _sample_design() -> SystemDesign:
    return SystemDesign(
        title="Habit Tracker — v1 Architecture",
        overview=(
            "Mobile-first SPA backed by a stateless REST API. Habit completions "
            "land in Postgres; daily metrics roll up via a scheduled job."
        ),
        components=[
            Component(
                name="Mobile Client",
                responsibility="Render the habit list and log completions.",
                technology="React Native",
            ),
            Component(
                name="API Server",
                responsibility="Authenticate users and persist habit events.",
                technology="FastAPI",
            ),
        ],
        data_models=[
            DataModel(
                entity="Habit",
                purpose="User-defined recurring activity.",
                key_fields=["id", "user_id", "name", "frequency", "created_at"],
            ),
        ],
        integration_points=["Firebase Cloud Messaging for push notifications"],
        open_design_questions=[
            "Offline-first sync — last-write-wins or CRDT?",
        ],
    )


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "fake")
    get_settings.cache_clear()


def test_designer_auto_registers() -> None:
    """Importing app.agents.designer triggers the registry decorator."""
    assert "designer" in AgentRegistry.names()
    assert AgentRegistry.get("designer") is DesignerAgent


async def test_designer_produces_systemdesign() -> None:
    expected = _sample_design()
    llm = _StubLLM(expected)
    agent = DesignerAgent(llm=llm)  # type: ignore[arg-type]

    out = await agent.design(make_prd())

    assert out.design.title == expected.title
    assert len(out.design.components) == 2
    assert out.design.components[0].technology == "React Native"
    assert llm.last_kwargs is not None
    assert llm.last_kwargs["schema"] is SystemDesign
    assert "PRD (JSON)" in llm.last_kwargs["prompt"]
    assert out.usage.completion == 400
    assert out.latency_ms == 300


def test_planner_and_designer_coexist_in_registry() -> None:
    """Multiple agents share the registry without collisions."""
    # Importing forces both decorators to run, regardless of pytest collection order.
    import app.agents.planner  # noqa: F401
    import app.agents.designer  # noqa: F401

    names = AgentRegistry.names()
    assert "planner" in names
    assert "designer" in names
