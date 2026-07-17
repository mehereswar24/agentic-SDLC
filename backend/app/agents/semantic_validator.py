"""SemanticValidatorAgent — checks that an artifact addresses the original prompt.

This agent runs as a non-blocking side step after the draft stage. It never
aborts the pipeline — if it fails, the orchestrator logs a warning and
continues. Its output is persisted as a VALIDATION_REPORT artifact so the
frontend can surface it to the user.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.prompts.semantic_validator import SEMANTIC_VALIDATOR_SYSTEM_PROMPT
from app.llm.client import get_llm_client
from app.llm.types import LLMClient, TokenUsage
from app.models import ArtifactKind
from app.schemas.validation import ValidationReport


@dataclass(slots=True)
class SemanticValidatorOutput:
    """Telemetry-rich return value from SemanticValidatorAgent.validate()."""

    report: ValidationReport
    usage: TokenUsage
    latency_ms: int
    model: str
    finish_reason: str | None


@AgentRegistry.register
class SemanticValidatorAgent(BaseAgent):
    """Validates an artifact against the original user prompt."""

    name = "semantic_validator"
    produces = ArtifactKind.VALIDATION_REPORT

    VALIDATE_TEMPERATURE = 0.1  # deterministic — consistency matters here

    def __init__(self, llm: LLMClient | None = None) -> None:
        super().__init__(llm=llm if llm is not None else get_llm_client())

    async def validate(
        self,
        original_prompt: str,
        artifact_kind: str,
        artifact_content: dict,  # type: ignore[type-arg]
    ) -> SemanticValidatorOutput:
        """Check whether `artifact_content` addresses `original_prompt`.

        Parameters
        ----------
        original_prompt:
            The user's original request, verbatim.
        artifact_kind:
            String label for the artifact type, e.g. ``"prd"`` or
            ``"system_design"``.
        artifact_content:
            The artifact serialised as a plain dict (from
            ``model.model_dump(mode="json")``).

        Returns
        -------
        SemanticValidatorOutput
            Contains the ValidationReport and standard telemetry fields.
        """
        user_message = (
            "Validate the following artifact against the original prompt.\n\n"
            f"original_prompt:\n{original_prompt}\n\n"
            f"artifact_kind: {artifact_kind}\n\n"
            "artifact_content (JSON):\n"
            f"{json.dumps(artifact_content, indent=2, default=str)}"
        )

        self.logger.info(
            "semantic_validator_start",
            artifact_kind=artifact_kind,
            prompt_chars=len(original_prompt),
        )

        result = await self._llm.chat(
            user_message,
            system=SEMANTIC_VALIDATOR_SYSTEM_PROMPT,
            schema=ValidationReport,
            temperature=self.VALIDATE_TEMPERATURE,
        )

        assert result.parsed is not None, "schema=ValidationReport guarantees parsed is set"

        self.logger.info(
            "semantic_validator_done",
            artifact_kind=artifact_kind,
            score=result.parsed.score,
            passed=result.parsed.passed,
            issues=len(result.parsed.issues),
            latency_ms=result.latency_ms,
        )

        return SemanticValidatorOutput(
            report=result.parsed,
            usage=result.usage,
            latency_ms=result.latency_ms,
            model=result.model,
            finish_reason=result.finish_reason,
        )
