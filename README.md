# Agentic SDLC Orchestrator

An autonomous multi-agent orchestrator that turns a simple product brief into a structured PRD, sprint plan, and test suite. Built on **FastAPI**, **LangGraph**, and **Google Gemini**, with a stunning, modern **React + Vite** dashboard.

## 🚀 Features

- **Multi-Agent Architecture**: Uses LangGraph to orchestrate specialized agents (Product Manager, Sprint Planner, and Tester) working together.
- **Sleek, Premium UI**: A highly responsive, glassmorphic dashboard built with Tailwind CSS, supporting seamless Dark & Light modes.
- **Real-Time Streaming**: Watch agents think and communicate in real-time through Server-Sent Events (SSE).
- **Persistent Runs**: Every run is saved to a SQLite database using SQLAlchemy and Alembic migrations.
- **Human-in-the-Loop**: Supports pausing runs for human review and auto-approve toggles.

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, LangGraph, SQLAlchemy, Alembic
- **LLM**: Google Gemini (Native API Integration)
- **Frontend**: React, Vite, Tailwind CSS, TanStack Router & Query
- **Styling**: Glassmorphism, CSS Transitions, `lucide-react` icons

## ⚡ Quickstart

### 1. Start the Backend

```powershell
# Install dependencies using uv
uv sync --extra dev --extra llm

# Set up your environment (Requires a Google Gemini API Key)
Copy-Item .env.example .env

# Apply database migrations
uv run alembic upgrade head

# Run the FastAPI server
uv run uvicorn app.main:app --reload --app-dir backend
```

### 2. Start the Frontend Dashboard

Open a new terminal window:

```powershell
cd frontend

# Install Node dependencies
npm install

# Run the Vite dev server
npm run dev
```

Your orchestrator dashboard will be running at `http://localhost:5173`.

## 📂 Project Structure

```text
agentic-sdlc/
├── backend/
│   ├── app/
│   │   ├── agents/         # PM, Sprint Planner, Tester logic
│   │   ├── api/            # REST and SSE endpoints
│   │   ├── orchestrator/   # LangGraph StateGraph definitions
│   │   ├── llm/            # Gemini client wrapper
│   │   └── models.py       # SQLAlchemy ORM models
│   └── tests/
└── frontend/
    ├── src/
    │   ├── components/     # UI components (Kanban, Sidebar, Chat)
    │   ├── routes/         # TanStack file-based routing
    │   ├── lib/            # API client (api.ts) & utils
    │   └── index.css       # Tailwind entry and theme variables
    └── public/             # SVGs and static assets
```
