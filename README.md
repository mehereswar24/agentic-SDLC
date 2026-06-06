# Agentic SDLC Orchestrator

Autonomous SDLC agents that turn a short product brief into a structured PRD (and, in later phases, designs, code, and reviews). Built on FastAPI + LangGraph + Google Gemini.

## Status

**Phase 1 — Foundation.** FastAPI skeleton, async SQLAlchemy persistence, Alembic migrations, structured logging, health check, smoke tests.

## Quickstart

```powershell
# 1. Install uv (https://docs.astral.sh/uv/) then sync deps
uv sync --extra dev --extra llm

# 2. Copy env template and set GOOGLE_API_KEY (https://aistudio.google.com/app/apikey)
Copy-Item .env.example .env

# 3. Apply migrations
uv run alembic upgrade head

# 4. Run the API
uv run uvicorn app.main:app --reload --app-dir backend

# 5. Smoke test
curl http://127.0.0.1:8000/health
```

## Tests

```powershell
uv run pytest
```

## Layout

```
backend/app
├── api/            # FastAPI routers (runs, websocket — added later phases)
├── agents/         # BaseAgent + concrete agents (planner — Phase 3)
├── orchestrator/   # LangGraph workflow (Phase 4)
├── llm/            # Gemini client wrapper (Phase 2)
├── tools/          # Agent tools (web search, etc.)
├── core/           # Config, db, logging, errors — shared infrastructure
└── main.py         # FastAPI entry
```
