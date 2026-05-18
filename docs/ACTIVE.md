# ACTIVE WORKING MEMORY – Phase 0: Foundation

> **Phase 0 is COMPLETE.** See MODULES.md for next phase status.

---

## Phase Goal

Runnable dual-agent text loop (Specialist → Skeptic) with mechanical confidence scoring
and a bare-bones frontend demonstrating gate UX guardrails (diffs, color tags, toggles).

---

## Deliverables Complete

- [x] FastAPI project shell + SQLite (`backend/`)
- [x] `core/models.py` Pydantic v2 contracts
- [x] `core/confidence.py` mechanical confidence formula (ignorance paradox, fragility flag)
- [x] `agents/specialist.py` Specialist agent (Ollama)
- [x] `agents/skeptic.py` Skeptic agent (Ollama)
- [x] `orchestrator/database.py` + `audit.py` SQLite append-only audit log
- [x] `orchestrator/gates.py` FastAPI endpoints (`/api/run-loop`, `/api/resolve-critique`, `/api/audit/events`)
- [x] `backend/main.py` entry point
- [x] React (Vite + TypeScript) frontend with UnderstandingView, CritiquePanel, ConfidenceBadge
- [x] 29 passing tests (pytest) + TypeScript clean compilation

## Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM Provider | Local Ollama | Free, offline, no API costs |
| Frontend Framework | React (Vite + TypeScript) | Mature ecosystem, good for interactive gate UI |
| LLM Integration | Direct `ollama` Python package | No LiteLLM overhead for Phase 0 |
| DB Pattern | Lazy init in closure | Avoids lifespan issues with ASGI test transport |
