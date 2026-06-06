from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.config import get_settings


@pytest.fixture
def with_api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    key = "test-secret-key-123"
    monkeypatch.setenv("API_KEY", key)
    monkeypatch.setenv("GOOGLE_API_KEY", "fake")
    get_settings.cache_clear()
    return key


async def test_api_open_when_key_unset(client: AsyncClient) -> None:
    res = await client.get("/api/runs")
    assert res.status_code == 200


async def test_api_rejects_when_key_missing(
    client: AsyncClient, with_api_key: str
) -> None:
    res = await client.get("/api/runs")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"


async def test_api_rejects_wrong_scheme(
    client: AsyncClient, with_api_key: str
) -> None:
    res = await client.get(
        "/api/runs", headers={"authorization": f"Basic {with_api_key}"}
    )
    assert res.status_code == 401


async def test_api_rejects_wrong_key(
    client: AsyncClient, with_api_key: str
) -> None:
    res = await client.get(
        "/api/runs", headers={"authorization": "Bearer nope"}
    )
    assert res.status_code == 401


async def test_api_accepts_correct_key(
    client: AsyncClient, with_api_key: str
) -> None:
    res = await client.get(
        "/api/runs", headers={"authorization": f"Bearer {with_api_key}"}
    )
    assert res.status_code == 200


async def test_health_and_ready_remain_public(
    client: AsyncClient, with_api_key: str
) -> None:
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/ready")).status_code == 200
