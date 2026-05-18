# Brogrammer — Agent Guide

## Project

Multi-agent system (Specialist → Skeptic → Planner → Builder → QA) with human gate approval. Human-in-the-loop: no agent takes irreversible action without approval at each gate.

## Quick commands

| Action | Command |
|---|---|
| Install backend | `pip install -e ".[dev]"` (from `backend/`) |
| Run backend | `uvicorn backend.main:app --reload` (port 8000) |
| Run frontend | `npm install && npm run dev` (from `frontend/`) |
| Frontend build | `npm run build` (runs `tsc && vite build`) |
| Run all tests | `pytest` (from repo root; config in `pytest.ini`) |
| Run a single test | `pytest tests/test_confidence.py::test_confidence_basic` |
| Run TUI | `brogrammer` CLI entry point (Textual) |

**Always run `pytest` before declaring work done.** No typecheck or lint step exists.

## Package structure

```
├── backend/                     # pip-installable Python package
│   ├── core/models.py           # All Pydantic v2 contracts
│   ├── core/confidence.py       # Mechanical confidence formula
│   ├── agents/                  # Specialist, Skeptic, Planner, Builder, QA
│   ├── orchestrator/gates.py    # FastAPI app factory (create_app()) + all endpoints
│   ├── orchestrator/sandbox.py  # Docker sandbox manager
│   ├── orchestrator/audit.py    # Append-only SQLite event log
│   └── cli/                     # Textual TUI
├── frontend/                    # Vite + React 18 + TypeScript
│   └── src/
│       ├── App.tsx              # 7-step gate flow
│       └── api.ts               # FastAPI client
├── tests/                       # pytest, asyncio_mode=auto
├── docs/                        # ARCHITECTURE.md, MODULES.md, ACTIVE.md, COMPLETED.md
└── pytest.ini                   # sets pythonpath=backend .
```

## Testing conventions

- `asyncio_mode = auto` in `pytest.ini` — async tests need only `@pytest.mark.asyncio`
- `conftest.py` provides `anyio_backend` fixture
- Agent tests use `FakeOllamaClient` (in `test_agents.py`) — never a real LLM. Mock `OllamaClient` at the agent boundary, not `ollama` directly.
- Models have no external deps; test them directly
- `test_sandbox.py` and `test_builder.py` require Docker running

## Key developer notes

- `create_app()` in `gates.py` is a factory with DI for all agents — used by tests and `main.py`
- `FileSpec.path` has a `@field_validator` that rejects path traversal (`..`), absolute paths, and special chars
- `OllamaClient` model defaults to `gemma4:latest` (check `OLLAMA_MODEL` env var — visible in README as `qwen3.6:35b`)
- SQLite DB file is `brogrammer.db` at repo root (gitignored)
- All API endpoints are POST except `/health`, `/api/ready`, and `/api/audit/events` (GET)
- Gate flow order: `/api/run-loop` → `/api/resolve-critique` → `/api/plan` → `/api/build` → `/api/test` → `/api/commit`
- Docker sandbox shared between BuilderAgent and QAAgent
- Specialist does 3× runs at high temp for fragility detection
- `OllamaClient.chat()` passes `format` param for JSON mode — models must support it

## Core invariants (do not violate)

1. Confidence is formula-derived only (never LLM self-reported)
2. All Skeptic critiques are immutable audit events (append-only SQLite)
3. Every gate requires explicit human approval before agents proceed
4. Mandatory categories (accessibility, performance, security, state_management, persistence) must be non-empty or confidence is penalized 50%
5. Skeptic investigates its own doubts with tools before escalating to human
