"""Test fixtures.

Each test gets a fresh in-memory SQLite database. The app's `get_settings`
cache is cleared so DATABASE_URL overrides take effect, and the global engine
is reset between tests to avoid leaking connections.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import db as db_module
from app.core.config import get_settings
from app.core.db import Base, get_sessionmaker, init_engine
from app import models  # noqa: F401 — register models


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[None]:
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ["ENVIRONMENT"] = "test"
    get_settings.cache_clear()

    await db_module.dispose_engine()
    engine = init_engine()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await db_module.dispose_engine()


@pytest_asyncio.fixture
async def session(engine: None) -> AsyncIterator[AsyncSession]:
    sm = get_sessionmaker()
    async with sm() as s:
        yield s


@pytest_asyncio.fixture
async def client(engine: None) -> AsyncIterator[AsyncClient]:
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
