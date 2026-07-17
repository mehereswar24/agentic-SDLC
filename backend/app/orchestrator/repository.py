"""Async DB access for Run / AgentStep / Artifact.

All orchestrator code goes through this layer — no ad-hoc queries elsewhere.
Each method opens its own session via `session_scope()` so the orchestrator
can write checkpoints atomically without holding open a long-running session.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import selectinload

from app.core.db import session_scope
from app.models import AgentStep, Artifact, ArtifactKind, Run, RunStatus


class RunRepository:
    """Thin persistence facade. Stateless — instantiate freely."""

    async def create_run(
        self, prompt: str, *, meta: dict[str, Any] | None = None
    ) -> Run:
        async with session_scope() as s:
            run = Run(prompt=prompt, status=RunStatus.PENDING, meta=meta or {})
            s.add(run)
            await s.flush()
            await s.refresh(run)
            # Detach from session so callers can read attributes safely.
            s.expunge(run)
            return run

    async def set_status(
        self, run_id: str, status: RunStatus, *, error: str | None = None
    ) -> None:
        async with session_scope() as s:
            stmt = (
                update(Run)
                .where(Run.id == run_id)
                .values(status=status, error=error)
            )
            await s.execute(stmt)

    async def update_meta(self, run_id: str, patch: dict[str, Any]) -> None:
        """Shallow-merge `patch` into Run.meta. Used to track pipeline progress
        and pending-approval state across resumable runs."""
        async with session_scope() as s:
            run = (
                await s.execute(select(Run).where(Run.id == run_id))
            ).scalar_one_or_none()
            if run is None:
                return
            # Reassign (not mutate) so SQLAlchemy marks the JSON column dirty.
            run.meta = {**(run.meta or {}), **patch}

    async def append_step(
        self,
        run_id: str,
        *,
        node: str,
        agent: str | None,
        input: dict[str, Any] | None = None,
        output: dict[str, Any] | None = None,
        error: str | None = None,
        latency_ms: int | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
    ) -> AgentStep:
        async with session_scope() as s:
            step = AgentStep(
                run_id=run_id,
                node=node,
                agent=agent,
                input=input or {},
                output=output or {},
                error=error,
                latency_ms=latency_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )
            s.add(step)
            await s.flush()
            await s.refresh(step)
            s.expunge(step)
            return step

    async def save_artifact(
        self,
        run_id: str,
        *,
        kind: ArtifactKind,
        content: dict[str, Any],
    ) -> Artifact:
        async with session_scope() as s:
            # Find the latest version of this artifact kind for the run.
            existing = await s.execute(
                select(Artifact.version)
                .where(Artifact.run_id == run_id, Artifact.kind == kind)
                .order_by(Artifact.version.desc())
                .limit(1)
            )
            latest = existing.scalar()
            version = (latest or 0) + 1
            art = Artifact(
                run_id=run_id, kind=kind, version=version, content=content
            )
            s.add(art)
            await s.flush()
            await s.refresh(art)
            s.expunge(art)
            return art

    async def get_run(self, run_id: str) -> Run | None:
        async with session_scope() as s:
            stmt = (
                select(Run)
                .where(Run.id == run_id)
                .options(selectinload(Run.steps), selectinload(Run.artifacts))
            )
            run = (await s.execute(stmt)).scalar_one_or_none()
            if run is not None:
                s.expunge(run)
            return run

    async def list_runs(self, *, limit: int = 50, offset: int = 0) -> list[Run]:
        async with session_scope() as s:
            stmt = (
                select(Run)
                .order_by(Run.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = (await s.execute(stmt)).scalars().all()
            for r in rows:
                s.expunge(r)
            return list(rows)

    async def list_artifact_versions(
        self, run_id: str, kind: ArtifactKind
    ) -> list[Artifact]:
        """All versions of one artifact kind, oldest first."""
        async with session_scope() as s:
            stmt = (
                select(Artifact)
                .where(Artifact.run_id == run_id, Artifact.kind == kind)
                .order_by(Artifact.version.asc())
            )
            rows = (await s.execute(stmt)).scalars().all()
            for a in rows:
                s.expunge(a)
            return list(rows)

    async def get_artifact_version(
        self, run_id: str, kind: ArtifactKind, version: int
    ) -> Artifact | None:
        async with session_scope() as s:
            stmt = select(Artifact).where(
                Artifact.run_id == run_id,
                Artifact.kind == kind,
                Artifact.version == version,
            )
            art = (await s.execute(stmt)).scalar_one_or_none()
            if art is not None:
                s.expunge(art)
            return art

    async def latest_artifact(
        self, run_id: str, kind: ArtifactKind
    ) -> Artifact | None:
        async with session_scope() as s:
            stmt = (
                select(Artifact)
                .where(Artifact.run_id == run_id, Artifact.kind == kind)
                .order_by(Artifact.version.desc())
                .limit(1)
            )
            art = (await s.execute(stmt)).scalar_one_or_none()
            if art is not None:
                s.expunge(art)
            return art

    async def delete_run(self, run_id: str) -> bool:
        async with session_scope() as s:
            stmt = select(Run).where(Run.id == run_id)
            run = (await s.execute(stmt)).scalar_one_or_none()
            if run is None:
                return False
            await s.delete(run)
            return True

    async def delete_all_runs(self) -> None:
        async with session_scope() as s:
            # Delete all runs (cascades will clean up steps/artifacts)
            stmt = delete(Run)
            await s.execute(stmt)
