from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentStep, Artifact, ArtifactKind, Run, RunStatus


async def test_create_run_with_steps_and_artifacts(session: AsyncSession) -> None:
    run = Run(prompt="build a habit tracker")
    session.add(run)
    await session.flush()

    step = AgentStep(
        run_id=run.id,
        node="draft_prd",
        agent="planner",
        input={"prompt": run.prompt},
        output={"draft": {"problem_statement": "..."}},
        latency_ms=420,
    )
    artifact = Artifact(
        run_id=run.id,
        kind=ArtifactKind.PRD,
        version=1,
        content={"problem_statement": "track daily habits"},
    )
    session.add_all([step, artifact])
    await session.commit()

    fetched = (await session.execute(select(Run).where(Run.id == run.id))).scalar_one()
    assert fetched.prompt == "build a habit tracker"
    assert fetched.status == RunStatus.PENDING
    assert len(fetched.steps) == 1
    assert fetched.steps[0].node == "draft_prd"
    assert len(fetched.artifacts) == 1
    assert fetched.artifacts[0].kind == ArtifactKind.PRD


async def test_cascade_delete(session: AsyncSession) -> None:
    run = Run(prompt="p")
    session.add(run)
    await session.flush()
    session.add(Artifact(run_id=run.id, kind=ArtifactKind.PRD, content={}))
    await session.commit()

    await session.delete(run)
    await session.commit()

    artifacts = (await session.execute(select(Artifact))).scalars().all()
    assert artifacts == []
