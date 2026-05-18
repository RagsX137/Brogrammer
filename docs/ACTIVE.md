# ACTIVE WORKING MEMORY – Phase 0: Foundation

> **Agent scope: Phase 0 ONLY.** Do not implement anything listed in MODULES.md Phase 1+.
> Complete tasks in order. When a task is done: mark ✅ here, append to COMPLETED.md.

---

## Phase Goal

Runnable dual-agent text loop (Specialist → Skeptic) with mechanical confidence scoring
and a bare-bones frontend demonstrating gate UX guardrails (diffs, color tags, toggles).

---

## In Scope

- FastAPI project shell + SQLite
- `core/models.py` Pydantic contracts (see ARCHITECTURE.md#core-data-contracts)
- Mechanical confidence formula (see ARCHITECTURE.md#confidence-formula)
- Specialist agent (text-only, no external tools)
- Skeptic agent (text-only, no external tools — tool use is Phase 2)
- SQLite append-only audit log
- Bare-bones React or Vue frontend (gate UI only)

## Out of Scope

ChromaDB · Docker sandbox · Skeptic tool calls (curl/npm) · Git workflow · CI/CD · PostgreSQL

---

## Active Tasks

### P0-001: Project Scaffold
**Status:** TODO
Set up Python 3.11+ project: FastAPI, SQLite, pytest. Directory layout:
```
core/        models.py, confidence.py
agents/      specialist.py, skeptic.py
orchestrator/ audit.py, gates.py
frontend/    (React or Vue)
```

### P0-002: Core Data Models
**Status:** TODO
Implement `core/models.py` with Pydantic v2.
Classes: `Understanding`, `Assumption`, `Unknown`, `MandatoryCategories`, `SkepticCritique`, `ConfidenceProfile`.
Reference: ARCHITECTURE.md → Core Data Contracts.

### P0-003: Confidence Formula
**Status:** TODO
Implement `core/confidence.py`:
- `score = max(0, 1 - open_unknowns / total_unknowns)`
- Cap by `validation_ratio`
- Penalize if any `MandatoryCategory` field has zero items
- `fragility_flag`: 3× Specialist runs at T=0.7, flag if assumption sets diverge
Reference: ARCHITECTURE.md → Confidence Formula.

### P0-004: Dual-Agent Text Loop
**Status:** TODO
Implement `agents/specialist.py` and `agents/skeptic.py`.
Loop: Specialist generates Understanding → Skeptic reads it → returns SkepticCritique.
No external tool calls. Wire into a runnable CLI or FastAPI endpoint.

### P0-005: SQLite Audit Log
**Status:** TODO
Implement `orchestrator/audit.py`: append-only event store.
Events: gate decisions, Skeptic critiques, human resolutions.
Schema must prevent UPDATE/DELETE on critique rows (immutability invariant).

### P0-006: Bare-Bones Frontend Gate UI
**Status:** TODO
React or Vue component (decision needed — see Blockers).
Must show: diff view of Understanding changes, 🔴/🟢 tagged assumptions, resolution toggles for Skeptic critiques.
No prose walls. No implementation of Phase 1+ UI features.

---

## Blockers / Open Questions

- **LLM provider:** OpenAI, Anthropic, or local Ollama? Affects P0-004 LiteLLM config.
- **Frontend framework:** React or Vue? Affects P0-006.

---

## Key Decisions Made

_(Populate this section as gates are passed and decisions are locked.)_
