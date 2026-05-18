# Brogrammer Phase 0: Foundation — Design Spec

> Dual-agent loop (Specialist ↔ Skeptic) with mechanical confidence scoring, SQLite audit log, and bare-bones React gate UI. Local Ollama LLM.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM Provider | Local Ollama | Free, offline, no API costs. Adequate for Phase 0 text-only agents. |
| Frontend Framework | React (Vite + TypeScript) | Mature ecosystem, good for interactive gate UI (diffs, toggles, tags). |

## Architecture

```
Frontend (React/Vite)         Backend (FastAPI)
┌───────────────────┐        ┌────────────────────────┐
│  Gate UI          │  HTTP  │  POST /api/run-loop     │
│  - Understanding  │◄──────►│  POST /api/audit        │
│    diff view      │        │  GET  /api/audit/events │
│  - 🔴/🟢 tags     │        └────────┬───────────────┘
│  - Toggles        │                 │
└───────────────────┘        ┌────────▼───────────────┐
                             │  Orchestrator          │
                             │  gates.py             │
                             │  audit.py             │
                             └────────┬───────────────┘
                        ┌──────────────┼───────────────┐
              ┌─────────▼───────┐ ┌────▼───────────┐
              │  Specialist     │ │  Skeptic        │
              │  agents/        │ │  agents/         │
              │  specialist.py  │ │  skeptic.py     │
              └─────────┬───────┘ └────┬───────────┘
                        │              │
              ┌─────────▼──────────────▼───────────┐
              │  Ollama (local)                    │
              │  http://localhost:11434/api/chat    │
              └────────────────────────────────────┘
```

## Directory Layout

```
brogrammer/
├── backend/
│   ├── pyproject.toml
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py         # Pydantic v2 contracts
│   │   └── confidence.py     # Mechanical confidence formula
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── specialist.py     # Generates Understanding
│   │   └── skeptic.py        # Generates SkepticCritique
│   └── orchestrator/
│       ├── __init__.py
│       ├── audit.py          # SQLite append-only event store
│       └── gates.py          # FastAPI endpoints
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── src/
│       ├── App.tsx
│       ├── components/
│       │   ├── UnderstandingView.tsx  # Diff view, 🔴/🟢 tags
│       │   ├── CritiquePanel.tsx      # Skeptic critique + toggles
│       │   └── ConfidenceBadge.tsx    # Score display
│       └── api.ts                    # FastAPI client
└── tests/
    ├── test_confidence.py
    ├── test_models.py
    └── test_loop.py
```

## Core Data Contracts (`core/models.py`)

```python
Assumption          { id: str, statement: str, status: "validated"|"open"|"invalidated", validated_by: str | None }
Unknown             { id: str, question: str, resolution: str | None, resolved_at: datetime | None }
MandatoryCategories { accessibility: list[str], performance: list[str], security: list[str], state_management: list[str], persistence: list[str] }
Understanding       { goal: str, assumptions: list[Assumption], unknowns: list[Unknown], mandatory_categories: MandatoryCategories }
SkepticCritique     { critique_id: str, understanding_id: str, scenarios: list[str], questions: list[str], tool_evidence: list[str] }
ConfidenceProfile   { score: float, open_unknowns: int, total_unknowns: int, validation_ratio: float, fragility_flag: bool }
```

## Confidence Formula (`core/confidence.py`)

1. Base: `score = max(0, 1 - open_unknowns / total_unknowns)` (if total_unknowns > 0, else 0.5)
2. Cap by `validation_ratio` — confidence cannot exceed % of assumptions validated
3. Mandatory category penalty: if any category has 0 items, multiply score by 0.5
4. Fragility flag: run Specialist 3× at T=0.7, check if assumption sets diverge significantly

## Dual-Agent Loop (`orchestrator/gates.py`)

1. FastAPI endpoint `POST /api/run-loop` accepts a goal string
2. Calls `Specialist.generate_understanding(goal)` → returns Understanding
3. (Optional) Runs fragility check — 3 calls at T=0.7
4. Calls `Skeptic.generate_critique(understanding)` → returns SkepticCritique
5. Computes ConfidenceProfile from Understanding + critique
6. Logs all events to SQLite audit table
7. Returns {understanding, critique, confidence_profile, critique_resolved: false}

## Audit Log (`orchestrator/audit.py`)

Append-only SQLite table:

```sql
CREATE TABLE audit_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,       -- 'understanding_generated', 'critique_created', 'human_resolution'
    understanding_id TEXT,
    critique_id TEXT,
    payload JSON NOT NULL,
    created_at TEXT NOT NULL
);
```

- CRITICAL: Application code must never issue UPDATE or DELETE on audit_events
- SQLite PRAGMA foreign_keys = ON

## Frontend Gate UI

Single-page React app with three sections:

1. **Understanding View** — Shows the goal, assumptions list (🟢 validated / 🔴 open color tags), unknowns list, mandatory categories
2. **Critique Panel** — Displays Skeptic scenarios and questions, with toggle/button for each resolution option
3. **Confidence Badge** — Shows mechanical confidence score; red (<70%), yellow (70-89%), green (≥90%)

No walls of text. Information dense, visual, actionable.

## API Contract

```
POST /api/run-loop
  Request:  { "goal": "string" }
  Response: { "understanding": Understanding, "critique": SkepticCritique | null,
              "confidence": ConfidenceProfile, "critique_resolved": bool }

POST /api/resolve-critique
  Request:  { "critique_id": "string", "resolution": "string" }
  Response: { "success": true }

GET /api/audit/events?limit=50
  Response: { "events": AuditEvent[] }
```

## Ollama Integration

- Uses `ollama` Python package
- Communicates with `http://localhost:11434`
- Default model: `llama3.2` (configurable via env var `OLLAMA_MODEL`)
- Specialist prompt: goal → structured Understanding JSON
- Skeptic prompt: Understanding → structured SkepticCritique JSON
- Fragility check: 3× calls with `temperature: 0.7`

## Out of Scope (Phase 0)

- ChromaDB / vector store
- Docker sandbox / terminal
- Skeptic tool calls (curl, npm view, web search)
- Git integration / CI/CD
- PostgreSQL
- Multi-turn conversation

## Phase Completion Criteria

- [ ] End-to-end test: trivial idea → adversarial dual-agent review → brief with ≥90% mechanical confidence
- [ ] Frontend renders diffs, 🔴/🟢 tags, and resolution toggles (no walls of text)
- [ ] All Skeptic critiques stored as immutable audit events in SQLite
