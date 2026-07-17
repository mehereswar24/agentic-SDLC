"""PRD (Product Requirements Document) schema.

Schema design notes:

  Gemini's structured-output API enforces an internal "state budget" on the
  response schema. Stacking many `min_length` / `max_length` / `ge` / `le`
  bounds across nested types causes a combinatorial blow-up and the API
  returns 400 INVALID_ARGUMENT ("too many states for serving"). We therefore
  declare only types + required fields in the schema sent to Gemini, and rely
  on (a) the system prompt to guide content quality and (b) Pydantic validation
  on the way back in to reject malformed shapes.

  We do NOT use `extra="forbid"`: Gemini's API rejects `additionalProperties`
  in the response schema.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class _StrictModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class Persona(_StrictModel):
    name: str = Field(description="Short persona name, e.g. 'Daily Commuter'.")
    description: str = Field(
        description="One- to three-sentence portrait covering role, context, and what they care about.",
    )
    key_needs: list[str] = Field(
        description="Concrete needs this persona has. Each entry is a complete clause.",
    )


class AcceptanceCriterion(_StrictModel):
    given: str = Field(description="Precondition / context.")
    when: str = Field(description="Action or trigger.")
    then: str = Field(description="Observable, testable outcome.")


class UserStory(_StrictModel):
    id: str = Field(description="Stable identifier, e.g. 'US-01'.")
    as_a: str = Field(description="The persona (matches a Persona.name).")
    i_want: str = Field(description="The capability the user wants.")
    so_that: str = Field(description="The user-facing value delivered.")
    priority: Priority = Priority.P1
    acceptance_criteria: list[AcceptanceCriterion] = Field(
        description="At least one Given/When/Then criterion that QA can verify.",
    )


class FunctionalRequirement(_StrictModel):
    id: str = Field(description="Stable identifier, e.g. 'FR-01'.")
    statement: str = Field(description="What the system must do, in active voice.")
    rationale: str | None = Field(
        default=None, description="Optional reason — why is this required?"
    )


class NonFunctionalRequirement(_StrictModel):
    id: str = Field(description="Stable identifier, e.g. 'NFR-01'.")
    category: str = Field(
        description="e.g. performance, security, accessibility, scalability, observability.",
    )
    statement: str = Field(
        description="Measurable constraint, e.g. 'p95 latency < 200ms for primary read paths'.",
    )


class Risk(_StrictModel):
    description: str
    severity: Severity = Severity.MEDIUM
    likelihood: Severity = Severity.MEDIUM
    mitigation: str = Field(
        description="Concrete action that reduces the risk, not a platitude.",
    )
    category: str | None = Field(
        default=None,
        description="Risk category, e.g. 'technical', 'operational', 'security'.",
    )


class SuccessMetric(_StrictModel):
    name: str = Field(description="Short metric name.")
    target: str = Field(description="Measurable target, e.g. '>= 40% D7 retention'.")
    instrumentation: str | None = Field(
        default=None,
        description="How the metric is measured (events, dashboards, query).",
    )


class AssumptionRegister(BaseModel):
    """Categorised assumption tracking for a PRD."""

    explicit: list[str] = Field(
        default_factory=list,
        description="Assumptions explicitly stated in the prompt or brief.",
    )
    inferred: list[str] = Field(
        default_factory=list,
        description="Assumptions the agent inferred from context.",
    )
    assumed: list[str] = Field(
        default_factory=list,
        description="Assumptions made without evidence — highest risk.",
    )
    missing: list[str] = Field(
        default_factory=list,
        description="Information that was absent and had to be guessed or skipped.",
    )


class PRD(_StrictModel):
    """Top-level PRD artifact. Versioned via the parent Artifact row."""

    title: str = Field(description="Short product/feature name.")
    summary: str = Field(
        description="2–4 sentence executive summary that a busy stakeholder can skim.",
    )
    problem_statement: str = Field(
        description="The user/business problem being solved. No solutioning here.",
    )
    goals: list[str] = Field(description="Outcome-oriented goals, not features.")
    non_goals: list[str] = Field(description="Explicit out-of-scope items.")
    target_users: list[Persona] = Field(description="Distinct user personas.")
    user_stories: list[UserStory]
    functional_requirements: list[FunctionalRequirement]
    non_functional_requirements: list[NonFunctionalRequirement] = Field(
        description="Measurable cross-cutting concerns: perf, security, a11y, etc.",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Tech / business / legal / time constraints.",
    )
    assumptions: list[str] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    open_questions: list[str] = Field(
        default_factory=list,
        description="Ambiguities the agent could not resolve — these gate downstream work.",
    )
    success_metrics: list[SuccessMetric]
    section_confidence: dict[str, int] = Field(
        default_factory=dict,
        description="Section name -> confidence score 0-100 for each key area.",
    )
    assumption_register: AssumptionRegister | None = None
