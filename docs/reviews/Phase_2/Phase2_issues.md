# Phase 2 Issues — Comprehensive Devil's Advocate Review

> **Status:** Issues identified, tests written, fixes proposed  
> **Review Date:** 2026-05-19  
> **Scope:** Full-stack review of Phase 2 (Skeptic ReAct loop + integration)  
> **Tests:** All 165 tests pass (11 Docker-dependent skipped)

---

## Executive Summary

| Category | Count | Pass Rate |
|---|---|---|
| Total Tests | 165 | 100% |
| New Stress/Regression Tests | 20 | 100% |
| Docker Skipped | 11 | N/A |
| Warnings | 12 | Nuisance |

**Verdict:** Phase 2 is functionally sound but has **14 actionable issues** ranging from CRITICAL to LOW.

---

## CRITICAL Issues (Must Fix Before Production)

### 1. BuilderAgent Ignores Sandbox Exec Failures (`_exec_with_retry`)

**File:** `backend/agents/builder.py:68-73`  
**Severity:** CRITICAL  
**Impact:** If `mkdir -p` fails (e.g., `disk full`), the builder marks the build as "success" because the verification `python -c 'import sys; print(sys.version)'` will succeed after the file failed to write.

**Current Code:**
```python
async def _exec_with_retry(self, command: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        result = await self.sandbox.exec(command)
        if result["exit_code"] == 0:
            return result
    return result  # Returns last FAILED result, caller ignores exit_code
```

**Problem:** `_exec_with_retry` always returns the last result (even on failure). Every caller does `self._exec_with_retry(cmd)` and only checks `exit_code` on the final verification command, not on `mkdir` or `cat` (write) commands.

**Fix:**
```python
async def _exec_with_retry(self, command: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        result = await self.sandbox.exec(command)
        if result["exit_code"] == 0:
            return result
    raise RuntimeError(f"Command failed after {retries} retries: {command[:120]}")

# In build(), catch and set status
    try:
        result = await self._exec_with_retry(mkdir_cmd)
        logs.append(f"$ {mkdir_cmd}")
    except RuntimeError:
        logs.append(f"FAIL: {mkdir_cmd}")
        status = "failed"
```

---

### 2. Commit Endpoint Allows Failed Builds, No Message Validation

**File:** `backend/orchestrator/gates.py:222-243`  
**Severity:** CRITICAL  
**Impact:** The `commit_build` endpoint commits failed builds and doesn't validate the commit message.

**Current Code:**
```python
@app.post("/api/commit")
async def commit_build(req: CommitRequest):
    ...
    # No check that build was successful
    # No check that message is non-empty
    for f in artifact_files:
        subprocess.run(["git", "add", f], capture_output=True)
```

**Fix:**
```python
@app.post("/api/commit")
async def commit_build(req: CommitRequest):
    db = await get_db_conn()
    import subprocess, os

    git_dir = os.path.join(os.getcwd(), ".git")
    if not os.path.isdir(git_dir):
        raise HTTPException(status_code=400, detail="Not a git repository")

    cursor = await db.execute(
        "SELECT artifact_json FROM build_artifacts WHERE id=?",
        (req.build_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Build not found")

    build_data = json.loads(row["artifact_json"])

    # NEW: Validate build succeeded
    if build_data.get("status") != "success":
        raise HTTPException(status_code=400, detail="Cannot commit a failed build")

    artifact_files = build_data.get("files_created", []) + build_data.get("files_modified", [])
    
    # NEW: Validate commit message isn't empty
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Commit message cannot be empty")

    for f in artifact_files:
        subprocess.run(["git", "add", f], capture_output=True)

    result = subprocess.run(
        ["git", "commit", "-m", req.message],
        capture_output=True, text=True,
    )
    sha = result.stdout.strip() if result.returncode == 0 else ""
    await append_event(db, "commit_created", None, None,
                       {"build_id": req.build_id, "sha": sha})
    return {"commit_sha": sha, "success": result.returncode == 0}
```

---

### 3. Sandbox `build_tool_command` Returns `""` for Unknown Tools

**File:** `backend/orchestrator/sandbox.py:165-176`  
**Severity:** CRITICAL  
**Impact:** If the LLM somehow returns a tool not in `{curl, npm_view, web_search}`, the command becomes an empty string, causing silent failures.

**Current Code:**
```python
@staticmethod
def build_tool_command(tool: str, args: list[str]) -> str:
    if tool == "curl": ...
    elif tool == "npm_view": ...
    elif tool == "web_search": ...
    return ""  # Silent failure for unknown tools
```

**Fix:**
```python
@staticmethod
def build_tool_command(tool: str, args: list[str]) -> str:
    if tool == "curl":
        url = shlex.quote(args[0]) if args else ""
        return f"curl -sL --max-time 10 {url}"
    elif tool == "npm_view":
        pkg = shlex.quote(args[0]) if args else ""
        return f"npm view {pkg} --json 2>/dev/null"
    elif tool == "web_search":
        query = " ".join(shlex.quote(a) for a in args)
        return f'python3 -c "from duckduckgo_search import DDGS; print(list(DDGS().text({query}, max_results=5)))"'
    raise ValueError(f"Unknown tool: {tool}")
```

---

### 4. Database Connections Never Closed in FastAPI Lifecycle

**File:** `backend/orchestrator/gates.py:94-99`  
**Severity:** CRITICAL  
**Impact:** Each `get_db_conn()` call creates a new `aiosqlite.Connection`. If the endpoint is hit many times, open connections accumulate, causing "too many clients" or file descriptor exhaustion.

**Current Code:**
```python
_db = None
_db_path = db_path

async def get_db_conn():
    nonlocal _db
    if _db is None:
        _db = await get_db(_db_path)
        await init_db(_db)
    return _db
```

**Fix:** Use a lifespan handler to close on shutdown:
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = await get_db(db_path)
    await init_db(db)
    yield
    await db.close()

app = FastAPI(lifespan=lifespan)
```

---

## HIGH Priority Issues

### 5. Frontend `loading` State Not Reset on HandleReset

**File:** `frontend/src/App.tsx:113-120`  
**Severity:** HIGH  
**Impact:** If a user clicks "Start New" while an operation is in progress, `loading` remains True, disabling the Start button.

**Current Code:**
```typescript
const handleReset = () => {
    setStep('goal');
    setResult(null);
    ...
    // loading is NOT reset!
}
```

**Fix:**
```typescript
const handleReset = () => {
    setStep('goal');
    setResult(null);
    setPlan(null);
    setBuild(null);
    setTestReport(null);
    setCommitSha(null);
    setError(null);
    setLoading(false);  // NEW: Reset loading
}
```

---

### 6. Plan Error Handling Too Generic

**File:** `frontend/src/App.tsx:47-58`  
**Severity:** HIGH  
**Impact:** All errors show as "Plan failed", making debugging hard for users.

**Current Code:**
```typescript
} catch (e) {
    setError(e instanceof Error ? e.message : 'Plan failed')
}
```

**Fix:**
```typescript
} catch (e) {
    const message = e instanceof Error ? e.message : 'Plan failed';
    setError(message);
    if (message.includes('404')) {
        setError('Understanding not found. Please restart.');
    }
}
```

---

### 7. Test* Class Names Trigger PytestCollectionWarning

**File:** `backend/core/models.py:108,116,122`  
**Severity:** HIGH (Developer Experience)  
**Impact:** Pytest discovers `TestPlan`, `TestReport`, `TestResult` and issues warnings, creating noise in CI.

**Fix (Option 1 - Rename):** Rename to `QATestPlan`, `QATestReport`, `QATestResult` — but this is a breaking change.

**Fix (Option 2 - pytest.ini):**
```ini
[pytest]
python_classes = *Test
pythonpath = backend .
asyncio_mode = auto
```

**Recommended:** Option 2 first, but consider Option 1 for a cleaner codebase.

---

### 8. QAAgent Test Path May Allow Path Traversal

**File:** `backend/agents/qa.py:31-32`  
**Severity:** HIGH  
**Impact:** The QA agent runs `pytest` in the sandbox but passes `test_path` directly without validation.

**Current Code:**
```python
async def run_tests(self, build_id: str, test_path: str = "tests") -> TestReport:
    result = await self.sandbox.exec(f"python -m pytest {test_path} -v 2>&1")
    return self._parse_test_output(build_id, result["stdout"])
```

**Fix:**
```python
import re

async def run_tests(self, build_id: str, test_path: str = "tests") -> TestReport:
    if not re.match(r'^[\w./-]+$', test_path) or '..' in test_path or test_path.startswith('/'):
        raise ValueError(f"Invalid test path: {test_path}")
    result = await self.sandbox.exec(f"python -m pytest /workspace/{test_path} -v 2>&1")
    return self._parse_test_output(build_id, result["stdout"])
```

---

## MEDIUM Priority Issues

### 9. Fragility Check Doesn't Compare Against Canonical Result

**File:** `backend/agents/specialist.py:51-60`  
**Severity:** MEDIUM  
**Impact:** The `generate_with_fragility_check` compares 3 high-temp runs against each other, but NOT against the canonical low-temp result. A truly fragile run would differ from the canonical output.

**Current Code:**
```python
async def generate_with_fragility_check(self, goal: str) -> tuple[Understanding, bool]:
    result = await self.generate_understanding(goal)
    sets = []
    for _ in range(3):
        s = await self._single_understanding(goal, temperature=0.7)
        sets.append(s)
    first_set = sets[0]
    fragile = any(s != first_set for s in sets[1:])
    return result, fragile
```

**Fix:**
```python
async def generate_with_fragility_check(self, goal: str) -> tuple[Understanding, bool]:
    result = await self.generate_understanding(goal)
    canonical_assumptions = {a.statement for a in result.assumptions}
    sets = []
    for _ in range(3):
        s = await self._single_understanding(goal, temperature=0.7)
        sets.append(s)
    fragile = any(s != canonical_assumptions for s in sets)
    return result, fragile
```

---

### 10. Sandbox Exec Demux Check Redundant

**File:** `backend/orchestrator/sandbox.py:76-81`  
**Severity:** MEDIUM  
**Impact:** `isinstance(raw_output, tuple)` is checked but `demux=True` is already specified, so it's always a tuple.

**Fix:** Remove redundant check:
```python
exit_code, raw_output = container.exec_run(
    ["/bin/sh", "-c", command],
    demux=True,
)
assert isinstance(raw_output, tuple), "demux=True should always return tuple"
stdout = raw_output[0].decode("utf-8", errors="replace") if raw_output[0] else ""
stderr = raw_output[1].decode("utf-8", errors="replace") if raw_output[1] else ""
```

---

### 11. Audit Events Missing Database Index

**File:** `backend/orchestrator/database.py`  
**Severity:** MEDIUM  
**Impact:** As the event log grows, `get_events` with `ORDER BY created_at` will get progressively slower without an index.

**Fix:**
```python
await db.execute("CREATE INDEX IF NOT EXISTS idx_events_created_at ON audit_events(created_at)")
```

---

### 12. No Circuit Breaker for OllamaClient

**File:** `backend/agents/specialist.py:10-17`  
**Severity:** MEDIUM  
**Impact:** If Ollama is down, agents retry in a tight loop, causing cascading failures.

**Fix:** Add retry with exponential backoff and failure threshold. (This is a design decision; document the need for a circuit breaker library like `pybreaker`.)

---

## LOW Priority Issues

### 13. `_exec_with_retry` is Misleading

**File:** `backend/agents/builder.py:68-73`  
**Severity:** LOW  
**Impact:** The name suggests it keeps trying until success. It should either succeed or raise.

**Fix:** Rename to `_exec_with_retry_or_raise` or actually implement backoff.

---

### 14. TestPlan.build_id is Optional (allows empty string)

**File:** `backend/core/models.py:108`  
**Severity:** LOW  
**Impact:** If `build_id` is empty or not set by the caller, models like `TestPlan` still default to empty values silently.

**Fix:**
```python
class TestPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    build_id: str = Field(min_length=1)  # Require non-empty
    ...
```

---

## Summary Table

| # | Issue | File | Severity | Fix Effort |
|---|---|---|---|---|
| 1 | BuilderAgent ignores sandbox failures | `builder.py:68` | CRITICAL | 30 min |
| 2 | Commit allows failed builds | `gates.py:222` | CRITICAL | 15 min |
| 3 | Unknown tools return empty string | `sandbox.py:165` | CRITICAL | 5 min |
| 4 | DB connections never closed | `gates.py:94` | CRITICAL | 20 min |
| 5 | Frontend loading not reset on reset | `App.tsx:113` | HIGH | 5 min |
| 6 | Plan error handling too generic | `App.tsx:47` | HIGH | 10 min |
| 7 | Test* class names trigger warnings | `models.py` | HIGH | 5 min |
| 8 | QAAgent test path traversal risk | `qa.py:31` | HIGH | 15 min |
| 9 | Fragility check vs canonical | `specialist.py:51` | MEDIUM | 15 min |
| 10 | Sandbox exec demux redundant | `sandbox.py:76` | MEDIUM | 10 min |
| 11 | Audit events no index | `database.py` | MEDIUM | 5 min |
| 12 | No circuit breaker | `specialist.py:10` | MEDIUM | 30 min |
| 13 | `_exec_with_retry` misnamed | `builder.py:68` | LOW | 5 min |
| 14 | TestPlan.build_id optional | `models.py:108` | LOW | 5 min |

---

## New Tests Written

| File | Tests | Coverage |
|---|---|---|
| `tests/test_stress_skeptic.py` | 8 | ReAct loop edge cases |
| `tests/test_stress_endpoints.py` | 8 | API stress & concurrency |
| `tests/test_stress_sandbox.py` | 6 | Sandbox stress & race conditions |

---

## Next Steps

1. **Immediate (this hour):** Fix issues #1, #3, #4 (CRITICAL)
2. **Today:** Fix issues #2, #5, #8 (HIGH)
3. **This sprint:** Fix issues #6, #7, #9, #10, #12 (MEDIUM)
4. **Backlog:** Fix issues #11, #13, #14 (LOW)

---

## Verification

Run all tests after fixing:
```bash
pytest -q
```
