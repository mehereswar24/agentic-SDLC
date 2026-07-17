"""REST endpoints for orchestrator runs.

POST /api/runs        — create a run + spawn the orchestrator in the background.
GET  /api/runs        — list recent runs (most recent first).
GET  /api/runs/{id}   — full run detail with all steps + artifacts.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.core.auth import require_api_key
from app.core.config import Settings, get_settings
from app.core.errors import (
    ConflictError,
    LLMUnavailableError,
    NotFoundError,
    ValidationFailedError,
)
from app.models import RunStatus
from app.orchestrator.events import Event, EventType, get_event_bus
from app.orchestrator.repository import RunRepository
from app.orchestrator.runner import REVISABLE_STAGES
from app.orchestrator.runtime import get_runtime
from app.schemas.api import (
    ArtifactVersionsResponse,
    ArtifactVersionSummary,
    ArtifactView,
    ClarificationAnswersRequest,
    CreateRunRequest,
    DecisionRequest,
    RunDetail,
    RunListResponse,
    RunSummary,
)
from app.models import ArtifactKind
from typing import Any
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from app.llm.client import get_planner_llm_client

from app.schemas.prd import PRD
from app.schemas.design import SystemDesign
from app.schemas.sprint_plan import SprintPlan
from app.schemas.code import CodeBundle
from app.schemas.test_suite import TestSuite

SCHEMA_MAP = {
    "prd": PRD,
    "system_design": SystemDesign,
    "sprint_plan": SprintPlan,
    "code": CodeBundle,
    "test_suite": TestSuite
}

class ParseRequest(BaseModel):
    text: str

router = APIRouter(
    prefix="/api/runs",
    tags=["runs"],
    dependencies=[Depends(require_api_key)],
)


def _repo() -> RunRepository:
    return RunRepository()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=RunSummary)
async def create_run(
    req: CreateRunRequest,
    repo: RunRepository = Depends(_repo),
    settings: Settings = Depends(get_settings),
) -> RunSummary:
    if not settings.llm_configured:
        raise LLMUnavailableError(
            "GOOGLE_API_KEY is not configured — cannot start a run."
        )
    run = await repo.create_run(
        req.prompt,
        meta={"max_revisions": req.max_revisions, "auto_approve": req.auto_approve},
    )
    get_runtime().spawn(run.id)
    return RunSummary.model_validate(run)


@router.post("/{run_id}/decision", response_model=RunSummary)
async def decide_run(
    run_id: str,
    req: DecisionRequest,
    repo: RunRepository = Depends(_repo),
    settings: Settings = Depends(get_settings),
) -> RunSummary:
    """Approve or reject a run paused at an approval gate.

    `approve` resumes the pipeline from the next stage; `reject` cancels the run.
    """
    run = await repo.get_run(run_id)
    if run is None:
        raise NotFoundError(f"Run '{run_id}' not found")
    if run.status != RunStatus.AWAITING_HUMAN:
        raise ConflictError(
            f"Run is not awaiting approval (current status: {run.status.value})."
        )

    if req.decision == "approve":
        if not settings.llm_configured:
            raise LLMUnavailableError(
                "GOOGLE_API_KEY is not configured — cannot resume the run."
            )
        # Flip to RUNNING before spawning so a duplicate approval hits the
        # AWAITING_HUMAN guard above and is rejected.
        await repo.set_status(run_id, RunStatus.RUNNING)
        get_runtime().spawn(run_id)
    elif req.decision == "revise":
        stage = (run.meta or {}).get("last_completed_stage")
        if stage == "clarify":
            raise ConflictError(
                "The clarify stage is answered, not revised — POST "
                f"/api/runs/{run_id}/clarifications instead."
            )
        if stage not in REVISABLE_STAGES:
            raise ConflictError(f"Stage '{stage}' does not support revision.")
        if not settings.llm_configured:
            raise LLMUnavailableError(
                "GOOGLE_API_KEY is not configured — cannot revise the run."
            )
        await repo.update_meta(
            run_id, {"pending_revision": {"stage": stage, "feedback": req.feedback}}
        )
        await repo.set_status(run_id, RunStatus.RUNNING)
        get_runtime().spawn(run_id)
    else:
        reason = req.feedback or "Rejected by reviewer."
        await repo.update_meta(run_id, {"awaiting_stage": None, "rejection": reason})
        await repo.set_status(run_id, RunStatus.CANCELLED, error=reason)
        await get_event_bus().publish(
            Event(
                type=EventType.RUN_CANCELLED,
                run_id=run_id,
                payload={"reason": reason},
            )
        )

    updated = await repo.get_run(run_id)
    return RunSummary.model_validate(updated or run)


@router.post("/{run_id}/clarifications", response_model=RunSummary)
async def submit_clarifications(
    run_id: str,
    req: ClarificationAnswersRequest,
    repo: RunRepository = Depends(_repo),
    settings: Settings = Depends(get_settings),
) -> RunSummary:
    """Answer the clarify stage's questions and resume the pipeline.

    Answers are merged into `Run.meta.clarification_answers`, which the planner
    stage formats into its drafting context.
    """
    run = await repo.get_run(run_id)
    if run is None:
        raise NotFoundError(f"Run '{run_id}' not found")
    meta = run.meta or {}
    if run.status != RunStatus.AWAITING_HUMAN or meta.get("last_completed_stage") != "clarify":
        raise ConflictError(
            "Run is not awaiting clarification answers "
            f"(status: {run.status.value}, last stage: {meta.get('last_completed_stage')})."
        )
    if not settings.llm_configured:
        raise LLMUnavailableError(
            "GOOGLE_API_KEY is not configured — cannot resume the run."
        )

    existing = dict(meta.get("clarification_answers") or {})
    await repo.update_meta(
        run_id, {"clarification_answers": {**existing, **req.answers}}
    )
    # RUNNING before spawn so a duplicate submission hits the guard above.
    await repo.set_status(run_id, RunStatus.RUNNING)
    get_runtime().spawn(run_id)

    updated = await repo.get_run(run_id)
    return RunSummary.model_validate(updated or run)


@router.post("/{run_id}/retry", response_model=RunSummary)
async def retry_run(
    run_id: str,
    repo: RunRepository = Depends(_repo),
    settings: Settings = Depends(get_settings),
) -> RunSummary:
    """Retry a failed run from its last completed stage."""
    run = await repo.get_run(run_id)
    if run is None:
        raise NotFoundError(f"Run '{run_id}' not found")
    if run.status != RunStatus.FAILED:
        raise ConflictError("Only failed runs can be retried.")
        
    if not settings.llm_configured:
        raise LLMUnavailableError("GOOGLE_API_KEY is not configured.")
        
    await repo.set_status(run_id, RunStatus.RUNNING, error=None)
    get_runtime().spawn(run_id)
    
    updated = await repo.get_run(run_id)
    return RunSummary.model_validate(updated or run)


@router.get("/{run_id}/artifacts/{kind}/versions", response_model=ArtifactVersionsResponse)
async def list_artifact_versions(
    run_id: str,
    kind: ArtifactKind,
    repo: RunRepository = Depends(_repo),
) -> ArtifactVersionsResponse:
    """Content-free version history for one artifact kind."""
    run = await repo.get_run(run_id)
    if run is None:
        raise NotFoundError(f"Run '{run_id}' not found")
    versions = await repo.list_artifact_versions(run_id, kind)
    return ArtifactVersionsResponse(
        kind=kind,
        versions=[ArtifactVersionSummary.model_validate(a) for a in versions],
        total=len(versions),
    )


@router.get("/{run_id}/artifacts/{kind}/versions/{version}", response_model=ArtifactView)
async def get_artifact_version(
    run_id: str,
    kind: ArtifactKind,
    version: int,
    repo: RunRepository = Depends(_repo),
) -> ArtifactView:
    run = await repo.get_run(run_id)
    if run is None:
        raise NotFoundError(f"Run '{run_id}' not found")
    art = await repo.get_artifact_version(run_id, kind, version)
    if art is None:
        raise NotFoundError(f"No {kind.value} artifact at version {version}")
    return ArtifactView.from_model(art)


@router.put("/{run_id}/artifacts/{kind}", response_model=ArtifactView)
async def update_artifact(
    run_id: str,
    kind: ArtifactKind,
    content: dict[str, Any],
    repo: RunRepository = Depends(_repo),
) -> ArtifactView:
    """Manually update an artifact (e.g. user editing PRD before approval).
    Creates a new version of the artifact.
    """
    run = await repo.get_run(run_id)
    if run is None:
        raise NotFoundError(f"Run '{run_id}' not found")
    if run.status in (RunStatus.RUNNING, RunStatus.PENDING):
        raise ConflictError(
            "Cannot edit artifacts while the run is executing — a stage could "
            "read the artifact mid-write."
        )

    schema = SCHEMA_MAP.get(kind.value)
    if schema is not None:
        # Validate now so a malformed edit fails here with details instead of
        # poisoning the next pipeline stage; persist the normalized form.
        try:
            parsed = schema.model_validate(content)
        except PydanticValidationError as exc:
            raise ValidationFailedError(
                f"Content does not match the {kind.value} schema.",
                details={"errors": exc.errors(include_url=False)},
            ) from exc
        content = parsed.model_dump(mode="json")

    art = await repo.save_artifact(run_id, kind=kind, content=content)
    await repo.append_step(
        run_id,
        node="artifact_edit",
        agent=None,
        input={"kind": kind.value},
        output={"version": art.version},
    )
    return ArtifactView.from_model(art)


@router.post("/{run_id}/artifacts/{kind}/parse", response_model=ArtifactView)
async def parse_artifact(
    run_id: str,
    kind: ArtifactKind,
    req: ParseRequest,
    repo: RunRepository = Depends(_repo),
) -> ArtifactView:
    """Uses the LLM to parse unstructured text back into the structured artifact schema."""
    run = await repo.get_run(run_id)
    if run is None:
        raise NotFoundError(f"Run '{run_id}' not found")
    if run.status in (RunStatus.RUNNING, RunStatus.PENDING):
        raise ConflictError(
            "Cannot edit artifacts while the run is executing — a stage could "
            "read the artifact mid-write."
        )

    schema = SCHEMA_MAP.get(kind.value)
    if not schema:
        raise ValidationFailedError(f"Artifact kind '{kind.value}' is not editable.")

    client = get_planner_llm_client()
    prompt = f"Parse the following unstructured text into the exact JSON schema required for a {kind.value}. Make sure to extract all relevant details from the text:\n\n{req.text}"

    result = await client.chat(prompt, schema=schema, temperature=0.1)
    if not result.parsed:
        raise ValidationFailedError("LLM failed to produce the requested schema.")

    art = await repo.save_artifact(
        run_id, kind=kind, content=result.parsed.model_dump(mode="json")
    )
    await repo.append_step(
        run_id,
        node="artifact_edit",
        agent=None,
        input={"kind": kind.value, "source": "parse"},
        output={"version": art.version},
    )
    return ArtifactView.from_model(art)


@router.get("", response_model=RunListResponse)
async def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    repo: RunRepository = Depends(_repo),
) -> RunListResponse:
    runs = await repo.list_runs(limit=limit, offset=offset)
    return RunListResponse(
        runs=[RunSummary.model_validate(r) for r in runs],
        total_returned=len(runs),
    )


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: str, repo: RunRepository = Depends(_repo)) -> RunDetail:
    run = await repo.get_run(run_id)
    if run is None:
        raise NotFoundError(f"Run '{run_id}' not found")
    return RunDetail.from_model(run)


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(run_id: str, repo: RunRepository = Depends(_repo)) -> None:
    """Delete a specific run and its associated steps and artifacts."""
    success = await repo.delete_run(run_id)
    if not success:
        raise NotFoundError(f"Run '{run_id}' not found")


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_runs(repo: RunRepository = Depends(_repo)) -> None:
    """Clear all runs history."""
    await repo.delete_all_runs()
