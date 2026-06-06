"""Critique schema — the planner's self-review output.

Bounds on score / list sizes are deliberately omitted from the schema sent to
Gemini (see note in app/schemas/prd.py). The prompt instructs the model to
return a 0–100 score.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Critique(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    score: int = Field(
        description="Overall PRD quality score. 0=unusable, 100=ship-ready.",
    )
    summary: str = Field(
        description="2–3 sentence verdict — what's good, what's missing.",
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Specific problems. Each entry should reference a section or field.",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Concrete fixes the planner should apply on revision.",
    )
    should_revise: bool = Field(
        description=(
            "True if a revision pass is warranted. Independent of score so the "
            "critic can flag e.g. 'score 85 but factual error in FR-03'."
        )
    )
