# Brogrammer – Module & Phase Registry

> Agent: Read this first to orient yourself. Then load ACTIVE.md for your actual task scope.
> Only one phase is ACTIVE at a time. Do not implement deliverables from future phases.

---

## Phase Registry

| Phase | Name | Status | Key Deliverables |
|---|---|---|---|
| 0 | Foundation | ✅ COMPLETE | Dual-agent loop (Specialist↔Skeptic), mechanical confidence scoring, SQLite audit log, bare-bones gate UI |
| 1 | Full Role Separation | ✅ COMPLETE | Planner, Builder, QA agents; Git workflow integration; Docker sandbox terminal |
| 2 | Learning & State-Drift Prevention | ⬜ PLANNED | Assumption regression checks on commits, Skeptic tool access (curl, npm view, web search) |
| 3 | Production Hardening | ⬜ PLANNED | Full CI/CD pipeline, app store configuration, performance monitoring |

---

## Scope Fences (What NOT to Build in Each Phase)

| Phase | Explicitly Out of Scope |
|---|---|
| 0 | ChromaDB, Docker sandbox, Skeptic tool calls, Git integration, CI/CD, PostgreSQL |
| 1 | Assumption regression checks, Skeptic tool use, CI/CD, store deployment |
| 2 | CI/CD, production deployment, store configuration |
| 3 | All prior phases must be complete first |

---

## Phase Completion Criteria

**Phase 0 done when:**
- End-to-end test: trivial app idea → adversarial dual-agent review → brief with ≥90% mechanical confidence score
- Frontend renders diffs, 🔴/🟢 tags, and resolution toggles (no walls of text)
- All Skeptic critiques stored as immutable audit events in SQLite

**Phase 1 done when:** All five gate types functional with Planner, Builder, QA in the loop; Git commit triggers state check.

**Phase 2 done when:** Assumption regression check runs on every major commit; Skeptic uses real tools.

**Phase 3 done when:** Release Gate produces a deployable artifact via CI/CD.

---

## Document Pipeline

```
ARCHITECTURE.md  ←  stable system design; update rarely (contracts, invariants)
MODULES.md       ←  this file; update only phase Status column
ACTIVE.md        ←  current phase working memory; update frequently
COMPLETED.md     ←  append-only task log; never delete rows
```

## Agent Protocol

1. **Load MODULES.md** → confirm active phase and its scope fence
2. **Load ACTIVE.md** → read tasks, context, and blockers
3. **Load ARCHITECTURE.md** → only if you need contract or system design details
4. When a task is done: mark it complete in ACTIVE.md, append row to COMPLETED.md
5. When a phase is done: update Status in this file, reset ACTIVE.md for next phase
