"""Health & readiness endpoints.

`/health` is a liveness probe — answers fast, never touches the DB.
`/ready` is a readiness probe — verifies DB connectivity and LLM key presence.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.core.config import Settings, get_settings
from app.core.db import get_session

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict[str, Any]:
    return {"status": "ok", "version": __version__}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def ready(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    checks: dict[str, str] = {}

    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc.__class__.__name__}"

    checks["llm"] = "configured" if settings.llm_configured else "missing_api_key"

    overall = "ok" if checks["database"] == "ok" else "degraded"
    return {"status": overall, "version": __version__, "checks": checks}
