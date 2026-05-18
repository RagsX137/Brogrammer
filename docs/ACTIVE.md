# ACTIVE WORKING MEMORY – Phase 2: Learning & State-Drift Prevention

> **Phase 2 deliverable #1: Skeptic tool access is COMPLETE.**
> See MODULES.md for full phase status.

---

## Phase Goal

Give the SkepticAgent real tool access (curl, npm_view, web_search) via a ReAct loop
inside the Docker sandbox. Sets the stage for assumption regression checks on commits.

---

## Deliverables Complete

- [x] ToolRequest, ToolResult, SkepticOutput data models (core/models.py)
- [x] Sandbox tool installation + exec_safe + build_tool_command (orchestrator/sandbox.py)
- [x] SkepticAgent ReAct loop with up to 4 tool rounds (agents/skeptic.py)
- [x] Sandbox wired into Skeptic via gates.py
- [x] 128 passing tests (pytest)
- [x] ReAct loop falls back to single-round when sandbox is None (backward compatible)

---

## Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tool loop pattern | ReAct (max 4 rounds) | Adaptive investigation; works with any LLM via JSON-mode parsing |
| Tool execution | Docker sandbox (SandboxManager.exec) | Already exists from Phase 1, provides isolation |
| Web search | duckduckgo-search Python library | No API key required, works in sandbox |
| Sandbox fallback | Old single-round prompt when sandbox=None | Backward compatible, no tool definitions leaked |
| Frontend changes | None needed | CritiquePanel already renders tool_evidence |

---

## Next Up

- **Assumption regression checks on commits** — Phase 2 deliverable #2
