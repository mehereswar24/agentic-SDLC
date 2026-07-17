"""Schema for AI reviewer agents' output."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ReviewFinding(BaseModel):
    severity: Literal["critical", "high", "medium", "low", "info"] = "medium"
    category: str
    description: str
    location: str = ""
    suggestion: str = ""


class ReviewReport(BaseModel):
    reviewer: str
    score: int = Field(ge=0, le=100)
    passed: bool
    findings: list[ReviewFinding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    summary: str = ""
