# Brogrammer Remediation Plan — Phases 0, 1, 2

> **Audience:** Human engineer or AI agent picking up the codebase fresh.
> **Goal:** Take Brogrammer from "tests pass, real runs are fragile" to "real runs are reliable end-to-end" across Phases 0–2, and lay the foundation for Phase 3+ functionality.
> **Branch under review:** `phases/phase_2` at HEAD `f641e0263`.
> **Last validated:** 2026-05-18.

---

## 0. How to Use This Document

Every task has the same shape so it can be executed without ambiguity:

```
### TASK-ID — Title                                          [Severity: …]
**Files:**           paths to touch
**Why:**             observed failure or risk
**Acceptance:**      checklist that proves the fix landed
**Verify by:**       exact command to run
**Out of scope:**    explicitly NOT this task
```

- Severity ladder: **CRITICAL** (silently produces wrong results), **HIGH** (intermittent runtime failure), **MEDIUM** (operability/UX), **LOW** (polish).
- Work top-to-bottom within a section. Sections are independent — a partial Phase 0 cleanup can ship without Phase 2 changes.
- Mark each TASK-ID complete in `docs/COMPLETED.md` (the append-only log) before moving on.
- Run `pytest -q` after every task. Do not start a new task with a red test suite.

---

## 1. Current State — Evidence, Not Claims

Three commits on `phases/phase_2` claim Phase 2 is complete. The test suite (128 passing tests) **uses mocked LLM clients and fake sandboxes** — it cannot catch the failures below. Real-world validation surfaced them.

### Works end-to-end
- `/api/plan` against real `gemma4:latest` — 200 in ~10 s.
- `/api/build` against real Docker — wrote `word_count.py` to the sandbox.
- `/api/test` returns HTTP 200.
- `compute_confidence` math.
- Path-traversal rejection on `FileSpec.path`.
- SQL is parameterized everywhere.

### Broken or fragile in real use
| Symptom | Where | Evidence |
|---|---|---|
| `/api/run-loop` 500s on first call | `SpecialistAgent.generate_with_fragility_check` makes 4 LLM calls; any single truncated JSON kills the request, no retry | Reproduced twice via `/api/run-loop` and direct script; `pydantic_core.ValidationError: Invalid JSON: EOF while parsing` |
| `/api/test` reports success on zero tests | `QAAgent.generate_test_plan` returns a `TestPlan` with `test_files`, but those files are never **written** to the sandbox. `run_tests` shells `pytest tests` against an empty directory and the parser sees no `FAILED`, so `passed=0 failed=0 skipped=0` is treated as success | Real `/api/test` returned `200` with empty counters after a real build |
| `/api/commit` would commit nothing | Builder writes files into the sandbox at `/workspace/...`. Commit endpoint runs `git add <path>` against the host CWD where those files do not exist | Code inspection — endpoint not exercised live to avoid mutating the repo |
| Stale Docker containers accumulate | `SandboxManager.cleanup_orphans()` only fires on FastAPI startup; tests, scripts, and crashed processes leave containers behind | Found 4 `python:3.11-slim` orphans before validation began |
| Skeptic ReAct can be prompted into SSRF | `curl` tool has no URL allowlist — a hostile or confused Skeptic could hit `169.254.169.254/latest/meta-data/` from inside Docker | Code inspection of `SandboxManager.build_tool_command` |
| ReAct loop silently eats JSON errors | `SkepticAgent.generate_critique` `except Exception: continue` on bad JSON — caller never knows | `backend/agents/skeptic.py:55-61` |
| Audit log loses tool evidence | `gates.py` `append_event("critique_created", …)` only persists `scenarios` and `questions`. `tool_evidence` is dropped | `backend/orchestrator/gates.py:121-124` |

### Confirmed sound
- Docker is reachable (`docker ps` works, image present).
- Ollama is reachable, serving `gemma4:latest` and `qwen3.6:35b`.
- `.env` plumbing landed cleanly in this session — 128 tests still pass.
- `PlannerAgent` has the only correctly hardened retry loop in the agent layer.

---

## 2. Operating Model

| Action | Command |
|---|---|
| Run the test suite | `pytest -q` (from repo root) |
| Run only the real-LLM integration tests (none exist yet — TASK-X3 adds them) | `RUN_REAL_LLM=1 pytest -q -m real_llm` |
| Start backend | `python -m backend.main` |
| Start frontend dev server | `cd frontend && npm run dev` |
| Clean up dangling sandbox containers | `docker rm -f $(docker ps -aq --filter label=brogrammer.build=true)` |

**Definition of done** for every task in this plan:

1. Acceptance checklist green.
2. `pytest -q` green.
3. New tests added if the task is fixing a behavior the mocks couldn't catch.
4. A line appended to `docs/COMPLETED.md` with task ID and date.

---

## 3. Phase 0 — Fix the Foundation

Phase 0 is the dual-agent loop. The contract is: a user goal goes in, a structured `Understanding` + `SkepticCritique` + `ConfidenceProfile` comes out. Today this contract is only met on a happy LLM day.

### P0-F01 — Add JSON-repair retry loop to `SpecialistAgent`                      [HIGH]
**Files:** `backend/agents/specialist.py`
**Why:** `generate_understanding` and `_single_understanding` both call `model_validate_json(raw)` directly. One truncated response from the LLM bubbles up as HTTP 500. `PlannerAgent` already demonstrates the right pattern.
**Acceptance:**
- Both methods retry up to 3 times on `pydantic.ValidationError`, `json.JSONDecodeError`, `ConnectionError`, `TimeoutError`, `OSError`.
- A final failure raises `RuntimeError("Specialist failed after 3 retries: …")` (same shape as Planner) so the orchestrator can return HTTP 502 with a meaningful body.
- Add a unit test using a `FlakyOllamaClient` that returns malformed JSON twice then good JSON.
**Verify by:** `pytest tests/test_agents.py::test_specialist_retries_malformed_json -q`
**Out of scope:** Fragility-detection redesign — see P0-F02.

### P0-F02 — Make fragility detection cost-proportional and resilient            [HIGH]
**Files:** `backend/agents/specialist.py`, `backend/orchestrator/gates.py`
**Why:** `generate_with_fragility_check` fires **four** LLM calls (1 cold + 3 at T=0.7). With a 4–8 B local model, p(any one returns malformed JSON) is non-trivial; chaining four multiplies the failure probability. The fragility signal is also a low-information bool that the UI never surfaces meaningfully.
**Acceptance:**
- Replace the 3-extra-call loop with a single resampled call at T=0.7 and a deterministic comparison of `{assumption.statement}` sets — fragility means the resample differs from the main set.
- Each sub-call uses the P0-F01 retry wrapper.
- If the resample retries are exhausted, return `fragile=True` instead of 500-ing (loud about uncertainty, not loud about errors).
- Update `compute_confidence` callers to keep the same `fragility_flag` semantics.
- Update `test_specialist.py` fragility tests for the new call count.
**Verify by:** `pytest tests/test_agents.py -k fragility -q`
**Out of scope:** Reworking the confidence formula.

### P0-F03 — Add JSON-repair retry loop to `SkepticAgent` (no-sandbox path)        [HIGH]
**Files:** `backend/agents/skeptic.py`
**Why:** The ReAct branch already tolerates malformed JSON via `try/except: continue`. The no-sandbox branch (taken whenever the shared sandbox is `None`, which is the default in `test_integration.py`) calls `SkepticCritique.model_validate_json(raw)` once and dies.
**Acceptance:**
- Extract the retry helper from P0-F01 into `backend/agents/_retry.py` and reuse it.
- No-sandbox path retries up to 3 times before raising.
- New test feeds two malformed responses then one good — must succeed.
**Verify by:** `pytest tests/test_agents.py::test_skeptic_retries_malformed_json -q`

### P0-F04 — Persist `tool_evidence` in the audit log                            [MEDIUM]
**Files:** `backend/orchestrator/gates.py`
**Why:** Phase 2's whole point is real tool evidence. `gates.py` only writes `{"scenarios": …, "questions": …}` to the audit table — the most useful column is dropped on the floor.
**Acceptance:**
- `append_event("critique_created", …)` payload includes `tool_evidence` and the `understanding_id`.
- A test asserts the audit row carries every field of `SkepticCritique`.
**Verify by:** `pytest tests/test_audit.py -k tool_evidence -q`

### P0-F05 — Input validation on `RunLoopRequest.goal`                           [HIGH]
**Files:** `backend/orchestrator/gates.py`, `backend/core/models.py` (optional)
**Why:** The DoS finding in `docs/PHASE2_AUDIT.md` is correct. `goal: str` is unbounded; a 1 MB goal stalls the LLM and bloats the audit table.
**Acceptance:**
- `goal: str = Field(min_length=1, max_length=10_000)` on `RunLoopRequest`.
- `@field_validator("goal")` strips whitespace and rejects empty post-strip.
- Test: `POST /api/run-loop {"goal": ""}` → 422; `{"goal": "A"*20000}` → 422.
**Verify by:** `pytest tests/test_integration.py -k goal_validation -q`

### P0-F06 — Audit event ordering and pagination                                 [MEDIUM]
**Files:** `backend/orchestrator/audit.py`, `backend/orchestrator/gates.py`, `frontend/src/api.ts`
**Why:** `get_events` returns oldest-first (`ORDER BY created_at ASC`) but the UI presents "recent activity". With Phase 1 each gate emits several events, so within minutes the limit-50 window misses the most recent items.
**Acceptance:**
- `get_events(db, limit, before=None)` orders **DESC** and supports a cursor (`before=<created_at iso>`).
- `/api/audit/events?limit=50&before=…` exposes the cursor.
- Frontend `getAuditEvents` accepts an optional cursor; document it but no UI change required yet.
- Tests: insert 60 events, ensure default fetch returns the latest 50.
**Verify by:** `pytest tests/test_audit.py -k pagination -q`

### P0-F07 — Externalize frontend `API_BASE`                                     [LOW]
**Files:** `frontend/src/api.ts`, `.env.example`, `.env`
**Why:** Already documented as a finding in `PHASE2_AUDIT.md` §6. The `.env` plumbing was added in this session; finish the wire.
**Acceptance:**
- `const API_BASE = import.meta.env.VITE_API_BASE || '/api';`
- `.env.example` and `.env` include `VITE_API_BASE=/api`.
**Verify by:** `cd frontend && npm run build` succeeds; in dev, network tab shows requests to `${VITE_API_BASE}/…`.

---

## 4. Phase 1 — Make the Build/Test/Commit Loop Real

Phase 1's contract is: an approved understanding becomes a working prototype, a passing test report, and a git commit. Today the test report is theatre and the commit references files that aren't on the host.

### P1-F01 — QA actually writes the test files it planned                         [CRITICAL]
**Files:** `backend/agents/qa.py`, `backend/orchestrator/gates.py`, `tests/test_qa.py`, `tests/test_integration_phase1.py`
**Why:** Today the test ran `pytest tests` against a directory that exists in the sandbox only because the Builder happened to mkdir it. No test files are written, pytest collects nothing, parser sees no `FAILED`, and the gate reports success. This silently lies to the human at the Prototype Gate — the most load-bearing gate in the whole product.
**Acceptance:**
- `QAAgent.generate_test_plan` returns a `TestPlan` **and** a `dict[path, content]` mapping. Either expand `TestPlan` with a `contents: dict[str, str]` field, or add a second LLM call per test file (mirroring Builder's `_generate_file_content`).
- New method `QAAgent.write_test_files(plan: TestPlan, sandbox)` writes each test file to the sandbox using the same heredoc-or-base64 pattern Builder uses (also see P1-F03).
- `/api/test` calls `write_test_files` **before** `run_tests`.
- If `pytest` collects zero items, the report status must be `failed` with `error_message="no tests collected"`, **never** silent success.
- New integration test: feed a real-LLM-style mock that produces a passing test and a failing test; assert counts are non-zero.
**Verify by:** `pytest tests/test_qa.py::test_qa_writes_then_runs -q`
**Out of scope:** Coverage measurement (deferred to P3).

### P1-F02 — Build artifacts land on the host, not just the sandbox               [CRITICAL]
**Files:** `backend/orchestrator/sandbox.py`, `backend/agents/builder.py`, `backend/orchestrator/gates.py`
**Why:** `commit_build` does `subprocess.run(["git", "add", path])` from the FastAPI process's CWD. Builder wrote to `/workspace/<path>` inside Docker. The host never sees the file, so the commit is empty or fails.
**Acceptance:**
- Pick one of two strategies and document it in `docs/ARCHITECTURE.md`:
  - **(A) Bind-mount strategy (preferred for Phase 1):** `SandboxManager.start` mounts a per-build host directory (e.g. `./.brogrammer/builds/<build_id>/`) at `/workspace`. `BuildArtifact.host_workdir` records the absolute path. Commit endpoint uses that path.
  - **(B) Copy-back strategy:** `SandboxManager.copy_out(container_path, host_path)` after build; `commit_build` operates on the host copy.
- Either way: `BuildArtifact` gains `host_workdir: str` so downstream agents (QA, commit) don't recompute it.
- Test (Docker required): write a file in the sandbox via Builder, assert it exists on the host at the recorded path.
**Verify by:** `pytest tests/test_sandbox.py -k host_workdir -q --run-docker`
**Out of scope:** Cleaning up old build directories — see P1-F08.

### P1-F03 — Robust file write into the sandbox                                  [MEDIUM]
**Files:** `backend/agents/builder.py`
**Why:** `cat > … << 'BROGRAMMER_EOF'\n{content}\nBROGRAMMER_EOF` corrupts whenever generated content contains the literal sentinel or unbalanced quotes. The LLM is being asked to emit arbitrary code — this **will** happen.
**Acceptance:**
- Replace heredoc with `base64 -d > path << 'EOF'\n{b64}\nEOF` or, better, use `docker put_archive` to upload a tar stream from Python directly.
- Test: write a file whose contents include `BROGRAMMER_EOF` and assert byte-identical read-back.
**Verify by:** `pytest tests/test_builder.py -k binary_safe_write -q --run-docker`

### P1-F04 — `commit_build` safety and feedback                                  [HIGH]
**Files:** `backend/orchestrator/gates.py`
**Why:** Today: empty `artifact_files` → silent no-op success; `git add` failure ignored; user gets `commit_sha=""` with `success=True`.
**Acceptance:**
- Reject the request with 400 if `artifact_files` is empty.
- Each `git add` checks return code; first failure → 500 with the stderr text.
- After commit, run `git rev-parse HEAD` to capture the SHA reliably (the current code parses `git commit` stdout which is empty on success).
- `CommitRequest.message` validated `min_length=1, max_length=500`.
- Audit event `commit_created` includes `files`, `sha`, and the validated message.
- Test: empty artifacts → 400; happy path → real SHA round-trips into audit log.
**Verify by:** `pytest tests/test_integration_phase1.py -k commit -q`

### P1-F05 — Make `exec_safe` thread-safe                                        [MEDIUM]
**Files:** `backend/orchestrator/sandbox.py`
**Why:** `exec_safe` mutates `self.exec_timeout` for the duration of one call. The shared sandbox is used by Builder, QA, **and** Skeptic ReAct concurrently in real workflows — concurrent calls will race and yield wrong timeouts.
**Acceptance:**
- Add an optional `timeout` parameter to `exec` itself; have `exec_safe` pass it through instead of mutating instance state.
- Concurrency test: gather 10 `exec_safe(timeout=2)` and 10 `exec(120)` calls; assert no call uses the wrong wall-clock budget (mock `_exec` to record the timeout it was scheduled with).
**Verify by:** `pytest tests/test_sandbox.py -k thread_safe -q`

### P1-F06 — Sandbox lifecycle owned by the request                              [MEDIUM]
**Files:** `backend/orchestrator/gates.py`, `backend/orchestrator/sandbox.py`
**Why:** `create_app` instantiates one shared sandbox that's never stopped. Containers accumulate when the server restarts or crashes. `cleanup_orphans()` only runs on startup.
**Acceptance:**
- Add `@app.on_event("shutdown")` calling `shared_sandbox.stop()`.
- Add a periodic background task (`asyncio.create_task` on startup) that runs `cleanup_orphans` every 10 minutes. Configurable via `SANDBOX_CLEANUP_INTERVAL` env var (default 600).
- For local dev, document `docker rm -f $(docker ps -aq --filter label=brogrammer.build=true)` in `AGENTS.md`.
**Verify by:** Start backend, kill it with `kill -9`, restart, observe orphan cleanup in logs.

### P1-F07 — Frontend `App.tsx` state persistence and ErrorBoundary               [MEDIUM]
**Files:** `frontend/src/App.tsx`, `frontend/src/components/ErrorBoundary.tsx` (new), `frontend/src/main.tsx`
**Why:** Documented in `PHASE2_AUDIT.md` §§3,5. Page reload nukes a 7-step in-flight gate flow; any uncaught throw shows a blank screen.
**Acceptance:**
- `ErrorBoundary` wraps `<App />` in `main.tsx`. Shows last error + a reload button.
- `App.tsx` persists `{step, goal, result, plan, build, testReport, commitSha}` to `localStorage` keyed by `brogrammer.flow.v1` on every state change; hydrates on mount.
- "Start New" clears the localStorage key.
- Bumps the key when the shape changes (`v1` → `v2`), discarding old state.
**Verify by:** Manual — kick off a flow, refresh after Design Gate, confirm UI hydrates to the same step.

### P1-F08 — Per-build host directory cleanup                                    [LOW]
**Files:** `backend/orchestrator/sandbox.py` or new `backend/orchestrator/janitor.py`
**Why:** Only matters once P1-F02 lands. Per-build directories accumulate under `./.brogrammer/builds/`.
**Acceptance:**
- A janitor function deletes build directories older than 7 days (configurable via `BUILD_RETENTION_DAYS`).
- Scheduled by the same periodic task as P1-F06.
- `.brogrammer/` added to `.gitignore`.
**Verify by:** Unit test that touches a directory's mtime to 8 days ago and asserts it gets removed.

---

## 5. Phase 2 — Skeptic Tool Access, Done Properly

Phase 2's contract is: the Skeptic uses real tools (`curl`, `npm_view`, `web_search`) inside the sandbox before escalating to a human. The structure is in place; the safety rails and error reporting are not.

### P2-F01 — URL allowlist + denylist on `curl` tool                              [HIGH]
**Files:** `backend/orchestrator/sandbox.py`, `backend/core/models.py`
**Why:** Today the Skeptic can be prompted (deliberately or accidentally) to `curl http://169.254.169.254/latest/meta-data/iam/security-credentials/` from inside Docker. That's a textbook SSRF surface, and the container has full outbound network by default.
**Acceptance:**
- `build_tool_command("curl", args)` validates the URL against:
  - **Scheme allowlist:** `http`, `https` only.
  - **Host denylist:** `localhost`, `127.0.0.0/8`, `169.254.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, IPv6 link-local, plus `metadata.google.internal`.
  - **Optional host allowlist:** if `SKEPTIC_CURL_ALLOWLIST` env var is set (comma-separated suffixes), only those hosts are reachable.
- `ToolRequest` validation rejects bad URLs at the model layer (so denylist is enforced even if `build_tool_command` is bypassed).
- Test matrix covers each rejected case with a parameterized test.
**Verify by:** `pytest tests/test_phase2_security.py -k url_allowlist -q`
**Out of scope:** Network namespacing the sandbox (Phase 3).

### P2-F02 — Surface, don't swallow, ReAct JSON errors                            [MEDIUM]
**Files:** `backend/agents/skeptic.py`
**Why:** On every non-final round, `except Exception: continue` hides parsing failures. The result is invisible cost (LLM calls + tool calls) with no diagnostic trail.
**Acceptance:**
- Each parse failure appends a `tool_evidence` line like `"[round 2] LLM returned malformed JSON: <first 200 chars>"`.
- After 2 consecutive parse failures, force-finalize the loop with an empty critique and a `questions` entry saying so.
- Tests cover: 1 failure then success, 2 failures then success, 4 failures.
**Verify by:** `pytest tests/test_agents.py -k react_loop_errors -q`

### P2-F03 — Idempotent and observable `install_tools`                            [MEDIUM]
**Files:** `backend/orchestrator/sandbox.py`
**Why:** Each `install_tools` shells `apt-get update` + `apt-get install` + `pip install`. The current attribute guard works, but failures (no network, apt mirror down, pip 429) are silent — the next `curl` call inexplicably returns `command not found`.
**Acceptance:**
- After install, `install_tools` calls `which curl`, `which npm`, `python3 -c "import duckduckgo_search"` and raises `RuntimeError` with the failed probe if any check fails.
- The exception bubbles to `_execute_tool` and goes into `ToolResult.stderr` so the ReAct loop sees it.
- Test: monkeypatch `exec` to simulate apt failure; assert the result captures it.
**Verify by:** `pytest tests/test_sandbox.py -k install_tools_failure -q`

### P2-F04 — Bake a pre-warmed sandbox image                                     [MEDIUM]
**Files:** `Dockerfile.sandbox` (new), `backend/orchestrator/sandbox.py`, `.env.example`
**Why:** Running `apt-get update` inside every container on first tool use takes 20–40 s and depends on package mirrors. For a multi-tenant or CI scenario this is brittle and slow.
**Acceptance:**
- New `Dockerfile.sandbox` based on `python:3.11-slim` that pre-installs `curl`, `nodejs`, `npm`, and `duckduckgo-search`.
- `SANDBOX_IMAGE` default becomes `brogrammer/sandbox:latest`; fall back to plain `python:3.11-slim` + runtime install when the image is missing.
- `bin/build-sandbox-image.sh` shell script wraps `docker build -t brogrammer/sandbox:latest -f Dockerfile.sandbox .`.
- README updated.
**Verify by:** `bash bin/build-sandbox-image.sh && SANDBOX_IMAGE=brogrammer/sandbox:latest pytest tests/test_sandbox.py -k tools_preinstalled -q`

### P2-F05 — Round-budget telemetry on the ReAct loop                            [LOW]
**Files:** `backend/agents/skeptic.py`, `backend/orchestrator/gates.py`
**Why:** Today there's no way to know whether the Skeptic ran 1 round or 4. That's the headline observability question for Phase 2.
**Acceptance:**
- `SkepticCritique` gains `rounds_used: int` and `tool_calls: int` (default 0 for backward compat).
- `gates.run_loop` includes both in the audit payload.
- Frontend `CritiquePanel` shows a small `🔍 N rounds, M tool calls` label below the critique.
**Verify by:** Manual + `pytest tests/test_agents.py -k react_telemetry -q`

### P2-F06 — Audit individual tool calls                                         [MEDIUM]
**Files:** `backend/orchestrator/database.py`, `backend/orchestrator/audit.py`, `backend/agents/skeptic.py`, `backend/orchestrator/gates.py`
**Why:** Tool calls are the only Phase 2 action with side effects. Today they leave no per-call trace; only the aggregate `tool_evidence` strings make it out.
**Acceptance:**
- New table `tool_call_events(id PK, critique_id FK, round INTEGER, tool TEXT, args TEXT, exit_code INTEGER, stdout_excerpt TEXT, stderr_excerpt TEXT, created_at TEXT)`.
- `excerpt` columns capped at 4 KB.
- `SkepticAgent._execute_tool` writes a row per call via a callback injected by `gates.py` (keep the agent DB-free).
- `/api/critique/<critique_id>/tools` returns the rows for that critique.
- Test: run a 2-round ReAct loop with 1 tool call per round, assert 2 audit rows exist.
**Verify by:** `pytest tests/test_audit.py -k tool_call_events -q`

---

## 6. Cross-Cutting — Reliability and Verifiability

These are not phase-bound. Do them once the per-phase critical/high items are landed.

### TASK-X1 — Centralize the retry decorator                                     [MEDIUM]
**Files:** `backend/agents/_retry.py` (new), all agents.
**Acceptance:**
- One async decorator `@with_retries(retries=3, on=(json.JSONDecodeError, ValidationError, ConnectionError, TimeoutError, OSError))`.
- All four agents use it where they call the LLM.
- 100% line coverage on the helper.
**Verify by:** `pytest tests/test_agents.py -k retry_helper -q`

### TASK-X2 — Structured logging                                                 [MEDIUM]
**Files:** `backend/core/logging.py` (new), `backend/orchestrator/gates.py`, agents.
**Why:** Today the codebase has zero `logger` calls. Failures are exceptions or `print`s. Without a log line per gate transition, debugging real runs is impossible.
**Acceptance:**
- Use `structlog` or stdlib `logging` with a JSON formatter.
- Every API endpoint logs `event=<endpoint> ok=true ms=<elapsed> understanding_id=<id> …` on success and `event=<endpoint> ok=false error=<class> …` on failure.
- `LOG_LEVEL` (default `INFO`) and `LOG_FORMAT` (`json`|`pretty`, default `pretty` in dev) env vars.
- Add a test that captures log output and asserts the success line is emitted for `/api/run-loop`.

### TASK-X3 — Real-LLM smoke test suite, gated by env                            [HIGH]
**Files:** `tests/test_real_llm.py` (new), `pytest.ini`.
**Why:** The current 128 tests can pass while the product is broken because they mock the LLM. A small gated suite that hits the real Ollama instance catches Phase 0/1/2 regressions before they reach a human.
**Acceptance:**
- Marker `@pytest.mark.real_llm` registered in `pytest.ini` under `markers`.
- Skipped by default; runs only when `RUN_REAL_LLM=1` is set.
- One test per phase, each end-to-end:
  - Phase 0: `POST /api/run-loop {"goal":"word count CLI"}` → 200, `confidence.score` ≥ 0, no exceptions in logs.
  - Phase 1: seed an Understanding → `POST /api/plan` → `/api/build` → `/api/test` returns at least one collected pytest item.
  - Phase 2: enable sandbox, run `/api/run-loop`, assert `critique.tool_evidence` length ≥ 1 and `rounds_used` ≥ 1.
- Document `RUN_REAL_LLM=1 OLLAMA_MODEL=gemma4:latest pytest -m real_llm` in `AGENTS.md`.
- These tests are slow (~60–120 s each). Mark `slow` as well.
**Verify by:** `RUN_REAL_LLM=1 pytest -m real_llm -q`

### TASK-X4 — Rate limiting on POST endpoints                                    [MEDIUM]
**Files:** `backend/orchestrator/gates.py`, `backend/pyproject.toml`.
**Why:** Per `PHASE2_AUDIT.md` §4. Local-dev is fine without it, but the moment the product runs on a shared host the LLM bill or sandbox capacity can be exhausted by a single misclick.
**Acceptance:**
- Add `slowapi`. Default limits: `/api/run-loop` 5/min, `/api/plan` 10/min, `/api/build` 5/min, `/api/test` 10/min, `/api/commit` 30/min.
- Limits configurable via env vars (`RATE_LIMIT_RUN_LOOP=5/minute`).
- Add a test asserting the 6th request in a minute returns 429.

### TASK-X5 — Tests for the model `Test*` collision                              [LOW]
**Files:** `pytest.ini`.
**Why:** `TestPlan`, `TestReport`, `TestResult` Pydantic models trigger `PytestCollectionWarning` whenever they're imported into a test file. Fix at the config level — renaming the contracts is not worth the churn this late.
**Acceptance:**
- `python_classes = *Test` in `pytest.ini`. Confirm no collection warnings remain.
- Add a CI-style check: `pytest -q 2>&1 | grep -q "PytestCollectionWarning" && exit 1 || exit 0`.

### TASK-X6 — Document the failure modes                                        [LOW]
**Files:** `docs/ARCHITECTURE.md`, `docs/MODULES.md`.
**Acceptance:** A new "Failure modes and degradation" section in `ARCHITECTURE.md` listing:
- LLM malformed JSON → retry then 502.
- Docker not running → `/api/build` returns 503 with hint.
- Ollama unreachable → `/api/run-loop` returns 503 with hint.
- ReAct exhausted → critique flagged with `rounds_used == MAX_TOOL_ROUNDS`.
This page is the on-call runbook in miniature.

---

## 7. Long-Term Roadmap — Foundation for Phase 3+

The fixes above leave Brogrammer correct on a single machine for a single human. The architecture diagram in `docs/ARCHITECTURE.md` already commits us to more. The next chunks of work should be done **after** the above, in this order. Each is a phase-sized initiative and gets its own spec under `docs/superpowers/specs/`.

### R1 — Pluggable LLM via LiteLLM                                              [Phase 3 prep]
- Replace direct `ollama` usage in `OllamaClient` with a `LiteLLMClient` that talks to any provider via `litellm.acompletion`.
- Move `OLLAMA_MODEL` to `LLM_MODEL` and `LLM_PROVIDER` env vars; default stays Ollama.
- Add a contract test that the same prompt produces a structurally valid `Understanding` from each provider.
- Adds Anthropic/OpenAI capability for the Specialist and Skeptic; keep Builder/QA on local Ollama by default to avoid runaway codegen bills.

### R2 — Postgres-backed orchestrator + ChromaDB for memory                     [Phase 3]
- Abstract DB access behind a `Repository` layer (interface preserved on SQLite for tests).
- Migrate audit, tech_plans, build_artifacts, test_reports to Postgres via Alembic.
- Add ChromaDB collection for past Understandings indexed by goal embedding so the Specialist can do RAG over priors at Phase 4.

### R3 — Assumption regression check                                            [Phase 2.5]
The original Phase 2 brief promised "assumption regression checks on commits" alongside Skeptic tools. With Phase 2 tool access landed, this becomes implementable:
- On commit, run the Skeptic with `tool_evidence` requested for each `assumption.statement` flagged `validated`.
- If any tool result contradicts the validation, block the commit (or warn — UX decision).
- Persist regression results to a new `regression_checks` table.

### R4 — Multi-user, authenticated, multi-tenant                                [Phase 3+]
- FastAPI `Depends(get_current_user)` on all POST endpoints; bearer token or session cookie auth.
- Per-user sandbox isolation (separate container, separate `/workspace`).
- Per-user audit scope on `/api/audit/events`.
- Quota enforcement (LLM tokens per day, builds per day).

### R5 — CI/CD pipeline (Release Gate)                                          [Phase 3]
- GitHub Actions workflow on push: `pytest`, frontend `npm run build`, sandbox image rebuild.
- `release-please` for changelog and tagging.
- `bin/release.sh` wraps a manual release: tag, push, run `RUN_REAL_LLM=1 pytest -m real_llm` against a staging Ollama.

### R6 — Productionized observability                                            [Phase 3]
- OpenTelemetry tracing on every gate.
- A Grafana dashboard fed from the audit table: gates per hour, p95 latency per gate, failure rate per agent.
- Alert: LLM error rate > 5% over 15 min.

---

## 8. Verification Matrix — What "Done" Looks Like

Use this as a release checklist. Every row must be true on `phases/phase_2` before declaring Phase 2 complete in `docs/MODULES.md`.

| ID | Statement | How to verify |
|---|---|---|
| P0-F01 | `/api/run-loop` recovers from one malformed LLM response | `pytest -k specialist_retries_malformed_json` |
| P0-F02 | Fragility detection survives a flaky resample | `pytest -k fragility` |
| P0-F03 | Skeptic non-sandbox path retries | `pytest -k skeptic_retries_malformed_json` |
| P0-F04 | Audit log row contains `tool_evidence` | inspect `audit_events.payload` for a recent critique |
| P0-F05 | Empty/oversize goal returns 422 | `pytest -k goal_validation` |
| P0-F06 | Audit list returns newest first with cursor | `pytest -k pagination` |
| P0-F07 | Frontend honors `VITE_API_BASE` | `cd frontend && VITE_API_BASE=/foo npm run build` |
| P1-F01 | `/api/test` over a real LLM returns `passed > 0` for a trivial app | `RUN_REAL_LLM=1 pytest -m real_llm -k phase1` |
| P1-F02 | Files Builder wrote exist on the host after `/api/build` | the same `real_llm` test asserts `Path(host_workdir/'word_count.py').exists()` |
| P1-F03 | Sentinel-laden content round-trips | `pytest -k binary_safe_write --run-docker` |
| P1-F04 | `/api/commit` returns a real SHA or 4xx/5xx with a reason | `pytest -k commit` |
| P1-F05 | Concurrent `exec_safe` calls use independent timeouts | `pytest -k thread_safe` |
| P1-F06 | After `kill -9`, restart cleans orphans | manual; logs include `cleaned N orphan containers` |
| P1-F07 | Page refresh preserves gate state | manual + cypress smoke (future) |
| P1-F08 | Builds older than retention are purged | `pytest -k retention` |
| P2-F01 | `curl 169.254.169.254` rejected by tool layer | `pytest -k url_allowlist` |
| P2-F02 | 2 consecutive JSON failures finalize the loop with a question | `pytest -k react_loop_errors` |
| P2-F03 | apt failure surfaces as `ToolResult.stderr` | `pytest -k install_tools_failure` |
| P2-F04 | `SANDBOX_IMAGE=brogrammer/sandbox:latest` skips runtime install | `pytest -k tools_preinstalled` |
| P2-F05 | `SkepticCritique.rounds_used` non-zero in real run | `RUN_REAL_LLM=1 pytest -m real_llm -k phase2` |
| P2-F06 | One audit row per tool call | `pytest -k tool_call_events` |
| TASK-X1 | All agents share one retry helper | grep — no module-local retry loop remains |
| TASK-X2 | `event=run_loop ok=true …` log line emitted | `pytest -k structured_logging` |
| TASK-X3 | `RUN_REAL_LLM=1 pytest -m real_llm` exits 0 | local run |
| TASK-X4 | 6th call within a minute returns 429 | `pytest -k rate_limit` |
| TASK-X5 | `pytest -q` produces zero `PytestCollectionWarning` | grep output |
| TASK-X6 | Failure-mode doc exists | `ls docs/ARCHITECTURE.md` and grep `Failure modes` |

---

## 9. Recommended Execution Order

If a single agent picks this up, work in this sequence — it minimizes rework and keeps the test suite green at every step.

1. **TASK-X1** (retry helper) — unblocks P0-F01, P0-F03, P2-F02.
2. **P0-F01, P0-F03, P0-F05, P0-F02** (in that order) — `/api/run-loop` becomes reliable.
3. **TASK-X3** (real-LLM smoke tests) — locks in Phase 0 before touching Phase 1.
4. **P1-F02, P1-F03, P1-F01, P1-F04** — pipeline truly produces and verifies an artifact.
5. **P1-F05, P1-F06, P1-F08** — sandbox lifetime hygiene.
6. **P0-F04, P0-F06, P2-F06** — audit improvements (touch the same tables, batch them).
7. **P2-F01** — close the SSRF gap before any non-trusted user can prompt the Skeptic.
8. **P2-F02, P2-F03, P2-F05** — Phase 2 quality of life.
9. **P2-F04** — pre-baked image once the API surface is settled.
10. **TASK-X2** (logging), **TASK-X4** (rate limit), **TASK-X5** (warnings), **TASK-X6** (docs) — operational polish.
11. **P0-F07, P1-F07** — frontend polish.
12. **R1 → R6** — Phase 3+ initiatives, in numbered order.

When a task completes:
- append `| <ID> | <phase> | <description> | <ISO date> |` to `docs/COMPLETED.md`,
- update the Status column in `docs/MODULES.md` only when **all** rows in a phase's verification matrix are green.

---

## 10. What This Plan Deliberately Does Not Do

- It does not redesign the confidence formula — the current formula is fit for purpose; tune it once the input signals (assumption validation, tool evidence count) are reliable.
- It does not introduce a new agent or change the gate sequence. Both belong to a future spec, not a remediation.
- It does not add a vector DB or LiteLLM in the same wave as the bug fixes — those are R1/R2.
- It does not change the contract types (`Understanding`, `SkepticCritique`, `TechPlan`, `BuildArtifact`, `TestReport`) except by **adding** optional fields. Existing clients keep working.

This is the minimum work to make the existing claims true. Anything beyond it goes into a Phase 3 design document under `docs/superpowers/specs/`.
