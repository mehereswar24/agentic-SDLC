"""API tests for GET /api/runs/{run_id}/code.zip."""
from __future__ import annotations

import io
import zipfile

from httpx import AsyncClient

from app.models import ArtifactKind
from app.orchestrator.repository import RunRepository

_BUNDLE = {
    "project_name": "Habit Tracker",
    "description": "A tiny habit tracker.",
    "tech_stack": ["Python 3.12", "FastAPI"],
    "files": [
        {"path": "app/main.py", "language": "python", "purpose": "entry", "content": "print('hi')\n"},
        {"path": "requirements.txt", "language": "text", "purpose": "deps", "content": "fastapi\n"},
    ],
    "setup_instructions": "pip install -r requirements.txt\npython app/main.py",
    "next_steps": ["Add tests"],
}


async def test_download_zip_returns_archive_with_files(client: AsyncClient) -> None:
    repo = RunRepository()
    run = await repo.create_run("Build a habit tracker", meta={})
    await repo.save_artifact(run.id, kind=ArtifactKind.CODE, content=_BUNDLE)

    res = await client.get(f"/api/runs/{run.id}/code.zip")
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/zip"
    assert "habit-tracker.zip" in res.headers.get("content-disposition", "")

    zf = zipfile.ZipFile(io.BytesIO(res.content))
    names = set(zf.namelist())
    assert "habit-tracker/app/main.py" in names
    assert "habit-tracker/requirements.txt" in names
    assert "habit-tracker/README.md" in names
    assert zf.read("habit-tracker/app/main.py").decode() == "print('hi')\n"
    # README captures the setup instructions so the user can run it.
    assert "pip install -r requirements.txt" in zf.read("habit-tracker/README.md").decode()


async def test_download_zip_404_when_no_code(client: AsyncClient) -> None:
    run = await RunRepository().create_run("No code yet", meta={})
    res = await client.get(f"/api/runs/{run.id}/code.zip")
    assert res.status_code == 404, res.text
    assert res.json()["error"]["code"] == "not_found"


async def test_download_zip_404_unknown_run(client: AsyncClient) -> None:
    res = await client.get("/api/runs/nope/code.zip")
    assert res.status_code == 404, res.text
