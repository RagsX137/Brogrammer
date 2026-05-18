# Brogrammer – System Architecture

> Human-centric AI engineering team. Human = final authority and source of intent.
> Agents augment only. No agent takes irreversible action without human gate approval.

---

## System Diagram

```
┌──────────────────────────────────────────────┐
│              Human Interface                 │
│  (Chat, Dashboard, Diffs, Toggles)           │
└──────────┬───────────────────────┬───────────┘
           │                       │
┌──────────▼──────────┐  ┌────────▼────────────┐
│  Orchestration Layer │  │  Shared Memory & DB  │
│  State Machine,      │  │  SQLite → PostgreSQL │
│  Task Queue,         │  │  ChromaDB (vectors)  │
│  Audit Log           │  │  Git (file history)  │
└──────────┬──────────┘  └────────▲────────────┘
           │                       │
┌──────────▼───────────────────────▼───────────┐
│           Agent Runtime (Multi-Agent)         │
│  Lead  Specialist  Skeptic  Engineer  QA  Prod│
└──────────────────────┬────────────────────────┘
                       │
┌──────────────────────▼────────────────────────┐
│          LLM Backend (Pluggable via LiteLLM)  │
│  Cloud: Anthropic, OpenAI  |  Local: Ollama   │
└───────────────────────────────────────────────┘
```

---

## Agent Roles

| Agent | Responsibility | Inputs | Outputs | Tools |
|---|---|---|---|---|
| Lead | Orchestrate, roadmap, gate management | Requirements | Roadmap, gate status | — |
| Specialist | Domain modelling, Understanding doc | Requirements | Understanding | RAG, arch diagrams |
| Skeptic | Adversarial review, surface failure scenarios | Understanding | SkepticCritique | curl, npm view, web search (read-only sandbox) |
| Planner | Technical plan, design tokens, mockups | Understanding | Tech plan | — |
| Builder | Write/run/iterate code | Tech plan | Working prototype | File I/O, compiler, Git |
| QA | Test plan, run tests, validate acceptance | Build artifacts | Test results | Test runner |
| Production | CI/CD, store config, monitoring | Release candidate | Deployed build | Docker, CI tools |

---

## Gate Flow (Human-in-the-Loop)

Gates are sequential. Each requires explicit human approval before the next phase begins.

1. **Vision Gate** – Lead presents parsed requirements → human confirms goal is correct
2. **Understanding Gate** – Specialist presents Understanding doc; Skeptic delivers critique via actionable toggles → human resolves conflicts
3. **Design Gate** – Planner/Designer present tech approach; assumption regression check runs automatically
4. **Prototype Gate** – Builder delivers testable build; QA presents test results
5. **Release Gate** – Production presents release candidate → human triggers deploy

---

## Core Data Contracts (`core/models.py`)

```python
Understanding       { goal, assumptions: Assumption[], unknowns: Unknown[], mandatory_categories: MandatoryCategories }
Assumption          { id, statement, status: "validated"|"open"|"invalidated", validated_by }
Unknown             { id, question, resolution, resolved_at }
MandatoryCategories { accessibility, performance, security, state_management, persistence }
SkepticCritique     { critique_id, understanding_id, scenarios[], questions[], tool_evidence[] }
ConfidenceProfile   { score, open_unknowns, total_unknowns, validation_ratio, fragility_flag }

### Phase 1 Contracts

TechPlan             { plan_id, understanding_id, tech_stack, file_tree, components, api_routes, markdown_summary }
FileSpec             { path, purpose, content_type }
ComponentSpec        { name, responsibility, depends_on }
APIRoute             { method, path, description }
BuildArtifact        { build_id, plan_id, files_created, files_modified, docker_logs, status }
TestPlan             { plan_id, build_id, framework, test_files, acceptance_criteria }
TestResult           { test_name, status, error_message }
TestReport           { report_id, build_id, passed, failed, skipped, coverage_pct, details }
```

---

## Confidence Formula (`core/confidence.py`)

```
score = max(0, 1 - (open_unknowns / total_unknowns_identified_at_start))
```

**Penalties and caps:**
- Score **capped** by `validation_ratio` (% of assumptions explicitly validated/tested)
- Score **heavily penalized** if any `MandatoryCategory` field has zero assumptions/unknowns listed
- `fragility_flag = True` if 3× Specialist runs at T=0.7 produce divergent assumption sets

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Backend | Python 3.11+, FastAPI | API layer |
| Agent Framework | LangChain / LlamaIndex / Custom | TBD at Phase 1 |
| Relational DB | SQLite (Phase 0) → PostgreSQL | Audit log, state |
| Vector Store | ChromaDB | Phase 1+ |
| Execution Env | Docker (sandboxed terminal) | Phase 1+ |
| LLM Routing | LiteLLM | Routes to Anthropic, OpenAI, Ollama |
| Frontend | React or Vue | Gate UI: diffs, toggles, color tags |

---

## Key Invariants (Do Not Violate)

1. Confidence is **formula-derived only** — never LLM self-reported
2. All Skeptic critiques are **immutable audit events** (append-only DB)
3. Every gate requires **explicit human approval** before agents proceed
4. Mandatory categories must be non-empty or confidence score is penalized
5. The Skeptic investigates its own doubts with tools **before** escalating to human
