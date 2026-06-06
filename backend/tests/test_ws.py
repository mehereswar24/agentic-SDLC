"""WebSocket tests for /ws/runs/{run_id}.

Uses `httpx_ws.aconnect_ws` with `ASGIWebSocketTransport` so the test client
talks to the in-process FastAPI app without spinning up a real server.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from app.agents.planner import PlannerOutput
from app.core.config import get_settings
from app.llm.types import TokenUsage
from app.orchestrator import runtime as runtime_module
from app.orchestrator.events import _reset_event_bus, get_event_bus
from app.orchestrator.repository import RunRepository
from app.orchestrator.runner import Orchestrator
from app.orchestrator.runtime import OrchestratorRuntime
from tests.fixtures import make_critique, make_prd


class _GatedPlanner:
    """Planner that pauses inside `draft` until released — gives the test
    deterministic control over when the run starts emitting events."""

    name = "planner"

    def __init__(self, release: asyncio.Event) -> None:
        self._release = release

    async def draft(self, prompt: str, *, context: str | None = None) -> PlannerOutput:
        await self._release.wait()
        return PlannerOutput(
            prd=make_prd(),
            critique=None,
            usage=TokenUsage(prompt=10, completion=50, total=60),
            latency_ms=10,
            model="stub",
            finish_reason="STOP",
        )

    async def critique(self, prd: Any) -> PlannerOutput:
        return PlannerOutput(
            prd=None,
            critique=make_critique(should_revise=False),
            usage=TokenUsage(prompt=5, completion=30, total=35),
            latency_ms=10,
            model="stub",
            finish_reason="STOP",
        )

    async def revise(self, prd: Any, critique: Any) -> PlannerOutput:  # pragma: no cover
        raise AssertionError("revise should not run in this test")


@pytest_asyncio.fixture
async def configured_runtime(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    get_settings.cache_clear()
    _reset_event_bus()

    release = asyncio.Event()
    bus = get_event_bus()

    def factory() -> Orchestrator:
        return Orchestrator(
            repo=RunRepository(),
            bus=bus,
            agent_factory=lambda: _GatedPlanner(release),  # type: ignore[arg-type]
        )

    runtime = OrchestratorRuntime(orchestrator_factory=factory)
    runtime_module.set_runtime(runtime)
    try:
        yield {"runtime": runtime, "release": release}
    finally:
        # Release the gate first so any orchestrator-in-flight finishes its
        # current step rather than getting cancelled mid-DB-write.
        release.set()
        await runtime.shutdown(timeout=5.0)
        runtime_module._reset_runtime()


async def _ws_url(client: AsyncClient, path: str) -> str:
    return f"{client.base_url}{path}".replace("http://", "ws://").replace(
        "https://", "wss://"
    )


async def _make_ws_client() -> AsyncClient:
    from app.main import create_app

    app = create_app()
    return AsyncClient(transport=ASGIWebSocketTransport(app), base_url="http://test")


async def _collect_until_close(ws: Any, max_messages: int = 50) -> list[dict[str, Any]]:
    """Receive messages until the server closes the socket."""
    from httpx_ws import WebSocketDisconnect

    received: list[dict[str, Any]] = []
    try:
        for _ in range(max_messages):
            msg = await asyncio.wait_for(ws.receive_json(), timeout=3.0)
            received.append(msg)
    except WebSocketDisconnect:
        pass
    return received


async def test_ws_unknown_run_closes_with_1008(
    configured_runtime: dict[str, Any], engine: None
) -> None:
    from httpx_ws import WebSocketDisconnect

    async with await _make_ws_client() as client:
        url = await _ws_url(client, "/ws/runs/does-not-exist")
        disconnect: WebSocketDisconnect | None = None
        async with aconnect_ws(url, client) as ws:
            try:
                await ws.receive_json()
                pytest.fail("expected server to close the connection")
            except WebSocketDisconnect as exc:
                disconnect = exc
        assert disconnect is not None
        assert disconnect.code == 1008


async def test_ws_terminal_run_sends_snapshot_then_closes(
    configured_runtime: dict[str, Any], engine: None
) -> None:
    from httpx_ws import WebSocketDisconnect

    repo = RunRepository()
    # Create + complete a run by spawning then releasing immediately.
    run = await repo.create_run("habit tracker")
    configured_runtime["release"].set()
    configured_runtime["runtime"].spawn(run.id)
    await configured_runtime["runtime"].wait_for(run.id, timeout=5.0)

    async with await _make_ws_client() as client:
        url = await _ws_url(client, f"/ws/runs/{run.id}")
        snapshot: dict[str, Any] | None = None
        disconnect: WebSocketDisconnect | None = None
        async with aconnect_ws(url, client) as ws:
            snapshot = await asyncio.wait_for(ws.receive_json(), timeout=3.0)
            try:
                await ws.receive_json()
                pytest.fail("expected server to close the connection")
            except WebSocketDisconnect as exc:
                disconnect = exc
        assert snapshot is not None
        assert snapshot["type"] == "snapshot"
        assert snapshot["run"]["status"] == "completed"
        # Steps and artifacts came through
        assert [s["node"] for s in snapshot["run"]["steps"]] == ["draft", "critique"]
        assert disconnect is not None
        assert disconnect.code == 1000


async def test_ws_streams_events_for_active_run(
    configured_runtime: dict[str, Any], engine: None
) -> None:
    from httpx_ws import WebSocketDisconnect

    repo = RunRepository()
    run = await repo.create_run("habit tracker")
    # Spawn but DO NOT release yet — orchestrator is blocked in `draft`.
    configured_runtime["runtime"].spawn(run.id)

    async with await _make_ws_client() as client:
        url = await _ws_url(client, f"/ws/runs/{run.id}")
        messages: list[dict[str, Any]] = []

        async with aconnect_ws(url, client) as ws:
            # 1. Snapshot first — run is still pending/running.
            snapshot = await asyncio.wait_for(ws.receive_json(), timeout=3.0)
            assert snapshot["type"] == "snapshot"
            assert snapshot["run"]["status"] in {"pending", "running"}

            # 2. Release the planner — events should start flowing.
            configured_runtime["release"].set()

            # 3. Drain until run completes.
            try:
                for _ in range(30):
                    msg = await asyncio.wait_for(ws.receive_json(), timeout=3.0)
                    messages.append(msg)
            except WebSocketDisconnect:
                pass

        event_types = [m["data"]["type"] for m in messages if m["type"] == "event"]
        assert "run.started" in event_types or event_types[0].startswith("step")
        assert "step.completed" in event_types
        assert "artifact.created" in event_types
        assert event_types[-1] == "run.completed"


async def test_ws_ping_pong(
    configured_runtime: dict[str, Any], engine: None
) -> None:
    repo = RunRepository()
    run = await repo.create_run("habit tracker")
    configured_runtime["runtime"].spawn(run.id)

    async with await _make_ws_client() as client:
        url = await _ws_url(client, f"/ws/runs/{run.id}")
        async with aconnect_ws(url, client) as ws:
            await asyncio.wait_for(ws.receive_json(), timeout=3.0)  # snapshot
            await ws.send_json({"type": "ping"})
            # Pong should come back before any event (planner is gated).
            reply = await asyncio.wait_for(ws.receive_json(), timeout=2.0)
            assert reply == {"type": "pong"}
            # Release so the orchestrator finishes cleanly.
            configured_runtime["release"].set()
