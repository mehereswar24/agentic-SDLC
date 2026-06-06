"""Planner diagnostic endpoints — useful before the orchestrator exists.

`POST /planner/draft` runs a single draft (no critique loop).
`POST /planner/run`   runs draft → critique → optional revise.

Both are dev-only and intended to validate prompt quality without the full
orchestrator scaffolding. They return both structured JSON and a Markdown
render so the response is human-readable.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.planner import PlannerAgent, render_prd_markdown
from app.core.config import Settings, get_settings
from app.core.errors import LLMUnavailableError
from app.llm.errors import LLMError

router = APIRouter(prefix="/planner", tags=["planner"])


class PlannerRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)
    context: str | None = Field(default=None, max_length=8000)


class PlannerRunRequest(PlannerRequest):
    max_revisions: int = Field(default=1, ge=0, le=2)


def _build_agent(settings: Settings) -> PlannerAgent:
    if settings.environment != "dev":
        raise LLMUnavailableError("Planner diagnostic endpoints are dev-only.")
    if not settings.llm_configured:
        raise LLMUnavailableError("GOOGLE_API_KEY is not configured.")
    return PlannerAgent()


@router.post("/draft")
async def planner_draft(
    req: PlannerRequest, settings: Settings = Depends(get_settings)
) -> dict[str, Any]:
    agent = _build_agent(settings)
    try:
        out = await agent.draft(req.prompt, context=req.context)
    except LLMError as exc:
        raise LLMUnavailableError(str(exc)) from exc
    assert out.prd is not None
    return {
        "prd": out.prd.model_dump(mode="json"),
        "markdown": render_prd_markdown(out.prd),
        "telemetry": {
            "model": out.model,
            "latency_ms": out.latency_ms,
            "tokens_in": out.usage.prompt,
            "tokens_out": out.usage.completion,
            "finish_reason": out.finish_reason,
        },
    }


@router.post("/run")
async def planner_run(
    req: PlannerRunRequest, settings: Settings = Depends(get_settings)
) -> dict[str, Any]:
    """Full draft → critique → revise (≤ max_revisions) loop."""
    agent = _build_agent(settings)
    steps: list[dict[str, Any]] = []

    try:
        draft = await agent.draft(req.prompt, context=req.context)
    except LLMError as exc:
        raise LLMUnavailableError(str(exc)) from exc
    assert draft.prd is not None
    prd = draft.prd
    steps.append(
        {
            "node": "draft",
            "latency_ms": draft.latency_ms,
            "tokens_in": draft.usage.prompt,
            "tokens_out": draft.usage.completion,
        }
    )

    last_critique = None
    for iteration in range(req.max_revisions + 1):
        try:
            critique_out = await agent.critique(prd)
        except LLMError as exc:
            raise LLMUnavailableError(str(exc)) from exc
        assert critique_out.critique is not None
        last_critique = critique_out.critique
        steps.append(
            {
                "node": "critique",
                "iteration": iteration,
                "score": last_critique.score,
                "should_revise": last_critique.should_revise,
                "latency_ms": critique_out.latency_ms,
                "tokens_in": critique_out.usage.prompt,
                "tokens_out": critique_out.usage.completion,
            }
        )
        if not last_critique.should_revise or iteration == req.max_revisions:
            break
        try:
            revised = await agent.revise(prd, last_critique)
        except LLMError as exc:
            raise LLMUnavailableError(str(exc)) from exc
        assert revised.prd is not None
        prd = revised.prd
        steps.append(
            {
                "node": "revise",
                "iteration": iteration,
                "latency_ms": revised.latency_ms,
                "tokens_in": revised.usage.prompt,
                "tokens_out": revised.usage.completion,
            }
        )

    return {
        "prd": prd.model_dump(mode="json"),
        "markdown": render_prd_markdown(prd),
        "critique": last_critique.model_dump(mode="json") if last_critique else None,
        "steps": steps,
    }
