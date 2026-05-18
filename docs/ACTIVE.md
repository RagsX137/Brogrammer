# ACTIVE WORKING MEMORY – Phase 1: Full Role Separation

> **Phase 1 is COMPLETE.** See MODULES.md for next phase status.

---

## Phase Goal

Extend Phase 0's dual-agent loop (Specialist ↔ Skeptic) with Planner, Builder, and QA agents,
Docker sandbox terminal, Git commit workflow, and multi-step gate flow in the frontend.

---

## Deliverables Complete

- [x] Docker SandboxManager (`backend/orchestrator/sandbox.py`)
- [x] PlannerAgent (`backend/agents/planner.py`)
- [x] BuilderAgent (`backend/agents/builder.py`)
- [x] QAAgent (`backend/agents/qa.py`)
- [x] Phase 1 data contracts (TechPlan, BuildArtifact, TestPlan, TestReport)
- [x] Phase 1 DB tables (tech_plans, build_artifacts, test_reports)
- [x] Full Understanding stored in audit payload for planner reconstruction
- [x] API endpoints: `/api/plan`, `/api/build`, `/api/test`, `/api/commit`
- [x] Frontend: TechPlanView, BuildView, TestReportView components
- [x] Frontend: 7-step gate flow (goal → understanding → design → build → test → commit → done)
- [x] 79 passing tests (pytest) + TypeScript clean compilation

---

## Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Orchestration pattern | Direct agent calls (same as Phase 0) | Keep it simple, same code style |
| Builder execution | Headless docker-py exec + streaming logs | Transparent: human sees all commands/output |
| Planner output | Structured JSON + markdown | Both machines and humans can consume it |
| QA strategy | Test plans from spec + execution after build | Human approves test plan at gate, sees results at next gate |
| Git commits | Automatic on prototype gate approval | Agent-authored messages, human reviews before push |
