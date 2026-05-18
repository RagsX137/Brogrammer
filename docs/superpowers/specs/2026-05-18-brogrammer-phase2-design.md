# Brogrammer Phase 2: Learning & State-Drift Prevention — Design Spec

> Gives the SkepticAgent real tool access (curl, npm view, web search) via a ReAct loop
> inside the Docker sandbox. Sets the stage for assumption regression checks on commits.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Order of delivery | Skeptic tools first, then assumption regression | Tools power the regression checks; build the foundation first |
| Tool loop pattern | ReAct (max 4 rounds) | Lets Skeptic investigate adaptively; works with any LLM via JSON-mode parsing |
| Tool execution | Docker sandbox (`SandboxManager.exec`) | Already exists from Phase 1, provides isolation, same pattern as Builder |
| Web search | `duckduckgo-search` Python library | No API key required, works in sandbox, returns structured results |
| Frontend changes | Minimal — `tool_evidence` already rendered | No new components or endpoints |
| API changes | Minimal — sandbox injected into SkepticAgent | No new endpoints; ReAct loop runs synchronously inside `/api/run-loop` |

## Architecture

```
Understanding (from Specialist)
        │
        ▼
┌─────────────────┐     4 rounds max
│  SkepticAgent   │◄────────────┐
│  ReAct Loop      │──────┐     │
└────────┬────────┘      │     │
         │ tool_requests  │     │
         ▼                │     │
┌─────────────────┐      │     │
│ SandboxManager  │──────┘     │
│ exec_safe()     │ tool result │
└─────────────────┘            │
         │                     │
         ▼                     │
  Final SkepticCritique ───────┘
  (tool_evidence populated)
```

## Directory Layout (new/changed files)

```
backend/
├── core/
│   ├── models.py              ← ADD: ToolRequest, ToolResult, SkepticOutput
│   └── confidence.py          (unchanged)
├── agents/
│   ├── specialist.py          (unchanged)
│   ├── skeptic.py             ← MODIFY: ReAct loop, tool definitions in prompt
│   ├── planner.py             (unchanged)
│   ├── builder.py             (unchanged)
│   └── qa.py                  (unchanged)
├── orchestrator/
│   ├── database.py            (unchanged)
│   ├── audit.py               (unchanged)
│   ├── gates.py               ← MODIFY: pass sandbox to Skeptic.generate_critique
│   ├── sandbox.py             ← MODIFY: add install_tools(), exec_safe()
│   └── __init__.py            (unchanged)
├── main.py                    (unchanged)
tests/
├── test_agents.py             ← MODIFY: add Skeptic ReAct loop tests
├── test_sandbox.py            ← MODIFY: add tool execution tests
└── test_integration.py        (unchanged — no new endpoints)
frontend/                      (unchanged — CritiquePanel already renders tool_evidence)
```

## New Data Contracts

### `backend/core/models.py` additions

```python
class ToolRequest(BaseModel):
    tool: Literal["curl", "npm_view", "web_search"]
    args: list[str] = []
    description: str = ""

class ToolResult(BaseModel):
    tool: str
    args: list[str]
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0

class SkepticOutput(BaseModel):
    tool_requests: list[ToolRequest] = []
    scenarios: list[str] = []
    questions: list[str] = []
    tool_evidence: list[str] = []
    thought: str = ""
```

## Sandbox Changes (`backend/orchestrator/sandbox.py`)

### New method: `exec_safe(command, timeout=15)`

Wraps `exec()` with a shorter timeout suitable for quick tool calls (curl, npm view, web search). Builder's existing `exec()` calls retain their 120s timeout.

### New method: `install_tools()`

Runs at sandbox `start()` to install prerequisites:

```bash
apt-get update -qq && apt-get install -y -qq curl nodejs npm
pip install duckduckgo-search
```

Installed only once per container lifecycle. If the container already has tools (e.g. from a custom image), `install_tools()` is a no-op.

### Tool command generation

```python
def build_tool_command(tool: str, args: list[str]) -> str:
    if tool == "curl":
        return f"curl -sL --max-time 10 {' '.join(shlex.quote(a) for a in args)}"
    elif tool == "npm_view":
        return f"npm view {shlex.quote(args[0])} --json 2>/dev/null"
    elif tool == "web_search":
        # Uses duckduckgo-search CLI installed via pip
        return f"python3 -m duckduckgo_search {' '.join(shlex.quote(a) for a in args)}"
```

## SkepticAgent ReAct Loop (`backend/agents/skeptic.py`)

### System Prompt additions

Added after the existing critique instructions:

```
You have access to the following tools to investigate your doubts
before reporting them. Use them to gather real evidence.

TOOLS:
  curl <url>       — Make HTTP requests to check APIs, services, documentation
  npm_view <pkg>   — Check npm package metadata (version, size, dependencies)
  web_search <q>   — Search the web for information

You have up to 4 rounds of tool use. When you need evidence, output:
{"tool_requests": [{"tool": "curl", "args": ["https://..."], "description": "why"}],
 "thought": "your reasoning"}

When you have enough evidence, output the final critique:
{"scenarios": [...], "questions": [...], "tool_evidence": [...]}
```

### `generate_critique(understanding, sandbox=None)` logic

```
1. Build initial message list with Understanding + tool definitions
2. For round in 1..4:
   a. Call ollama.chat(messages, format="json", temperature=0.3)
   b. Parse response as SkepticOutput
   c. If output.tool_requests and sandbox is available:
      - For each request: exec in sandbox, append result message
      - Continue to next round
   d. Else: this is the final critique
      - Return SkepticCritique with tool_evidence from output
3. If 4 rounds exhausted without final output, force finalize
```

When `sandbox` is None (tests, or tool access disabled), the Skeptic skips the ReAct loop and produces the critique in a single call — same as Phase 1 behavior.

## API / Orchestrator Changes

In `gates.py`:

```python
# Before:
critique = await _skeptic.generate_critique(understanding)

# After:
critique = await _skeptic.generate_critique(understanding, sandbox=shared_sandbox)
```

The `/api/run-loop` endpoint returns the same structure as before — the only difference is `critique.tool_evidence` now contains real command outputs instead of LLM-hallucinated ones.

## Frontend Changes

None required. The `CritiquePanel` component already renders `critique.tool_evidence` as a list of strings. Real evidence from tool execution will show up automatically.

## Testing

### New/Modified tests in `tests/test_agents.py`

```
test_skeptic_react_loop_full       — 4-round loop: tool request → tool result → final critique
test_skeptic_react_loop_no_tools   — 0 tools needed, single-round path
test_skeptic_react_loop_no_sandbox — Falls back to single-round when sandbox=None
test_skeptic_tool_parsing          — ToolRequest JSON parsing
test_skeptic_react_exhausted       — 4 rounds exhausted, forced finalization
```

### New tests in `tests/test_sandbox.py`

```
test_sandbox_install_tools    — install_tools() succeeds (requires Docker)
test_sandbox_exec_curl        — curl command inside sandbox (requires Docker)
test_sandbox_exec_safe_timeout — exec_safe respects shorter timeout (requires Docker)
```

### FakeOllamaClient for tool loop

```python
class SkepticReActFakeClient:
    def __init__(self):
        self.call_count = 0

    async def chat(self, messages, format="", temperature=0.0):
        self.call_count += 1
        if self.call_count == 1:
            # Round 1: request a tool
            content = '{"tool_requests": [{"tool": "curl", "args": ["https://example.com"], "description": "Check endpoint"}], "thought": "Investigating"}'
        elif self.call_count == 2:
            # Round 2: final critique with evidence
            content = '{"scenarios": ["API could be down"], "questions": [], "tool_evidence": ["curl https://example.com → 200 OK (0.4s)"]}'
        return {"message": {"content": content}}
```

## Error Handling

| Scenario | Behavior |
|---|---|
| Tool command times out | Return `ToolResult(exit_code=124, stderr="Timed out")`, continue loop |
| Tool not installed | Auto-install on first use, retry |
| Sandbox not running | Skip ReAct loop, single-round fallback |
| JSON parse failure | Retry same round (max 2×), then abort loop and use what we have |
| Ollama client error | Bubbles up to `/api/run-loop` HTTP 500 |
| 4 rounds exhausted | Force-finalize with whatever evidence gathered |

## Out of Scope (Phase 2)

- Assumption regression checks on commits (Phase 2.5 — comes after tools are stable)
- CI/CD, production deployment, store configuration (Phase 3)
- Streaming tool execution progress to frontend (future improvement)
- ChromaDB / vector store (future)
- PostgreSQL (future)

## Phase 2 Completion Criteria

- [ ] SkepticAgent runs up to 4-round ReAct loop when sandbox is available
- [ ] `curl`, `npm_view`, `web_search` tools execute inside Docker sandbox
- [ ] Tool output propagates to `SkepticCritique.tool_evidence` in `/api/run-loop` response
- [ ] Fallback to single-round when sandbox is None (backward compatible)
- [ ] All existing 79 tests still pass
- [ ] New ReAct loop tests pass with `FakeOllamaClient`
- [ ] Docker-requiring tool tests pass (CI with Docker)
