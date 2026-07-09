"""BaseAgent + AgentRegistry — the extensibility seam of the orchestrator.

Adding a new SDLC stage (Designer, Coder, Reviewer) means:
  1. Subclass BaseAgent, set `name` and `produces` class vars.
  2. Decorate with `@AgentRegistry.register`.
  3. Implement the agent's primary method(s) — there's no forced single-method
     signature because each stage has different input/output shapes.

The base class owns shared infrastructure (LLM client, structured logger,
agent name) so concrete agents stay focused on prompting + parsing.
"""
from __future__ import annotations

from typing import ClassVar

from structlog.stdlib import BoundLogger

from app.core.logging import get_logger
from app.llm.client import get_llm_client
from app.llm.types import LLMClient
from app.models import ArtifactKind


class BaseAgent:
    """Base class for all SDLC agents."""

    #: Stable identifier used by the registry and persisted on AgentStep.agent.
    name: ClassVar[str] = ""
    #: Primary artifact kind this agent produces (informational; agents may emit
    #: secondary artifacts like notes or critiques).
    produces: ClassVar[ArtifactKind | None] = None

    def __init__(self, llm: LLMClient | None = None) -> None:
        if not self.name:
            raise TypeError(
                f"{self.__class__.__name__} must set a non-empty `name` class var."
            )
        self._llm: LLMClient = llm if llm is not None else get_llm_client()
        self.logger: BoundLogger = get_logger(f"agent.{self.name}")

    @property
    def llm(self) -> LLMClient:
        return self._llm


class AgentRegistry:
    """Process-wide registry of agent classes, keyed by `BaseAgent.name`."""

    _agents: ClassVar[dict[str, type[BaseAgent]]] = {}

    @classmethod
    def register(cls, agent_cls: type[BaseAgent]) -> type[BaseAgent]:
        if not agent_cls.name:
            raise ValueError(
                f"Cannot register {agent_cls.__name__}: empty `name` class var."
            )
        if agent_cls.name in cls._agents and cls._agents[agent_cls.name] is not agent_cls:
            raise ValueError(
                f"Agent name collision: '{agent_cls.name}' already registered."
            )
        cls._agents[agent_cls.name] = agent_cls
        return agent_cls

    @classmethod
    def get(cls, name: str) -> type[BaseAgent]:
        try:
            return cls._agents[name]
        except KeyError as exc:
            available = ", ".join(sorted(cls._agents)) or "<none>"
            raise KeyError(
                f"Unknown agent '{name}'. Registered: {available}"
            ) from exc

    @classmethod
    def names(cls) -> list[str]:
        return sorted(cls._agents)

    @classmethod
    def _reset(cls) -> None:
        """Test hook."""
        cls._agents.clear()
