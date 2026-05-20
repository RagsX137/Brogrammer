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

---

## Failure Modes and Degradation

This section is the on-call runbook. Every known failure mode, its symptom, and the expected system behaviour.

### LLM returns malformed JSON
- **Symptom:** `RuntimeError: {agent} failed after 3 retries` in logs; API returns 502
- **Where:** All agents (`SpecialistAgent`, `SkepticAgent`, `PlannerAgent`, `BuilderAgent`, `QAAgent`) wrap LLM calls with `@with_retries(retries=3)`
- **Behaviour:** Retries up to 3 times on `json.JSONDecodeError`, `ValidationError`, `ConnectionError`, `TimeoutError`, `OSError`. After exhaustion, the error propagates to the orchestrator which returns HTTP 502 with the agent's error message.
- **Recovery:** Retry the request. If persistent, check Ollama health (`ollama ps`) and model availability.

### Docker not running
- **Symptom:** `/api/build` or `/api/test` returns HTTP 503 with hint about Docker
- **Where:** `SandboxManager._ensure_connected()` calls `client.ping()`; Docker SDK raises `DockerException` on connection failure
- **Behaviour:** Build endpoints fail fast with a 503 and message: "Docker sandbox failed to start..."
- **Recovery:** Run `docker ps` to verify Docker is running. Run `docker pull python:3.11-slim`.

### Ollama unreachable
- **Symptom:** First LLM call in any endpoint times out or returns connection refused
- **Where:** `OllamaClient.chat()` in `specialist.py`
- **Behaviour:** Agent retries 3 times via `@with_retries`, then raises `RuntimeError` which becomes HTTP 502
- **Recovery:** Verify Ollama is running: `curl http://localhost:11434/api/tags`. Check `OLLAMA_BASE_URL` in `.env`.

### ReAct loop exhausted
- **Symptom:** Critique returned with `rounds_used == MAX_TOOL_ROUNDS` (4) and `questions` containing "Skeptic loop exhausted without finalizing"
- **Where:** `SkepticAgent.generate_critique()` sandbox path
- **Behaviour:** Returns a critique with empty `scenarios` and a single `questions` entry explaining the exhaustion
- **Recovery:** Run again; the LLM may produce parseable output on a retry. If persistent, the goal may be too complex for the model.

### Consecutive JSON parse failures in ReAct loop
- **Symptom:** Critique returned with `tool_evidence` containing `[round N] LLM returned malformed JSON: ...` and force-finalised after 2 consecutive failures
- **Where:** `SkepticAgent.generate_critique()` sandbox path
- **Behaviour:** The loop appends an error message to the LLM context and retries. After 2 consecutive failures, it force-finalises with `rounds_used` set to the current round.
- **Recovery:** Retry the request. The non-determinism of the LLM may resolve it.

### Sandbox container accumulates
- **Symptom:** `docker ps` shows many `python:3.11-slim` or `brogrammer/sandbox` containers with label `brogrammer.build=true`
- **Where:** `SandboxManager` containers not cleaned up after crashes
- **Behaviour:** Startup and periodic tasks run `cleanup_orphans()` which removes all containers with the label. Default interval is 600s, configurable via `SANDBOX_CLEANUP_INTERVAL`.
- **Recovery:** Manual: `docker rm -f $(docker ps -aq --filter label=brogrammer.build=true)`.

### Sandbox tools not found
- **Symptom:** Tool execution returns `ToolResult.stderr` with "command not found" or import error
- **Where:** `SandboxManager.install_tools()`
- **Behaviour:** On first tool use, `install_tools` runs `apt-get` and `pip install`. If any verification probe (`which curl`, `which npm`, `python3 -c "import duckduckgo_search"`) fails, it raises `RuntimeError` which is caught by `_execute_tool` and placed in `ToolResult.stderr`.
- **Recovery:** Build the pre-warmed sandbox image: `bash bin/build-sandbox-image.sh && SANDBOX_IMAGE=brogrammer/sandbox:latest`.

### SSRF attempt blocked
- **Symptom:** `ValueError: URL host '169.254.169.254' is in the denylist` in logs
- **Where:** `SandboxManager.validate_url()` in `sandbox.py`
- **Behaviour:** The curl command is never executed; the error surfaces in `ToolResult.stderr`. Denied ranges: `localhost`, `127.0.0.0/8`, `169.254.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, IPv6 link-local, `metadata.google.internal`.
- **Recovery:** No action needed—this is protective. If a legitimate external tool needs access to a private host, set `SKEPTIC_CURL_ALLOWLIST` env var.

### Git commit fails
- **Symptom:** `/api/commit` returns 400 ("No files to commit") or 500 ("git add/commit failed")
- **Where:** `gates.py:commit_build()`
- **Behaviour:** Returns HTTP 400 if the build produced no artifacts. Returns HTTP 500 with `git add` or `git commit` stderr if the git operation fails.
- **Recovery:** Ensure the build completed successfully first. Check that the host working directory (`.brogrammer/builds/<build_id>/`) contains the expected files.

### Frontend hydration fails
- **Symptom:** Page reload shows blank screen or incorrect step
- **Where:** `App.tsx` localStorage persistence
- **Behaviour:** `ErrorBoundary` wraps the app and shows a reload button. Stale localStorage state from a different schema version (v1 vs v2) is silently discarded.
- **Recovery:** Click "Reload" on the ErrorBoundary overlay, or clear `localStorage` manually (`localStorage.removeItem('brogrammer.flow.v1')` in devtools).
