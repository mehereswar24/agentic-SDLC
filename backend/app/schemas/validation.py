"""ValidationReport schema — output of the SemanticValidatorAgent."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ValidationReport(BaseModel):
    """Result of a semantic validation check against the original prompt."""

    passed: bool
    score: int = Field(ge=0, le=100, description="Overall alignment score 0-100.")
    issues: list[str] = Field(
        default_factory=list,
        description="Specific requirements missing or mismatched.",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Actionable suggestions to improve alignment.",
    )
    artifact_kind: str = Field(
        description="The kind of artifact that was validated, e.g. 'prd'."
    )
    checked_at: str = Field(
        default="",
        description="ISO-8601 timestamp when the validation ran.",
    )
