# Brogrammer Phase 1: Full Role Separation — Design Spec

> Extends Phase 0's dual-agent loop (Specialist ↔ Skeptic) with Planner, Builder, and QA agents,
> a Docker sandbox terminal, and Git commit workflow. Each new gate requires explicit human approval.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Orchestration pattern | Direct agent calls (same as Phase 0) | Keep it simple, same code style, no extra infra |
| Builder execution | Headless `docker-py` exec + streaming logs | Transparent: human sees all commands/output, can `docker exec` manually |
| Planner output | Structured JSON (for Builder) + markdown (for human gate review) | Both consumers get what they need |
| QA strategy | Test plans from spec + execution after build | Human approves test plan at gate, sees results at next gate |
| Git commits | Automatic on prototype gate approval | Agent-authored messages, human reviews before push |

## Architecture

```
Human Goal
    │
    ▼
┌─────────────┐     ┌─────────────┐
│ Specialist   │────▶│   Skeptic    │
│ (Phase 0)    │     │ (Phase 0)    │
└──────┬───────┘     └──────┬───────┘
       │                    │
       ▼                    ▼
  Understanding Gate (Human approves)
       │
       ▼
┌──────────────┐
│   Planner    │── Produces TechPlan (JSON + Markdown)
└──────┬───────┘
       │
       ▼
   Design Gate (Human approves plan)
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
  Prototype Gate (Human approves → Git commit)
```

## Directory Layout (new/changed files)

```
backend/
├── core/
│   ├── models.py              ← ADD: TechPlan, BuildArtifact, TestReport, TestPlan
│   └── confidence.py          (unchanged)
├── agents/
│   ├── specialist.py          (unchanged)
│   ├── skeptic.py             (unchanged)
│   ├── planner.py             ← NEW: PlannerAgent
│   ├── builder.py             ← NEW: BuilderAgent
│   └── qa.py                  ← NEW: QAAgent
├── orchestrator/
│   ├── database.py            ← ADD: tech_plans, build_artifacts, test_reports tables
│   ├── audit.py               (unchanged)
│   ├── gates.py               ← ADD: /api/plan, /api/build, /api/test, /api/commit endpoints
│   └── sandbox.py             ← NEW: Docker container management
├── main.py                    ← ADD: docker dependency, init sandbox on startup
└── pyproject.toml             ← ADD: docker-py dependency
frontend/
├── src/
│   ├── App.tsx                ← MODIFY: add gate flow steps, state management
│   ├── api.ts                 ← ADD: new endpoint types and client methods
│   └── components/
│       ├── UnderstandingView.tsx   (unchanged)
│       ├── CritiquePanel.tsx       (unchanged)
│       ├── ConfidenceBadge.tsx     (unchanged)
│       ├── TechPlanView.tsx        ← NEW: display planner output
│       ├── BuildView.tsx           ← NEW: streaming build logs
│       └── TestReportView.tsx      ← NEW: test results display
tests/
├── test_planner.py            ← NEW
├── test_builder.py            ← NEW
├── test_qa.py                 ← NEW
├── test_sandbox.py            ← NEW
├── test_agents.py             ← MODIFY: add planner/qa tests
└── test_integration.py        ← MODIFY: add phase1 integration tests
```

## New Data Contracts

### `backend/core/models.py` additions

```python
class FileSpec(BaseModel):
    path: str                              # relative path from project root
    purpose: str                           # why this file exists
    content_type: str                      # "code" | "config" | "test" | "doc"

class ComponentSpec(BaseModel):
    name: str
    responsibility: str
    depends_on: list[str] = []

class APIRoute(BaseModel):
    method: str                            # GET | POST | PUT | DELETE
    path: str
    description: str

class TechPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    understanding_id: str
    tech_stack: list[str]
    file_tree: list[FileSpec]
    components: list[ComponentSpec]
    api_routes: list[APIRoute] = []
    markdown_summary: str

class BuildArtifact(BaseModel):
    build_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    plan_id: str
    files_created: list[str]
    files_modified: list[str]
    docker_logs: list[str]
    status: str                            # "success" | "failed"

class TestPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    build_id: str
    framework: str
    test_files: list[FileSpec]
    acceptance_criteria: list[str]

class TestReport(BaseModel):
    report_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    build_id: str
    passed: int
    failed: int
    skipped: int
    coverage_pct: float | None = None
    details: list[TestResult]

class TestResult(BaseModel):
    test_name: str
    status: str                            # "passed" | "failed" | "skipped"
    error_message: str | None = None
```

## Docker Sandbox (`backend/orchestrator/sandbox.py`)

- Uses `docker-py` (`DockerClient` from env or default socket)
- Sandbox lifecycle tied to FastAPI app lifespan
- **`SandboxManager`** class:
  - `start()` — creates container with project mounted as volume, returns container_id
  - `exec(command)` — runs command in container, returns `{stdout, stderr, exit_code}`
  - `stream_logs()` — async generator yielding log lines for frontend SSE
  - `stop()` — kills and removes container
- Builder calls `sandbox.exec()` for code generation + testing; logs streamed to frontend
- Base image: `python:3.11-slim` (can be swapped via env)

## API Endpoints

```
POST /api/plan
  Request:  { "understanding_id": "..." }
  Response: { "plan": TechPlan, "plan_id": "..." }

POST /api/build
  Request:  { "plan_id": "..." }
  Response: { "build": BuildArtifact }

POST /api/test
  Request:  { "build_id": "..." }
  Response: { "test_plan": TestPlan, "test_report": TestReport }

POST /api/commit
  Request:  { "build_id": "...", "message": "..." }
  Response: { "commit_sha": "...", "success": true }

POST /api/sandbox/start
  Response: { "container_id": "..." }

POST /api/sandbox/exec
  Request:  { "command": "..." }
  Response: { "stdout": "...", "stderr": "...", "exit_code": 0 }

GET /api/sandbox/logs?since=seconds
  Response: SSE stream of log lines

POST /api/sandbox/stop
  Response: { "success": true }
```

## Agent Details

### PlannerAgent (`backend/agents/planner.py`)

- Ollama prompt: Understanding JSON → TechPlan JSON
- System prompt instructs to produce file tree, components, tech stack decisions
- Temperature: 0.2 (low creativity, structured output)
- Returns `TechPlan` model
- `markdown_summary` field rendered in the Design Gate frontend

### BuilderAgent (`backend/agents/builder.py`)

- Takes `TechPlan` → generates code file-by-file
- Uses `SandboxManager.exec()` to create files and run commands inside the container
- Retry loop: up to 3 attempts per command on failure
- Every command + result logged to `docker_logs` for full transparency
- Returns `BuildArtifact` with list of files created/modified

### QAAgent (`backend/agents/qa.py`)

- Phase 1: generates `TestPlan` from `TechPlan` (what to test, framework choice)
- Runs test suite inside Docker sandbox via `pytest` (or equivalent)
- Parses test output into `TestReport`
- Reports to human at Prototype Gate

## Frontend Changes

### New components:
- **`TechPlanView.tsx`** — renders file tree, tech stack, component list. Color-coded tags for each file spec (new/modified/config).
- **`BuildView.tsx`** — scrollable log panel showing docker commands + output in real-time. File change summary at the top.
- **`TestReportView.tsx`** — pass/fail counts, test detail list with expandable error messages.

### Modified:
- **`App.tsx`** — multi-step gate flow: goal input → Understanding Gate → Plan Gate → Build Gate → Test Gate → Commit button. Each step loads sequentially with human approval between.
- **`api.ts`** — new types and client methods for plan/build/test/commit/sandbox endpoints.

## Gate Flow (Human-in-the-Loop)

```
Step 1: Enter goal → Specialist + Skeptic run → Human resolves critique at Understanding Gate
Step 2: Planner generates TechPlan → Human reviews at Design Gate (✅ Approve / 🔄 Retry)
Step 3: Builder generates code in Docker sandbox → logs stream to frontend → Human reviews at Build Gate
Step 4: QA runs tests → TestReport displayed → Human approves at Prototype Gate
Step 5: Human enters commit message → backend commits to Git
```

## Error Handling

- Planner retries (2×) on JSON parse failure
- Builder retries failed commands (3×), reports final failure as `BuildArtifact.status = "failed"`
- QA reports test failures in `TestReport` — does not block, human decides
- Docker sandbox restart: if container dies, `SandboxManager.start()` recreates

## Out of Scope (Phase 1)

- Assumption regression checks (Phase 2)
- Skeptic tool use (Phase 2)
- CI/CD, store deployment (Phase 3)
- ChromaDB / vector store (Phase 2)
- PostgreSQL (Phase 2+)

## Phase Completion Criteria

- [ ] `POST /api/plan` produces TechPlan from approved Understanding
- [ ] `POST /api/build` generates working code in Docker sandbox, logs streamable
- [ ] `POST /api/test` runs test suite and returns TestReport
- [ ] `POST /api/commit` creates a Git commit with agent-authored message
- [ ] Frontend displays all five gates sequentially with human approve/retry
- [ ] Human can view Docker sandbox logs at any time
- [ ] All new code passes existing 58 tests + new Phase 1 tests
