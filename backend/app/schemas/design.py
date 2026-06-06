"""SystemDesign schema — the DesignerAgent's output.

This is intentionally minimal. The point of having it in the codebase is to
prove that the BaseAgent + AgentRegistry extensibility seam works for a
second SDLC stage. Full Designer implementation is future work.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Component(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(description="Short component name, e.g. 'API Gateway'.")
    responsibility: str = Field(
        description="One-sentence statement of what this component owns."
    )
    technology: str | None = Field(
        default=None, description="Concrete tech choice if decided (e.g. 'FastAPI', 'Postgres')."
    )


class DataModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    entity: str = Field(description="Entity / table / collection name.")
    purpose: str = Field(description="What this entity represents.")
    key_fields: list[str] = Field(description="A few defining attributes.")


class SystemDesign(BaseModel):
    """Lightweight architecture sketch derived from a PRD."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str
    overview: str = Field(description="2–3 sentence architectural summary.")
    components: list[Component]
    data_models: list[DataModel]
    integration_points: list[str] = Field(
        default_factory=list,
        description="External systems / APIs this design relies on.",
    )
    open_design_questions: list[str] = Field(default_factory=list)
