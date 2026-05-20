# Completed Tasks

> Append-only. Never delete rows. Format: `| Task ID | Phase | Description | Date |`

| Task ID | Phase | Description | Date |
|---|---|---|---|---|---|
| P0-001 | 0 | Project scaffold (pyproject.toml, __init__.py, conftest.py) | 2026-05-17 |
| P1-001 | 1 | docker-py dependency added | 2026-05-18 |
| P1-002 | 1 | Phase 1 data models (TechPlan, BuildArtifact, TestReport) | 2026-05-18 |
| P1-003 | 1 | Docker SandboxManager with exec lifecycle | 2026-05-18 |
| P1-004 | 1 | PlannerAgent with retry logic | 2026-05-18 |
| P1-005 | 1 | BuilderAgent with Docker sandbox code generation | 2026-05-18 |
| P1-006 | 1 | QAAgent with test plan generation and execution | 2026-05-18 |
| P1-007 | 1 | Database tables (tech_plans, build_artifacts, test_reports) | 2026-05-18 |
| P1-008 | 1 | Full Understanding stored in audit event payload | 2026-05-18 |
| P1-009 | 1 | Phase 1 gate endpoints (/api/plan, /api/build, /api/test, /api/commit) | 2026-05-18 |
| P1-010 | 1 | Frontend API client updates | 2026-05-18 |
| P1-011 | 1 | TechPlanView component | 2026-05-18 |
| P1-012 | 1 | BuildView component with Docker logs | 2026-05-18 |
| P1-013 | 1 | TestReportView component | 2026-05-18 |
| P1-014 | 1 | Multi-step gate flow App.tsx | 2026-05-18 |
| P1-015 | 1 | CSS for Phase 1 components | 2026-05-18 |
| P1-016 | 1 | Integration tests with mock agents | 2026-05-18 |
| P1-017 | 1 | Final verification (79 tests pass, TS clean) | 2026-05-18 |
| P0-002 | 0 | Core data models (models.py) | 2026-05-17 |
| P0-003 | 0 | Confidence formula (confidence.py) | 2026-05-17 |
| P0-004 | 0 | SQLite audit log (database.py, audit.py) | 2026-05-17 |
| P0-005 | 0 | SpecialistAgent with Ollama (specialist.py) | 2026-05-17 |
| P0-006 | 0 | SkepticAgent with Ollama (skeptic.py) | 2026-05-17 |
| P0-007 | 0 | FastAPI orchestrator (gates.py, main.py) | 2026-05-17 |
| P0-008 | 0 | Frontend scaffold (Vite + React + TypeScript) | 2026-05-17 |
| P0-009 | 0 | Frontend components (UnderstandingView, CritiquePanel, ConfidenceBadge) | 2026-05-17 |
| P0-010 | 0 | Final integration test & verification | 2026-05-17 |
| TASK-X1 | X | Centralized retry helper (_retry.py) | 2026-05-20 |
| P0-F01 | 0 | SpecialistAgent retry loop (wraps generate_understanding + _single_understanding) | 2026-05-20 |
| P0-F02 | 0 | Fragility detection: 3-call → 1-resample with deterministic comparison | 2026-05-20 |
| P0-F03 | 0 | SkepticAgent no-sandbox retry (_generate_no_sandbox with @with_retries) | 2026-05-20 |
| P0-F04 | 0 | Persist tool_evidence + rounds_used + tool_calls in audit payload | 2026-05-20 |
| P0-F05 | 0 | RunLoopRequest.goal validation (min_length, max_length=10k, whitespace strip) | 2026-05-20 |
| P0-F06 | 0 | Audit events ORDER BY DESC + cursor pagination (before= param) | 2026-05-20 |
| P0-F07 | 0 | Frontend VITE_API_BASE from env with fallback to '/api' | 2026-05-20 |
| P1-F01 | 1 | QA writes test files to sandbox (write_test_files + contents dict) | 2026-05-20 |
| P1-F02 | 1 | Bind-mount host dir at /workspace so build artifacts survive on host | 2026-05-20 |
| P1-F03 | 1 | Base64-encoded file write (replaces fragile heredoc) | 2026-05-20 |
| P1-F04 | 1 | commit_build safety: empty artifact 400, git add rc check, rev-parse SHA, message validation | 2026-05-20 |
| P1-F05 | 1 | exec_safe passes timeout param instead of mutating instance state | 2026-05-20 |
| P1-F06 | 1 | Shutdown handler + periodic orphan cleanup (SANDBOX_CLEANUP_INTERVAL) | 2026-05-20 |
| P2-F01 | 2 | URL denylist + optional SKEPTIC_CURL_ALLOWLIST on curl tool | 2026-05-20 |
| P2-F02 | 2 | ReAct JSON errors surfaced as tool_evidence, force-finalize after 2 consecutive failures | 2026-05-20 |
| P2-F03 | 2 | install_tools probes (which curl/npm, import duckduckgo_search) after install | 2026-05-20 |
| P2-F05 | 2 | rounds_used + tool_calls fields on SkepticCritique model | 2026-05-20 |
| TASK-X5 | X | Suppress PytestCollectionWarning via filterwarnings in pytest.ini | 2026-05-20 |
| P2-F04 | 2 | Pre-warmed sandbox Dockerfile + build script + image fallback | 2026-05-20 |
| P2-F06 | 2 | tool_call_events table + per-call audit + /api/critique/{id}/tools endpoint | 2026-05-20 |
| TASK-X3 | X | Real-LLM smoke tests gated by RUN_REAL_LLM=1 env | 2026-05-20 |
| TASK-X2 | X | Structured logging module (JSON/pretty) + log calls in gates.py | 2026-05-20 |
| TASK-X4 | X | slowapi rate limiting (configurable per-endpoint, noop in tests) | 2026-05-20 |
| P1-F07 | 1 | Frontend ErrorBoundary + localStorage persistence + hydration | 2026-05-20 |
| TASK-X6 | X | Failure modes and degradation section in ARCHITECTURE.md | 2026-05-20 |
