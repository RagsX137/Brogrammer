# Phase 1 Fixes — Devil's Advocate Review

> **Status:** Open issues identified during Phase 1 verification
> **Review Date:** 2025-05-18
> **Model:** gemma4:latest

## CRITICAL Issues

### 1. Git Commit Endpoint Security Flaw
**File:** `backend/orchestrator/gates.py` (line 197)
**Issue:** The `commit_build` endpoint executes `subprocess.run(["git", "add", "-A"])` with no path validation. It commits the *entire repository* rather than just the artifact, and will fail if `git` is not initialized.
**Impact:** Calling this endpoint will stage and commit all modifications in the working tree, potentially including sensitive files.
**Fix:**
1. Create a temporary or isolated directory for the build artifact.
2. Initialize a `git` repository there if it doesn't exist.
3. Only add and commit files within that specific path.
4. Return a clear error if no git repository is found.

### 2. BuilderAgent Path Handling Bug
**File:** `backend/agents/builder.py` (line 34)
**Issue:** `file_spec.path.rsplit("/", 1)[0]` fails for paths with multiple directories (e.g., `src/components/main.py`). For a single-level path like `main.py`, it returns `'.'`, which is ambiguous.
**Impact:** Incorrect directory creation and file writing in the Docker sandbox.
**Fix:** Use `os.path.dirname` or `pathlib.Path(file_spec.path).parent`.

### 3. PlannerAgent Error Handling Gap
**File:** `backend/agents/planner.py` (line 26)
**Issue:** The retry loop catches `json.JSONDecodeError` for 3 attempts but does not catch `ConnectionError`, `TimeoutError`, or other network-related exceptions.
**Impact:** If the Ollama server is unreachable, the application will crash.
**Fix:** Add a more robust retry mechanism that catches `ConnectionError` and `TimeoutError`, or implement a circuit breaker.

### 4. SandboxManager exec() Demux Check
**File:** `backend/orchestrator/sandbox.py` (line 47)
**Issue:** The `exec` method uses `demux=True` and then checks `isinstance(output, tuple)`. This is redundant because `demux=True` always returns a tuple.
**Impact:** This indicates a lack of testing and is a code smell.
**Fix:** Simplify the `exec` method to assert the type of `output` directly.

## HIGH Priority Issues

### 5. Database Schema - Missing Foreign Key Constraints
**File:** `backend/orchestrator/database.py`
**Issue:** The tables `tech_plans`, `build_artifacts`, and `test_reports` have related columns (e.g., `build_artifacts.plan_id`), but there are no foreign key constraints.
**Impact:** Referential integrity is not enforced. You can create a `build_artifact` with a non-existent `plan_id`.
**Fix:** Add `FOREIGN KEY` constraints and ensure `PRAGMA foreign_keys` is enabled during database initialization.

### 6. Missing Input Validation for Stored JSON
**File:** `backend/core/models.py`
**Issue:** The `TechPlan`, `BuildArtifact`, and `TestReport` objects are stored as JSON in `TEXT` columns. There is no validation that the JSON is a valid instance of the model before insertion.
**Impact:** Corrupt or malformed data can be inserted into the database.
**Fix:** Use `TechPlan.model_validate_json()` or similar Pydantic validators in the API layer before database insertion.

### 7. API Pagination Missing
**File:** `backend/orchestrator/gates.py` (line 144)
**Issue:** The `/api/audit/events` endpoint returns a maximum of 50 events with no `offset` or `cursor` parameter.
**Impact:** This will be a performance bottleneck as the number of events grows.
**Fix:** Implement cursor-based pagination using the `created_at` and `id` columns.

## MEDIUM Priority Issues

### 8. No Input Validation for Empty/Whitespace Goals
**File:** `backend/orchestrator/gates.py` (line 17)
**Issue:** The `RunLoopRequest` model has `goal: str` without a `strip()` check or `min_length` constraint.
**Impact:** Empty goals will be passed to the LLM, causing unexpected behavior.
**Fix:**
1. Add `Field(min_length=1)` and a custom validator.
2. Strip whitespace from the goal before processing.

### 9. Frontend State Management is Volatile
**File:** `frontend/src/App.tsx`
**Issue:** The application state is stored in `useState` and is lost on page refresh.
**Impact:** If a user refreshes, they must restart the entire gate flow.
**Fix:** Store the current gate step and in-progress data in `localStorage` or persist it on the backend.

### 10. Missing React Error Boundaries
**File:** `frontend/src/App.tsx`
**Issue:** There are no error boundaries in the React application.
**Impact:** Any unhandled exception will crash the entire application with a blank screen.
**Fix:** Implement a `React.ErrorBoundary` component to log errors and show a user-friendly fallback UI.

### 11. Hardcoded API Base URL
**File:** `frontend/src/api.ts`
**Issue:** The `API_BASE` is hardcoded to `/api`.
**Impact:** The frontend cannot be deployed or tested against a different backend URL.
**Fix:** Use an environment variable like `import.meta.env.VITE_API_BASE` for the base URL.

## LOW Priority Issues

### 12. No Rate Limiting
**File:** `backend/orchestrator/gates.py`
**Issue:** There is no rate limiting on any of the API endpoints.
**Fix:** Implement rate limiting using `slowapi` or FastAPI middleware.

### 13. Missing Health Check Endpoint
**File:** `backend/orchestrator/gates.py`
**Issue:** There is no `/health` or `/ping` endpoint for monitoring.
**Fix:** Add a `/health` endpoint that checks the database and Ollama connection.

### 14. PytestCollectionWarning for Test* Models
**File:** `backend/core/models.py`
**Issue:** Classes `TestPlan`, `TestReport`, and `TestResult` cause pytest warnings in test discovery.
**Impact:** This is a minor developer experience issue and can lead to false positives.
**Fix:** Either rename the classes to non-prefixed names or add a pytest configuration to ignore them.
