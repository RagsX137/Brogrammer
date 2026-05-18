<p align="center">
  <img src="https://img.shields.io/badge/phase-1%20full%20role%20separation-green?style=for-the-badge" alt="Phase 1" />
  <img src="https://img.shields.io/badge/tests-79%20passing-brightgreen?style=for-the-badge" alt="Tests" />
  <img src="https://img.shields.io/badge/python-3.11+-blue?style=for-the-badge&logo=python" alt="Python" />
  <img src="https://img.shields.io/badge/react-18-61dafb?style=for-the-badge&logo=react" alt="React" />
  <img src="https://img.shields.io/badge/ollama-local%20LLM-000?style=for-the-badge&logo=ollama" alt="Ollama" />
</p>

<h1 align="center">Brogrammer</h1>

<p align="center"><strong>Human-centric AI engineering team.</strong></p>

<p align="center">
  You have the vision. AI agents have the horsepower.<br/>
  Brogrammer makes sure the AI never ships without your sign-off.
</p>

---

## The Problem

AI coding agents are fast — and reckless. They guess silently, hallucinate confidently, and race past decisions that needed your input. By the time you see the output, the damage is already baked in.

## The Idea

Brogrammer flips the dynamic: **you** are the sun, and every agent orbits around your intent.

- **No agent takes an irreversible action without your approval.**
- **Confidence is mechanically derived** — never an LLM's self-reported guess.
- **A dedicated Skeptic agent** actively tries to break the plan *before* a single line of code is written.

The result is a multi-agent system where AI accelerates the mechanical parts of engineering while the human owns the creative and strategic decisions.

---

## How It Works

### The Full Gate Flow

```
  You describe a goal
         │
         ▼
  ┌─────────────┐     ┌─────────────┐
  │ Specialist   │────▶│   Skeptic    │
  │ Builds the   │     │ Tries to    │
  │ Understanding│     │ break it    │
  └──────┬───────┘     └──────┬───────┘
         │                    │
         ▼                    ▼
  ┌──────────────────────────────────┐
  │    Understanding Gate (You)      │
  │  Red/green tags, toggles, diffs  │
  └──────────────────────────────────┘
         │
         ▼
  ┌──────────────┐
  │   Planner    │── Produces TechPlan (JSON + Markdown)
  └──────┬───────┘
         │
         ▼
  ┌──────────────────────────────────┐
  │      Design Gate (You)           │
  │  Approve/retry the TechPlan      │
  └──────────────────────────────────┘
         │
         ▼
  ┌──────────────┐     ┌──────────────────┐
  │   Builder    │────▶│ Docker Sandbox   │
  │              │◀────│ (execute + test) │
  └──────┬───────┘     └──────────────────┘
         │
         ▼
  ┌──────────────┐
  │     QA       │── Runs tests, reports results
  └──────┬───────┘
         │
         ▼
  ┌──────────────────────────────────┐
  │    Prototype Gate (You)          │
  │  Approve → Git commit            │
  └──────────────────────────────────┘
```

1. **Specialist** — Reads your goal, produces a structured `Understanding` document.
2. **Skeptic** — Takes that Understanding and attacks it. Generates failure scenarios, questions, blind spots.
3. **You** — Resolve critique at Understanding Gate.
4. **Planner** — Converts Understanding into a TechPlan with file tree, tech stack, API routes.
5. **You** — Approve the plan at Design Gate.
6. **Builder** — Generates code in a Docker sandbox, logs stream to frontend.
7. **QA** — Runs test suite, reports pass/fail.
8. **You** — Approve at Prototype Gate → Git commit.

### Mechanical Confidence

We don't ask an LLM "how confident are you?" — that's meaningless. Confidence is a **formula**:

```
score = max(0, 1 - open_unknowns / total_unknowns)
```

With guardrails:

| Guardrail | What It Does |
|-----------|-------------|
| **Validation cap** | Score can't exceed the % of assumptions explicitly validated |
| **Ignorance paradox penalty** | If any mandatory category (accessibility, performance, security, state management, persistence) has zero items, score is halved |
| **Fragility flag** | Specialist is run 3× at high temperature; divergent assumption sets trigger a flag and human alert |

### 5-Gate Flow

Every major decision passes through a human gate before agents proceed:

| Gate | Who Presents | What You Approve |
|------|-------------|-----------------|
| **Vision** | Lead | "Is this the right goal?" |
| **Understanding** | Specialist + Skeptic | Domain model + critique + resolutions |
| **Design** | Planner | Technical approach + assumption regression check |
| **Prototype** | Builder + QA | Testable build + test results |
| **Release** | Production | Release candidate → you trigger deploy |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| LLM | Ollama (local — zero API costs) |
| Database | SQLite (append-only audit log) |
| Frontend | React 18, TypeScript, Vite |
| Testing | pytest, pytest-asyncio |

Works with any Ollama-compatible model. Default: `qwen3.6:35b`. Swap via the `OLLAMA_MODEL` env var.

---

## Project Structure

```
brogrammer/
├── backend/
│   ├── core/
│   │   ├── models.py          # Pydantic contracts (Understanding, TechPlan, BuildArtifact, etc.)
│   │   └── confidence.py      # Mechanical confidence formula
│   ├── agents/
│   │   ├── specialist.py      # Generates Understanding from a goal
│   │   ├── skeptic.py         # Generates SkepticCritique from Understanding
│   │   ├── planner.py         # Generates TechPlan from Understanding
│   │   ├── builder.py         # Generates code in Docker sandbox
│   │   └── qa.py              # Test plan generation and test execution
│   └── orchestrator/
│       ├── gates.py           # FastAPI endpoints (all gates)
│       ├── sandbox.py         # Docker container management
│       ├── audit.py           # Append-only SQLite event store
│       └── database.py        # Async SQLite connection
├── frontend/
│   └── src/
│       ├── App.tsx            # Main app shell (7-step gate flow)
│       ├── api.ts             # FastAPI client
│       └── components/
│           ├── UnderstandingView.tsx   # Assumptions + unknowns + mandatory categories
│           ├── CritiquePanel.tsx       # Skeptic scenarios + resolution toggles
│           ├── ConfidenceBadge.tsx     # Color-coded confidence score
│           ├── TechPlanView.tsx        # Planner output display
│           ├── BuildView.tsx           # Streaming build logs
│           └── TestReportView.tsx      # Test results display
├── tests/                     # 79 passing tests
└── docs/
    ├── ARCHITECTURE.md        # System design, agent roles, data contracts
    ├── MODULES.md             # Phase registry + scope fences
    ├── ACTIVE.md              # Current working memory
    └── COMPLETED.md           # Append-only task log
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.ai) running locally with a model pulled (e.g. `ollama pull qwen3.6:35b`)

### Backend

```bash
cd backend
pip install -e ".[dev]"
uvicorn backend.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Run Tests

```bash
pytest
```

---

## Roadmap

| Phase | Name | Status | Focus |
|-------|------|--------|-------|
| 0 | **Foundation** | ✅ Complete | Dual-agent loop, mechanical confidence, audit log, gate UI |
| 1 | **Full Role Separation** | ✅ Complete | Planner, Builder, QA agents; Git workflow; Docker sandbox |
| 2 | **Learning & State-Drift Prevention** | 📋 Planned | Assumption regression checks on commits; Skeptic tool use (curl, npm view, web search) |
| 3 | **Production Hardening** | 📋 Planned | Full CI/CD pipeline, deployment, monitoring |

---

## Core Invariants

1. Confidence is **formula-derived only** — never LLM self-reported
2. All Skeptic critiques are **immutable audit events** (append-only DB)
3. Every gate requires **explicit human approval** before agents proceed
4. Mandatory categories must be non-empty or confidence score is penalized
5. The Skeptic investigates its own doubts with tools **before** escalating to human

---

## License

MIT
