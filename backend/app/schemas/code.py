"""Code-generation schemas.

Same Gemini-2.5 schema budget caveat as elsewhere: no size bounds, flat
shapes, no nested optionals deeper than one level.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CodeFile(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    path: str = Field(
        description=(
            "Relative path from the project root, using forward slashes. "
            "Example: 'src/api/health.py' or 'package.json'."
        ),
    )
    language: str = Field(
        description="Language identifier for syntax highlighting (python, typescript, json, markdown, css, etc.).",
    )
    purpose: str = Field(
        description="One-sentence statement of what this file does — used in code review.",
    )
    content: str = Field(description="Full file content. Should be runnable as written.")


class CodeBundle(BaseModel):
    """A minimal-but-coherent codebase scaffold derived from PRD + SystemDesign."""

    model_config = ConfigDict(str_strip_whitespace=True)

    project_name: str = Field(description="Slug-style name, e.g. 'habit-tracker'.")
    description: str = Field(description="One-paragraph summary of what was built.")
    tech_stack: list[str] = Field(
        description="Concrete tech choices, e.g. ['Python 3.12', 'FastAPI', 'SQLite'].",
    )
    files: list[CodeFile] = Field(
        description=(
            "Source files. Aim for 3–6 files that form a runnable v1 — not an "
            "exhaustive codebase. Each file should be 30–150 lines."
        ),
    )
    setup_instructions: str = Field(
        description=(
            "Commands the user runs to install + start the project, in order. "
            "Plain text with one command per line."
        ),
    )
    next_steps: list[str] = Field(
        default_factory=list,
        description="Concrete follow-on work the user would do next.",
    )
