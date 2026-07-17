"""Schema for the Requirement Analyzer agent's output — clarifying questions."""
from __future__ import annotations

from typing import Literal  # noqa: F401 — kept for future discriminated-union extensions

from pydantic import BaseModel, Field


class ClarifyingQuestion(BaseModel):
    id: str
    category: str
    question: str
    options: list[str] = Field(default_factory=list)
    required: bool = True


class ClarifyingQuestions(BaseModel):
    questions: list[ClarifyingQuestion]
    assumptions: list[str] = Field(default_factory=list)
    inferred_scope: str = ""
