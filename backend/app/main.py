"""FastAPI application entrypoint.

Wires together config, logging, middleware, error handlers, and routers.
The lifespan context manages engine creation/disposal so connections are
released cleanly on shutdown.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.health import router as health_router
from app.api.llm import router as llm_router
from app.api.planner import router as planner_router
from app.api.runs import router as runs_router
from app.api.stats import router as stats_router
from app.api.ws import router as ws_router
from sqlalchemy import inspect

from app.core.config import get_settings
from app.core.db import dispose_engine, init_engine
from app.core.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.orchestrator.runtime import get_runtime


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    logger = get_logger(__name__)

    engine = init_engine(settings)
    runtime = get_runtime()
    logger.info(
        "app_starting",
        version=__version__,
        env=settings.environment,
        llm_configured=settings.llm_configured,
        database_url=settings.database_url,
    )

    # Verify the schema is present so the user sees a clear error at startup
    # instead of a 500 on the first /api/runs call.
    async with engine.begin() as conn:
        tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    required = {"runs", "agent_steps", "artifacts"}
    missing = required - tables
    if missing:
        logger.error(
            "schema_missing_tables",
            missing=sorted(missing),
            hint="Run: uv run alembic -c backend/alembic.ini upgrade head (from project root)",
        )

    try:
        yield
    finally:
        await runtime.shutdown()
        await dispose_engine()
        logger.info("app_stopped")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Agentic SDLC Orchestrator",
        version=__version__,
        lifespan=lifespan,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(RequestContextMiddleware)

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(health_router)
    app.include_router(llm_router)
    app.include_router(planner_router)
    app.include_router(runs_router)
    app.include_router(stats_router)
    app.include_router(ws_router)

    return app


app = create_app()
