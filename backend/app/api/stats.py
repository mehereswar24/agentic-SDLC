"""Aggregate run + token metrics. Cheap, single-query summary; intended for a
small UI widget rather than full observability."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.core.auth import require_api_key
from app.core.db import session_scope
from app.models import AgentStep, Run, RunStatus

router = APIRouter(
    prefix="/api/stats",
    tags=["stats"],
    dependencies=[Depends(require_api_key)],
)


@router.get("")
async def get_stats() -> dict[str, Any]:
    async with session_scope() as s:
        # Counts by status
        status_rows = (
            await s.execute(select(Run.status, func.count(Run.id)).group_by(Run.status))
        ).all()
        by_status = {str(status.value if hasattr(status, "value") else status): count for status, count in status_rows}

        total_runs = sum(by_status.values())

        # Token & latency aggregates from AgentSteps
        agg = (
            await s.execute(
                select(
                    func.coalesce(func.sum(AgentStep.tokens_in), 0),
                    func.coalesce(func.sum(AgentStep.tokens_out), 0),
                    func.coalesce(func.avg(AgentStep.latency_ms), 0),
                    func.count(AgentStep.id),
                )
            )
        ).one()
        tokens_in, tokens_out, avg_latency_ms, step_count = agg

    return {
        "total_runs": total_runs,
        "by_status": {
            "pending": by_status.get("pending", 0),
            "running": by_status.get("running", 0),
            "completed": by_status.get(RunStatus.COMPLETED.value, 0),
            "failed": by_status.get(RunStatus.FAILED.value, 0),
            "cancelled": by_status.get(RunStatus.CANCELLED.value, 0),
        },
        "agent_steps": int(step_count),
        "tokens_in_total": int(tokens_in),
        "tokens_out_total": int(tokens_out),
        "avg_step_latency_ms": int(avg_latency_ms or 0),
    }
