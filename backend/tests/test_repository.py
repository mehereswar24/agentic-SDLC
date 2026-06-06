from __future__ import annotations

import pytest

from app.models import ArtifactKind, RunStatus
from app.orchestrator.repository import RunRepository


@pytest.fixture
async def repo(engine: None) -> RunRepository:
    return RunRepository()


async def test_create_run_and_get(repo: RunRepository) -> None:
    run = await repo.create_run("build a habit tracker")
    assert run.status == RunStatus.PENDING

    fetched = await repo.get_run(run.id)
    assert fetched is not None
    assert fetched.prompt == "build a habit tracker"
    assert fetched.steps == []
    assert fetched.artifacts == []


async def test_set_status_persists(repo: RunRepository) -> None:
    run = await repo.create_run("p")
    await repo.set_status(run.id, RunStatus.RUNNING)
    refreshed = await repo.get_run(run.id)
    assert refreshed is not None
    assert refreshed.status == RunStatus.RUNNING

    await repo.set_status(run.id, RunStatus.FAILED, error="boom")
    failed = await repo.get_run(run.id)
    assert failed is not None
    assert failed.status == RunStatus.FAILED
    assert failed.error == "boom"


async def test_append_step_and_save_artifact_versions(repo: RunRepository) -> None:
    run = await repo.create_run("p")

    s1 = await repo.append_step(
        run.id,
        node="draft",
        agent="planner",
        input={"prompt": "p"},
        output={"prd_title": "X"},
        latency_ms=100,
        tokens_in=50,
        tokens_out=200,
    )
    assert s1.latency_ms == 100

    a1 = await repo.save_artifact(run.id, kind=ArtifactKind.PRD, content={"title": "v1"})
    a2 = await repo.save_artifact(run.id, kind=ArtifactKind.PRD, content={"title": "v2"})
    assert a1.version == 1
    assert a2.version == 2

    latest = await repo.latest_artifact(run.id, ArtifactKind.PRD)
    assert latest is not None
    assert latest.version == 2
    assert latest.content == {"title": "v2"}


async def test_list_runs_orders_newest_first(repo: RunRepository) -> None:
    a = await repo.create_run("first")
    b = await repo.create_run("second")
    c = await repo.create_run("third")

    rows = await repo.list_runs(limit=10)
    assert [r.id for r in rows] == [c.id, b.id, a.id]
