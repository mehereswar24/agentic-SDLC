"""Conversational Q&A about a single run.

POST /api/runs/{run_id}/chat — let a user ask about a run's details, progress,
artifacts (PRD / system design / code), and errors. Answers are *grounded* in
the run's persisted state (status, steps, artifacts) so the model reports what
actually happened rather than hallucinating. One-shot calls via the Gemini
client; prior turns are replayed from `history` so follow-ups have context.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from app.core.auth import require_api_key
from app.core.config import Settings, get_settings
from app.core.errors import LLMUnavailableError, NotFoundError
from app.llm.client import get_llm_client
from app.llm.errors import LLMError
from app.models import Run
from app.orchestrator.repository import RunRepository
from app.schemas.api import ChatMessage, ChatRequest, ChatResponse

router = APIRouter(
    prefix="/api/runs",
    tags=["chat"],
    dependencies=[Depends(require_api_key)],
)

_SYSTEM_PROMPT = (
    "You are a helpful assistant embedded in the Agentic SDLC Orchestrator. "
    "A user is viewing a single workflow run and wants to understand its "
    "details, progress, artifacts (PRD, system design, code), and any errors. "
    "Answer ONLY from the RUN CONTEXT provided in the user message. Be concise "
    "and concrete — reference stages, statuses, critique scores, and artifact "
    "contents when they are relevant. If a stage has not run yet or the answer "
    "is not in the context, say so plainly instead of guessing. Format replies "
    "as short plain-text paragraphs or bullet points (no markdown headers)."
)

# Bounds so a long run can't blow past the model's context window.
_MAX_STEPS = 40
_MAX_ARTIFACT_CHARS = 2000
_MAX_HISTORY = 12


def _repo() -> RunRepository:
    return RunRepository()


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "… (truncated)"


def _build_run_context(run: Run) -> str:
    """Render the run's persisted state as a compact, model-readable briefing."""
    lines: list[str] = ["=== RUN OVERVIEW ==="]
    lines.append(f"Run ID: {run.id}")
    lines.append(f"Product brief: {run.prompt}")
    lines.append(f"Status: {run.status.value}")
    if run.error:
        lines.append(f"Error: {_truncate(run.error, 500)}")
    lines.append(f"Created: {run.created_at.isoformat()}")
    lines.append(f"Last updated: {run.updated_at.isoformat()}")
    if run.meta:
        lines.append(f"Settings/progress: {json.dumps(run.meta, default=str)}")

    lines.append("")
    lines.append(f"=== EXECUTION TRACE ({len(run.steps)} step(s)) ===")
    if not run.steps:
        lines.append("No agent steps have run yet.")
    else:
        steps = run.steps[-_MAX_STEPS:]
        if len(run.steps) > _MAX_STEPS:
            lines.append(
                f"(showing the most recent {_MAX_STEPS} of {len(run.steps)} steps)"
            )
        for i, s in enumerate(steps, 1):
            detail = f"{i}. node={s.node}"
            if s.agent:
                detail += f" agent={s.agent}"
            detail += f" status={'error' if s.error else 'ok'}"
            if s.latency_ms is not None:
                detail += f" latency_ms={s.latency_ms}"
            if s.tokens_in or s.tokens_out:
                detail += f" tokens={s.tokens_in or 0}in/{s.tokens_out or 0}out"
            lines.append(detail)
            if s.error:
                lines.append(f"   error: {_truncate(s.error, 300)}")
            critique = (s.output or {}).get("critique")
            if isinstance(critique, dict):
                lines.append(
                    f"   critique: score={critique.get('score')} "
                    f"summary={_truncate(str(critique.get('summary', '')), 200)}"
                )

    lines.append("")
    lines.append(f"=== ARTIFACTS ({len(run.artifacts)}) ===")
    if not run.artifacts:
        lines.append("No artifacts produced yet.")
    else:
        for a in run.artifacts:
            content = json.dumps(a.content, default=str, ensure_ascii=False)
            lines.append(f"- {a.kind.value} (v{a.version}):")
            lines.append(_truncate(content, _MAX_ARTIFACT_CHARS))

    return "\n".join(lines)


def _format_history(history: list[ChatMessage]) -> str:
    if not history:
        return ""
    lines = ["=== CONVERSATION SO FAR ==="]
    for m in history[-_MAX_HISTORY:]:
        who = "User" if m.role == "user" else "Assistant"
        lines.append(f"{who}: {m.text}")
    return "\n".join(lines) + "\n\n"


@router.post("/{run_id}/chat", response_model=ChatResponse)
async def chat_about_run(
    run_id: str,
    req: ChatRequest,
    repo: RunRepository = Depends(_repo),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    """Answer a user question about a specific run, grounded in its state."""
    run = await repo.get_run(run_id)
    if run is None:
        raise NotFoundError(f"Run '{run_id}' not found")
    if not settings.llm_configured:
        raise LLMUnavailableError(
            "GOOGLE_API_KEY is not configured — chat is unavailable."
        )

    prompt = (
        f"{_build_run_context(run)}\n\n"
        f"{_format_history(req.history)}"
        f"User question: {req.message}"
    )

    client = get_llm_client()
    try:
        result = await client.chat(
            prompt,
            system=_SYSTEM_PROMPT,
            temperature=0.3,
            max_output_tokens=1024,
        )
    except LLMError as exc:
        raise LLMUnavailableError(str(exc)) from exc

    return ChatResponse(message=result.text.strip())
