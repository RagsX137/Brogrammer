# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

A parallel `AGENTS.md` exists with overlapping guidance; keep the two in sync when changing developer-facing facts.

## What this is

Brogrammer is a human-in-the-loop multi-agent engineering system. Five agents run in sequence — **Specialist → Skeptic → Planner → Builder → QA** — and no agent takes an irreversible action without explicit human approval at a gate. The backend is a FastAPI app driving Ollama (local LLM); the frontend is a React/Vite gate UI; a Textual TUI is an alternate frontend.

## Commands

Run from `backend/` unless noted.

| Action | Command |
|---|---|
| Install backend | `pip install -e ".[dev]"` |
| Run backend | `uvicorn backend.main:app --reload` (port 8000) |
| Run frontend | `npm install && npm run dev` (from `frontend/`) |
| Frontend build | `npm run build` (runs `tsc && vite build`, from `frontend/`) |
| Run all tests | `pytest` (from **repo root** — `pytest.ini` sets `pythonpath = backend .`) |
| Run one test | `pytest tests/test_confidence.py::test_confidence_basic` |
| Run TUI | `brogrammer` (console script → `backend:main`, Textual) |

- **`pytest` is the only verification step — there is no lint or typecheck.** Run it before declaring work done.
- `real_llm`-marked tests are skipped unless `RUN_REAL_LLM=1`; `slow` marks >30s tests. Async tests need only `@pytest.mark.asyncio` (`asyncio_mode = auto`).
- Config comes from env / `.env` (see `.env.example`), loaded via `backend/core/config.py`. Note the model default differs between `.env.example`/code (`gemma4:latest`) and README (`qwen3.6:35b`) — the env var `OLLAMA_MODEL` is authoritative.

## Architecture

The pipeline is a linear gate flow, each step gated by a POST endpoint in `backend/orchestrator/gates.py`:

```
/api/run-loop → /api/resolve-critique → /api/plan → /api/build → /api/test → /api/commit
```

`/api/run-loop` runs Specialist **and** Skeptic together. GET-only endpoints: `/health`, `/api/ready`, `/api/audit/events`, `/api/critique/{id}/tools`. Everything else is POST.

**Key structural facts that require reading multiple files to see:**

- **`create_app(db_path, ...)` in `gates.py` is a factory with dependency injection for every agent.** Tests construct their own app with fake agents; `main.py` uses the defaults. Do not instantiate agents at module scope — inject them.
- **`OllamaClient` lives in `backend/agents/specialist.py`** and is imported by planner/skeptic/builder/qa. It is the single LLM boundary. `OllamaClient.chat()` passes a `format` param for JSON mode — models must support it. **Mock at the `OllamaClient` boundary (see `FakeOllamaClient` in `test_agents.py`), never mock `ollama` directly.**
- **`backend/core/models.py`** holds all Pydantic v2 contracts (`Understanding`, `SkepticCritique`, `TechPlan`, `BuildArtifact`, `FileSpec`, etc.) — the data flowing between every stage. Models have no external deps and are tested directly.
- **`FileSpec.path` has a `@field_validator`** rejecting `..`, absolute paths, and special chars — this is the security boundary for what the Builder is allowed to write.
- **`backend/orchestrator/sandbox.py`** manages a Docker container **shared between Builder and QA**. Tests touching it (`test_sandbox.py`, `test_builder.py`) require Docker running.
- **`backend/orchestrator/audit.py` + `database.py`** are an append-only async SQLite event store (`brogrammer.db` at repo root, gitignored). Critiques are written as immutable audit events.
- **`backend/core/confidence.py`** computes confidence mechanically — see invariants below.

`docs/` (`ARCHITECTURE.md`, `MODULES.md`, `ACTIVE.md`, `COMPLETED.md`) tracks system design and working memory.

## Core invariants — do not violate

1. **Confidence is formula-derived only**, never LLM self-reported: `score = max(0, 1 - open_unknowns / total_unknowns)`, capped by the fraction of validated assumptions.
2. **All Skeptic critiques are immutable append-only audit events.**
3. **Every gate requires explicit human approval** before the next agent proceeds.
4. **Mandatory categories** (accessibility, performance, security, state_management, persistence) must be non-empty or confidence is penalized 50%.
5. The **Specialist runs 3× at high temperature** for fragility detection (divergent assumption sets raise a flag).
6. The **Skeptic investigates its own doubts with tools** before escalating to a human.
