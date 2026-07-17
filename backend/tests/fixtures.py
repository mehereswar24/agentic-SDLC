"""Reusable fixtures for building valid PRDs and critiques in tests.

Lives outside conftest so it can be imported explicitly — keeps the test
files self-documenting about what data they depend on.
"""
from __future__ import annotations

from app.schemas import (
    PRD,
    AcceptanceCriterion,
    Critique,
    FunctionalRequirement,
    NonFunctionalRequirement,
    Persona,
    Priority,
    Risk,
    Severity,
    SuccessMetric,
    UserStory,
)


def make_prd(*, title: str = "Habit Tracker") -> PRD:
    return PRD(
        title=title,
        summary=(
            "A mobile app that helps individuals build daily habits through "
            "reminders, streak tracking, and lightweight social accountability. "
            "Targets users who have tried generic to-do apps and lapsed."
        ),
        problem_statement=(
            "People who want to build habits lapse within two weeks because "
            "existing tools surface tasks but not progress, and offer no "
            "social accountability without exposing personal data."
        ),
        goals=[
            "Help users complete a chosen habit for 7 consecutive days within "
            "the first 30 days.",
            "Reach 40% D7 retention.",
        ],
        non_goals=[
            "Calendar integration in v1.",
            "Wearable device integration in v1.",
        ],
        target_users=[
            Persona(
                name="Daily Commuter",
                description=(
                    "Office worker, 25–45, owns a smartphone, has tried 2+ "
                    "productivity apps and abandoned them within a month."
                ),
                key_needs=[
                    "Quick logging during a commute (<5s interactions).",
                    "Visible streak progress to maintain motivation.",
                ],
            )
        ],
        user_stories=[
            UserStory(
                id="US-01",
                as_a="Daily Commuter",
                i_want="to mark a habit complete with one tap",
                so_that="logging does not become a chore in itself",
                priority=Priority.P0,
                acceptance_criteria=[
                    AcceptanceCriterion(
                        given="I am on the home screen with one habit",
                        when="I tap the habit card",
                        then="the habit is marked complete and the streak count increments by 1",
                    )
                ],
            )
        ],
        functional_requirements=[
            FunctionalRequirement(
                id="FR-01",
                statement="The system shall record a habit completion event with timestamp and habit id.",
            )
        ],
        non_functional_requirements=[
            NonFunctionalRequirement(
                id="NFR-01",
                category="performance",
                statement="p95 habit-completion tap-to-confirm latency < 150ms on mid-tier Android devices.",
            )
        ],
        risks=[
            Risk(
                description="Notifications fatigue causes uninstalls.",
                severity=Severity.HIGH,
                likelihood=Severity.MEDIUM,
                mitigation="Cap notifications at 2/day and add per-habit mute.",
            )
        ],
        open_questions=["Should anonymous social accountability be opt-in or opt-out?"],
        success_metrics=[
            SuccessMetric(
                name="D7 retention",
                target=">= 40%",
                instrumentation="cohort analysis on `app_open` events",
            )
        ],
    )


def make_critique(
    *, score: int = 82, should_revise: bool = True, issues: int = 2
) -> Critique:
    return Critique(
        score=score,
        summary=(
            "PRD covers the core problem and a measurable success metric. "
            "User stories need stronger acceptance criteria coverage."
        ),
        issues=[f"placeholder issue {i}" for i in range(issues)],
        suggestions=["Add a second acceptance criterion to US-01 covering offline mode."],
        should_revise=should_revise,
    )


# --- Design / Code fixtures + stub agents for pipeline & API tests -----------

from app.agents.coder import CoderOutput  # noqa: E402
from app.agents.designer import DesignerOutput  # noqa: E402
from app.agents.planner import PlannerOutput  # noqa: E402
from app.agents.planner_reviewer import ReviewerOutput  # noqa: E402
from app.agents.requirement_analyzer import RequirementAnalyzerOutput  # noqa: E402
from app.agents.semantic_validator import SemanticValidatorOutput  # noqa: E402
from app.agents.sprint_planner import SprintPlannerOutput  # noqa: E402
from app.agents.tester import TesterOutput  # noqa: E402
from app.llm.types import TokenUsage  # noqa: E402
from app.schemas import Component, DataModel, SystemDesign  # noqa: E402
from app.schemas.clarifying_questions import (  # noqa: E402
    ClarifyingQuestion,
    ClarifyingQuestions,
)
from app.schemas.code import CodeBundle, CodeFile  # noqa: E402
from app.schemas.review import ReviewFinding, ReviewReport  # noqa: E402
from app.schemas.sprint_plan import Sprint, SprintPlan, SprintTask  # noqa: E402
from app.schemas.test_suite import TestFile, TestSuite  # noqa: E402
from app.schemas.validation import ValidationReport  # noqa: E402


def make_clarifying_questions() -> ClarifyingQuestions:
    return ClarifyingQuestions(
        questions=[
            ClarifyingQuestion(
                id="q-1",
                category="platform",
                question="Which platforms should v1 target?",
                options=["Web", "iOS", "Android"],
            ),
            ClarifyingQuestion(
                id="q-2",
                category="data",
                question="Where should habit data be stored?",
                options=[],
            ),
        ],
        assumptions=["Single-user app; no team features in v1."],
        inferred_scope="A personal habit tracking app.",
    )


def make_review_report(
    *, reviewer: str = "planner_reviewer", score: int = 85, passed: bool = True
) -> ReviewReport:
    return ReviewReport(
        reviewer=reviewer,
        score=score,
        passed=passed,
        findings=[
            ReviewFinding(
                severity="medium",
                category="completeness",
                description="Auth flows are underspecified.",
                location="user_stories",
                suggestion="Add a login/logout story.",
            )
        ],
        recommendations=["Clarify authentication before build."],
        summary="Solid overall; one medium gap.",
    )


def make_validation_report(*, artifact_kind: str = "prd") -> ValidationReport:
    return ValidationReport(
        passed=True,
        score=92,
        issues=[],
        suggestions=[],
        artifact_kind=artifact_kind,
        checked_at="2026-01-01T00:00:00Z",
    )


def make_sprint_plan() -> SprintPlan:
    return SprintPlan(
        sprints=[
            Sprint(
                id="sprint-1",
                name="Sprint 1",
                goal="Set up the foundation and initial models",
                duration_days=14,
                stories=["US-01"],
                tasks=[
                    SprintTask(
                        id="task-1",
                        title="Database setup",
                        description="Initialize SQLite DB",
                        story_points=3,
                        type="db",
                    )
                ],
            )
        ]
    )


def make_test_suite() -> TestSuite:
    return TestSuite(
        framework="pytest",
        test_files=[
            TestFile(
                path="tests/test_main.py",
                content="def test_ok(): assert True",
                test_type="unit",
                covers=["main.py"],
            )
        ],
    )


def make_design(*, title: str = "Habit Tracker — Architecture") -> SystemDesign:
    return SystemDesign(
        title=title,
        overview="Stateless REST API backed by SQLite; a mobile client logs habits.",
        components=[
            Component(
                name="API Server",
                responsibility="Persist habit completion events.",
                technology="FastAPI",
            ),
            Component(
                name="Mobile Client",
                responsibility="Log completions and show streaks.",
                technology="React Native",
            ),
        ],
        data_models=[
            DataModel(
                entity="Habit",
                purpose="A user-defined recurring activity.",
                key_fields=["id", "name", "frequency"],
            ),
        ],
        integration_points=[],
        open_design_questions=[],
    )


def make_code(*, project_name: str = "habit-tracker") -> CodeBundle:
    return CodeBundle(
        project_name=project_name,
        description="Minimal FastAPI habit tracker.",
        tech_stack=["Python 3.12", "FastAPI"],
        files=[
            CodeFile(
                path="main.py",
                language="python",
                purpose="API entrypoint.",
                content="print('ok')",
            ),
        ],
        setup_instructions="uv run uvicorn main:app",
        next_steps=["Add persistence."],
    )


class FastPlanner:
    """Planner stub: draft → critique with no revision."""

    name = "planner"

    async def draft(self, prompt: str, *, context: str | None = None) -> PlannerOutput:
        return PlannerOutput(
            prd=make_prd(),
            critique=None,
            usage=TokenUsage(prompt=10, completion=50, total=60),
            latency_ms=10,
            model="stub",
            finish_reason="STOP",
        )

    async def critique(self, prd: PRD) -> PlannerOutput:
        return PlannerOutput(
            prd=None,
            critique=make_critique(should_revise=False),
            usage=TokenUsage(prompt=5, completion=30, total=35),
            latency_ms=10,
            model="stub",
            finish_reason="STOP",
        )

    async def revise(self, prd: PRD, critique: Critique) -> PlannerOutput:
        self.last_revise_feedback = critique.summary
        revised = prd.model_copy(update={"title": f"{prd.title} (revised)"})
        return PlannerOutput(
            prd=revised,
            critique=None,
            usage=TokenUsage(prompt=10, completion=40, total=50),
            latency_ms=10,
            model="stub",
            finish_reason="STOP",
        )


class StubRequirementAnalyzer:
    name = "requirement_analyzer"

    async def analyze(self, prompt: str) -> RequirementAnalyzerOutput:
        return RequirementAnalyzerOutput(
            questions=make_clarifying_questions(),
            usage=TokenUsage(prompt=10, completion=40, total=50),
            latency_ms=10,
            model="stub",
            finish_reason="STOP",
        )


class StubPlannerReviewer:
    name = "planner_reviewer"

    async def review(self, prd: PRD) -> ReviewerOutput:
        return ReviewerOutput(
            report=make_review_report(reviewer="planner_reviewer"),
            usage=TokenUsage(prompt=10, completion=40, total=50),
            latency_ms=10,
            model="stub",
            finish_reason="STOP",
        )


class StubDesignReviewer:
    """Stands in for the architecture and security reviewers."""

    def __init__(self, reviewer: str) -> None:
        self.name = reviewer
        self._reviewer = reviewer

    async def review(self, design: SystemDesign) -> ReviewerOutput:
        return ReviewerOutput(
            report=make_review_report(reviewer=self._reviewer),
            usage=TokenUsage(prompt=10, completion=40, total=50),
            latency_ms=10,
            model="stub",
            finish_reason="STOP",
        )


class RaisingReviewer:
    """A reviewer that always fails — proves reviews are non-blocking."""

    def __init__(self, reviewer: str = "architecture_reviewer") -> None:
        self.name = reviewer

    async def review(self, design: SystemDesign) -> ReviewerOutput:
        raise RuntimeError("reviewer exploded")


class StubSemanticValidator:
    name = "semantic_validator"

    async def validate(
        self, original_prompt: str, artifact_kind: str, artifact_content: dict
    ) -> SemanticValidatorOutput:
        return SemanticValidatorOutput(
            report=make_validation_report(artifact_kind=artifact_kind),
            usage=TokenUsage(prompt=10, completion=40, total=50),
            latency_ms=10,
            model="stub",
            finish_reason="STOP",
        )


class StubDesigner:
    name = "designer"

    def __init__(self) -> None:
        self.last_feedback: str | None = None
        self.last_previous: SystemDesign | None = None

    async def design(
        self,
        prd: PRD,
        *,
        previous: SystemDesign | None = None,
        feedback: str | None = None,
    ) -> DesignerOutput:
        self.last_feedback = feedback
        self.last_previous = previous
        title = "Habit Tracker — Architecture (revised)" if feedback else "Habit Tracker — Architecture"
        return DesignerOutput(
            design=make_design(title=title),
            usage=TokenUsage(prompt=20, completion=100, total=120),
            latency_ms=50,
            model="stub",
            finish_reason="STOP",
        )


class StubCoder:
    name = "coder"

    def __init__(self) -> None:
        self.last_sprint_plan: SprintPlan | None = None

    async def build(
        self, prd: PRD, design: SystemDesign, sprint_plan: SprintPlan | None = None
    ) -> CoderOutput:
        self.last_sprint_plan = sprint_plan
        return CoderOutput(
            code=make_code(),
            usage=TokenUsage(prompt=30, completion=200, total=230),
            latency_ms=80,
            model="stub",
            finish_reason="STOP",
        )


class StubSprintPlanner:
    name = "sprint_planner"

    def __init__(self) -> None:
        self.last_feedback: str | None = None

    async def plan(
        self,
        prd: PRD,
        design: SystemDesign,
        *,
        previous: SprintPlan | None = None,
        feedback: str | None = None,
    ) -> SprintPlannerOutput:
        self.last_feedback = feedback
        return SprintPlannerOutput(
            plan=make_sprint_plan(),
            usage=TokenUsage(prompt=30, completion=200, total=230),
            latency_ms=80,
            model="stub",
            finish_reason="STOP",
        )


class StubTester:
    name = "tester"

    async def generate_tests(self, code: CodeBundle) -> TesterOutput:
        return TesterOutput(
            test_suite=make_test_suite(),
            usage=TokenUsage(prompt=30, completion=200, total=230),
            latency_ms=80,
            model="stub",
            finish_reason="STOP",
        )
