from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models import ArtifactKind, RunStatus
from app.orchestrator.repository import RunRepository


@pytest.fixture
async def seeded(engine: None) -> None:
    repo = RunRepository()
    r1 = await repo.create_run("alpha")
    await repo.set_status(r1.id, RunStatus.COMPLETED)
    await repo.append_step(
        r1.id, node="draft", agent="planner", latency_ms=1200, tokens_in=50, tokens_out=400
    )
    await repo.append_step(
        r1.id, node="critique", agent="planner", latency_ms=800, tokens_in=420, tokens_out=80
    )
    await repo.save_artifact(r1.id, kind=ArtifactKind.PRD, content={})

    r2 = await repo.create_run("bravo")
    await repo.set_status(r2.id, RunStatus.FAILED, error="x")


async def test_stats_endpoint(client: AsyncClient, seeded: None) -> None:
    res = await client.get("/api/stats")
    assert res.status_code == 200
    body = res.json()
    assert body["total_runs"] == 2
    assert body["by_status"]["completed"] == 1
    assert body["by_status"]["failed"] == 1
    assert body["agent_steps"] == 2
    assert body["tokens_in_total"] == 470
    assert body["tokens_out_total"] == 480
    assert body["avg_step_latency_ms"] == 1000  # (1200+800)/2
