from __future__ import annotations

from typing import ClassVar

import pytest

from app.agents.base import AgentRegistry, BaseAgent
from app.core.config import get_settings


class _DummyAgent(BaseAgent):
    name: ClassVar[str] = "dummy_test"


def test_register_and_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    get_settings.cache_clear()
    AgentRegistry.register(_DummyAgent)
    assert "dummy_test" in AgentRegistry.names()
    assert AgentRegistry.get("dummy_test") is _DummyAgent


def test_unknown_agent_raises() -> None:
    with pytest.raises(KeyError, match="Unknown agent"):
        AgentRegistry.get("does_not_exist_xyz")


def test_empty_name_rejected() -> None:
    class Bad(BaseAgent):
        name: ClassVar[str] = ""

    with pytest.raises(ValueError, match="empty `name`"):
        AgentRegistry.register(Bad)


def test_collision_rejected() -> None:
    class A(BaseAgent):
        name: ClassVar[str] = "collide_test"

    class B(BaseAgent):
        name: ClassVar[str] = "collide_test"

    AgentRegistry.register(A)
    with pytest.raises(ValueError, match="collision"):
        AgentRegistry.register(B)


def test_planner_is_auto_registered() -> None:
    # Importing the planner module triggers its @AgentRegistry.register decorator.
    from app.agents.planner import PlannerAgent  # noqa: F401

    assert "planner" in AgentRegistry.names()
