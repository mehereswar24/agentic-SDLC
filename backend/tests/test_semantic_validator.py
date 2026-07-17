"""Unit tests for SemanticValidatorAgent and ValidationReport schema.

These tests use stub LLM clients so no real API calls are made.
The suite covers:
  - ValidationReport schema validation (valid, edge-cases, rejects bad input).
  - SemanticValidatorAgent.validate() happy path.
  - SemanticValidatorAgent.validate() handles LLM errors gracefully.
  - Orchestrator integration: semantic_validate step is non-blocking
    (pipeline completes even when the validator raises).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.agents.semantic_validator import SemanticValidatorAgent, SemanticValidatorOutput
from app.llm.types import LLMResult, TokenUsage
from app.models import ArtifactKind
from app.schemas.validation import ValidationReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(
    *,
    passed: bool = True,
    score: int = 85,
    issues: list[str] | None = None,
    suggestions: list[str] | None = None,
    artifact_kind: str = "prd",
    checked_at: str = "2026-07-15T00:00:00Z",
) -> ValidationReport:
    return ValidationReport(
        passed=passed,
        score=score,
        issues=issues or [],
        suggestions=suggestions or [],
        artifact_kind=artifact_kind,
        checked_at=checked_at,
    )


def _make_llm_result(report: ValidationReport) -> LLMResult[ValidationReport]:
    """Wrap a ValidationReport in an LLMResult as the stub LLM would return."""
    return LLMResult(
        text=report.model_dump_json(),
        parsed=report,
        usage=TokenUsage(prompt=50, completion=100, total=150),
        latency_ms=42,
        model="stub-model",
        finish_reason="STOP",
    )


def _make_stub_llm(report: ValidationReport) -> MagicMock:
    """Return a mock LLM client whose chat() returns `report`."""
    llm = MagicMock()
    llm.chat = AsyncMock(return_value=_make_llm_result(report))
    return llm


# ---------------------------------------------------------------------------
# ValidationReport schema tests
# ---------------------------------------------------------------------------

class TestValidationReportSchema:
    def test_valid_minimal(self) -> None:
        r = ValidationReport(passed=True, score=80, artifact_kind="prd")
        assert r.passed is True
        assert r.score == 80
        assert r.issues == []
        assert r.suggestions == []
        assert r.checked_at == ""

    def test_valid_full(self) -> None:
        r = _make_report(
            passed=False,
            score=45,
            issues=["FR-01 not addressed"],
            suggestions=["Add FR-01 to functional_requirements"],
            artifact_kind="system_design",
            checked_at="2026-07-15T12:00:00Z",
        )
        assert r.passed is False
        assert r.score == 45
        assert len(r.issues) == 1
        assert len(r.suggestions) == 1

    def test_score_boundary_zero(self) -> None:
        r = ValidationReport(passed=False, score=0, artifact_kind="prd")
        assert r.score == 0

    def test_score_boundary_hundred(self) -> None:
        r = ValidationReport(passed=True, score=100, artifact_kind="prd")
        assert r.score == 100

    def test_score_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ValidationReport(passed=False, score=-1, artifact_kind="prd")

    def test_score_above_hundred_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ValidationReport(passed=True, score=101, artifact_kind="prd")

    def test_score_wrong_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ValidationReport(passed=True, score="high", artifact_kind="prd")  # type: ignore[arg-type]

    def test_passed_required(self) -> None:
        with pytest.raises(ValidationError):
            ValidationReport(score=80, artifact_kind="prd")  # type: ignore[call-arg]

    def test_artifact_kind_required(self) -> None:
        with pytest.raises(ValidationError):
            ValidationReport(passed=True, score=80)  # type: ignore[call-arg]

    def test_round_trip_json(self) -> None:
        r = _make_report(score=72, issues=["Missing auth"], suggestions=["Add auth section"])
        revived = ValidationReport.model_validate_json(r.model_dump_json())
        assert revived == r

    def test_extra_fields_ignored(self) -> None:
        """Pydantic should not raise on unknown fields (no extra='forbid')."""
        data = {"passed": True, "score": 90, "artifact_kind": "prd", "unknown_field": "x"}
        r = ValidationReport.model_validate(data)
        assert r.score == 90


# ---------------------------------------------------------------------------
# SemanticValidatorAgent unit tests
# ---------------------------------------------------------------------------

class TestSemanticValidatorAgent:
    def test_class_attributes(self) -> None:
        assert SemanticValidatorAgent.name == "semantic_validator"
        assert SemanticValidatorAgent.produces == ArtifactKind.VALIDATION_REPORT

    @pytest.mark.asyncio
    async def test_validate_happy_path(self) -> None:
        report = _make_report(passed=True, score=88, issues=[], artifact_kind="prd")
        agent = SemanticValidatorAgent(llm=_make_stub_llm(report))

        artifact = {"title": "Habit Tracker", "summary": "Track daily habits."}
        out = await agent.validate(
            original_prompt="Build a habit tracker app",
            artifact_kind="prd",
            artifact_content=artifact,
        )

        assert isinstance(out, SemanticValidatorOutput)
        assert out.report.passed is True
        assert out.report.score == 88
        assert out.latency_ms == 42
        assert out.model == "stub-model"
        assert out.finish_reason == "STOP"
        assert out.usage.prompt == 50
        assert out.usage.completion == 100

    @pytest.mark.asyncio
    async def test_validate_failing_report(self) -> None:
        report = _make_report(
            passed=False,
            score=40,
            issues=["Offline mode requirement not addressed"],
            suggestions=["Add offline support section to NFRs"],
            artifact_kind="prd",
        )
        agent = SemanticValidatorAgent(llm=_make_stub_llm(report))

        out = await agent.validate(
            original_prompt="Build a habit tracker with offline support",
            artifact_kind="prd",
            artifact_content={"title": "Habit Tracker"},
        )

        assert out.report.passed is False
        assert out.report.score == 40
        assert len(out.report.issues) == 1
        assert "offline" in out.report.issues[0].lower()

    @pytest.mark.asyncio
    async def test_validate_passes_correct_user_message(self) -> None:
        """Verify the user message sent to the LLM includes prompt, kind, and artifact."""
        report = _make_report(score=90, artifact_kind="system_design")
        llm = _make_stub_llm(report)
        agent = SemanticValidatorAgent(llm=llm)

        await agent.validate(
            original_prompt="Design a microservices architecture",
            artifact_kind="system_design",
            artifact_content={"title": "Microservices Architecture"},
        )

        call_args = llm.chat.call_args
        user_message: str = call_args[0][0]
        assert "Design a microservices architecture" in user_message
        assert "system_design" in user_message
        assert "Microservices Architecture" in user_message

    @pytest.mark.asyncio
    async def test_validate_uses_low_temperature(self) -> None:
        """Validator should request temperature=0.1 for determinism."""
        report = _make_report(score=75, artifact_kind="prd")
        llm = _make_stub_llm(report)
        agent = SemanticValidatorAgent(llm=llm)

        await agent.validate("Build X", "prd", {"title": "X"})

        call_kwargs = llm.chat.call_args[1]
        assert call_kwargs.get("temperature") == pytest.approx(0.1)

    @pytest.mark.asyncio
    async def test_validate_passes_schema_to_llm(self) -> None:
        """The LLM must be asked to parse into ValidationReport."""
        report = _make_report(score=75, artifact_kind="prd")
        llm = _make_stub_llm(report)
        agent = SemanticValidatorAgent(llm=llm)

        await agent.validate("Build X", "prd", {"title": "X"})

        call_kwargs = llm.chat.call_args[1]
        assert call_kwargs.get("schema") is ValidationReport

    @pytest.mark.asyncio
    async def test_uses_default_llm_client_when_none_provided(self) -> None:
        """When llm=None, the agent should call get_llm_client() — verify no crash."""
        with patch(
            "app.agents.semantic_validator.get_llm_client",
            return_value=_make_stub_llm(_make_report()),
        ):
            agent = SemanticValidatorAgent()
            assert agent.name == "semantic_validator"


# ---------------------------------------------------------------------------
# Orchestrator integration: semantic_validate is non-blocking
# ---------------------------------------------------------------------------

class TestSemanticValidateNonBlocking:
    """The orchestrator must not abort the pipeline when validation fails."""

    @pytest.mark.asyncio
    async def test_pipeline_completes_when_validator_raises(
        self, engine: None
    ) -> None:
        """Even if SemanticValidatorAgent raises, the plan stage finishes."""
        from app.models import RunStatus
        from app.orchestrator.events import EventBus
        from app.orchestrator.repository import RunRepository
        from app.orchestrator.runner import Orchestrator
        from tests.fixtures import FastPlanner

        repo = RunRepository()
        bus = EventBus()

        run = await repo.create_run("habit tracker", meta={"auto_approve": False})

        # Make the validator always raise.
        with patch(
            "app.orchestrator.runner.SemanticValidatorAgent",
            side_effect=RuntimeError("LLM exploded"),
        ):
            orch = Orchestrator(
                repo=repo,
                bus=bus,
                agent_factory=lambda: FastPlanner(),
            )
            await orch.run(run.id)

        final = await repo.get_run(run.id)
        assert final is not None
        # Planner-only mode: one stage with no approval gate → COMPLETED.
        assert final.status in (RunStatus.COMPLETED, RunStatus.AWAITING_HUMAN)
        # PRD artifact must still exist.
        assert any(a.kind.value == "prd" for a in final.artifacts)

    @pytest.mark.asyncio
    async def test_pipeline_completes_when_validator_validate_raises(
        self, engine: None
    ) -> None:
        """Even if validate() call raises mid-flight, pipeline continues."""
        from app.models import RunStatus
        from app.orchestrator.events import EventBus
        from app.orchestrator.repository import RunRepository
        from app.orchestrator.runner import Orchestrator
        from tests.fixtures import FastPlanner

        repo = RunRepository()
        bus = EventBus()
        run = await repo.create_run("habit tracker", meta={"auto_approve": False})

        failing_agent = MagicMock()
        failing_agent.name = "semantic_validator"
        failing_agent.validate = AsyncMock(side_effect=ValueError("parse error"))

        with patch(
            "app.orchestrator.runner.SemanticValidatorAgent",
            return_value=failing_agent,
        ):
            orch = Orchestrator(
                repo=repo,
                bus=bus,
                agent_factory=lambda: FastPlanner(),
            )
            await orch.run(run.id)

        final = await repo.get_run(run.id)
        assert final is not None
        assert final.status in (RunStatus.COMPLETED, RunStatus.AWAITING_HUMAN)
        # Validation report artifact should NOT be present (it failed).
        assert not any(a.kind.value == "validation_report" for a in final.artifacts)

    @pytest.mark.asyncio
    async def test_validation_report_persisted_on_success(
        self, engine: None
    ) -> None:
        """When validation succeeds, the artifact is stored."""
        from app.models import RunStatus
        from app.orchestrator.events import EventBus
        from app.orchestrator.repository import RunRepository
        from app.orchestrator.runner import Orchestrator
        from tests.fixtures import FastPlanner

        report = _make_report(passed=True, score=90, artifact_kind="prd")
        stub_agent = MagicMock()
        stub_agent.name = "semantic_validator"
        stub_agent.validate = AsyncMock(
            return_value=SemanticValidatorOutput(
                report=report,
                usage=TokenUsage(prompt=10, completion=20, total=30),
                latency_ms=5,
                model="stub",
                finish_reason="STOP",
            )
        )

        repo = RunRepository()
        bus = EventBus()
        run = await repo.create_run("habit tracker", meta={"auto_approve": False})

        with patch(
            "app.orchestrator.runner.SemanticValidatorAgent",
            return_value=stub_agent,
        ):
            orch = Orchestrator(
                repo=repo,
                bus=bus,
                agent_factory=lambda: FastPlanner(),
            )
            await orch.run(run.id)

        final = await repo.get_run(run.id)
        assert final is not None
        # Should have persisted a validation_report artifact.
        val_arts = [a for a in final.artifacts if a.kind.value == "validation_report"]
        assert len(val_arts) == 1
        assert val_arts[0].content["score"] == 90
        assert val_arts[0].content["passed"] is True
