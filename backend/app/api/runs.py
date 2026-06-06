"""REST endpoints for orchestrator runs.

POST /api/runs        — create a run + spawn the orchestrator in the background.
GET  /api/runs        — list recent runs (most recent first).
GET  /api/runs/{id}   — full run detail with all steps + artifacts.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.core.auth import require_api_key
from app.core.config import Settings, get_settings
from app.core.errors import ConflictError, LLMUnavailableError, NotFoundError
from app.models import RunStatus
from app.orchestrator.events import Event, EventType, get_event_bus
from app.orchestrator.repository import RunRepository
from app.orchestrator.runtime import get_runtime
from app.schemas.api import (
    CreateRunRequest,
    DecisionRequest,
    RunDetail,
    RunListResponse,
    RunSummary,
)

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
