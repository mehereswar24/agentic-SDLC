from __future__ import annotations

from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    res = await client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "version" in body


async def test_ready_reports_db_and_llm(client: AsyncClient) -> None:
    res = await client.get("/ready")
    assert res.status_code == 200
    body = res.json()
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["llm"] in {"configured", "missing_api_key"}


async def test_request_id_round_trips(client: AsyncClient) -> None:
    res = await client.get("/health", headers={"x-request-id": "test-req-123"})
    assert res.headers["x-request-id"] == "test-req-123"


async def test_unknown_route_returns_envelope(client: AsyncClient) -> None:
    res = await client.get("/does-not-exist")
    assert res.status_code == 404
    assert "error" in res.json()
