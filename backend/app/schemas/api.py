"""API request/response models for /api/runs.

Decoupled from the ORM models so we can evolve the wire format without
touching the schema.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import AgentStep, Artifact, ArtifactKind, Run, RunStatus


class CreateRunRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)
    max_revisions: int = Field(default=1, ge=0, le=2)
    auto_approve: bool = Field(
        default=False,
        description="Skip human approval gates and run all stages to completion.",
    )


class DecisionRequest(BaseModel):
    """Human decision at an approval gate."""

    decision: Literal["approve", "reject"]
    feedback: str | None = Field(default=None, max_length=4000)


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    prompt: str
    status: RunStatus
    error: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class StepView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    node: str
    agent: str | None
    input: dict[str, Any]
    output: dict[str, Any]
    error: str | None
    latency_ms: int | None
    tokens_in: int | None
    tokens_out: int | None
    created_at: datetime

    @classmethod
    def from_model(cls, step: AgentStep) -> "StepView":
        return cls.model_validate(step)


class ArtifactView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: ArtifactKind
    version: int
    content: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_model(cls, art: Artifact) -> "ArtifactView":
        return cls.model_validate(art)


class RunDetail(RunSummary):
    steps: list[StepView] = Field(default_factory=list)
    artifacts: list[ArtifactView] = Field(default_factory=list)

    @classmethod
    def from_model(cls, run: Run) -> "RunDetail":
        return cls(
            id=run.id,
            prompt=run.prompt,
            status=run.status,
            error=run.error,
            meta=run.meta or {},
            created_at=run.created_at,
            updated_at=run.updated_at,
            steps=[StepView.from_model(s) for s in run.steps],
            artifacts=[ArtifactView.from_model(a) for a in run.artifacts],
        )


class RunListResponse(BaseModel):
    runs: list[RunSummary]
    total_returned: int
