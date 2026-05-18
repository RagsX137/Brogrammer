# Phase 2: Skeptic Tool Access — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the SkepticAgent a ReAct loop with real tool access (curl, npm_view, web_search) inside the Docker sandbox.

**Architecture:** Add `ToolRequest`/`ToolResult`/`SkepticOutput` models to `models.py`. Add `install_tools()` and `exec_safe()` to `SandboxManager`. Refactor `SkepticAgent.generate_critique` into a multi-turn ReAct loop (max 4 rounds). Inject the sandbox from `gates.py`.

**Tech Stack:** Python, Pydantic v2, docker-py, duckduckgo-search

---

### Task 1: Add Phase 2 data models

**Files:**
- Modify: `backend/core/models.py` — append after existing models

- [ ] **Step 1: Write the failing test**

Add to `tests/test_models.py`:

```python
def test_tool_request_defaults():
    tr = ToolRequest(tool="curl", args=["https://example.com"])
    assert tr.tool == "curl"
    assert tr.args == ["https://example.com"]
    assert tr.description == ""


def test_tool_request_literal_validation():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ToolRequest(tool="invalid_tool", args=[])


def test_tool_result_defaults():
    tr = ToolResult(tool="curl", args=["https://example.com"])
    assert tr.tool == "curl"
    assert tr.stdout == ""
    assert tr.stderr == ""
    assert tr.exit_code == 0


def test_skeptic_output_forward():
    so = SkepticOutput(
        scenarios=["API could be down"],
        tool_evidence=["curl returned 200"],
    )
    assert len(so.scenarios) == 1
    assert len(so.tool_evidence) == 1
    assert so.tool_requests == []


def test_skeptic_output_with_tool_requests():
    so = SkepticOutput(
        tool_requests=[ToolRequest(tool="curl", args=["https://api.example.com"], description="Check endpoint")],
    )
    assert len(so.tool_requests) == 1
    assert so.tool_requests[0].tool == "curl"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py::test_tool_request_defaults tests/test_models.py::test_tool_request_literal_validation tests/test_models.py::test_tool_result_defaults tests/test_models.py::test_skeptic_output_forward tests/test_models.py::test_skeptic_output_with_tool_requests -v
```

Expected: 5 FAILED (ImportError for ToolRequest/ToolResult/SkepticOutput).

- [ ] **Step 3: Add the models**

Add to `backend/core/models.py` after the `TestReport` class (before EOF):

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

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_models.py::test_tool_request_defaults tests/test_models.py::test_tool_request_literal_validation tests/test_models.py::test_tool_result_defaults tests/test_models.py::test_skeptic_output_forward tests/test_models.py::test_skeptic_output_with_tool_requests -v
```

Expected: 5 PASSED.

- [ ] **Step 5: Run full model tests to confirm no regressions**

```bash
pytest tests/test_models.py -v
```

Expected: All tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add tests/test_models.py backend/core/models.py
git commit -m "feat: add Phase 2 data models (ToolRequest, ToolResult, SkepticOutput)"
```

---

### Task 2: Add sandbox tool execution methods

**Files:**
- Modify: `backend/orchestrator/sandbox.py` — add `install_tools()`, `exec_safe()`, `build_tool_command()`

- [ ] **Step 1: Add imports and new methods to SandboxManager**

Add at the top of `backend/orchestrator/sandbox.py`:

```python
import shlex
```

Add inside `SandboxManager` class, after `cleanup_orphans`:

```python
    TOOLS_INSTALLED_ATTR = "_tools_installed"

    async def install_tools(self) -> None:
        if getattr(self, self.TOOLS_INSTALLED_ATTR, False):
            return
        cmds = [
            "apt-get update -qq && apt-get install -y -qq curl nodejs npm 2>/dev/null",
            "pip install duckduckgo-search -q 2>/dev/null",
        ]
        for cmd in cmds:
            await self.exec(cmd)
        setattr(self, self.TOOLS_INSTALLED_ATTR, True)

    async def exec_safe(self, command: str, timeout: int = 15) -> dict:
        original_timeout = self.exec_timeout
        self.exec_timeout = timeout
        try:
            return await self.exec(command)
        finally:
            self.exec_timeout = original_timeout

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
        return ""
```

- [ ] **Step 2: Write tool execution tests**

Add to `tests/test_sandbox.py` at the end:

```python
@pytest.mark.asyncio
async def test_sandbox_install_tools():
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    from backend.orchestrator.sandbox import SandboxManager
    mgr = SandboxManager()
    await mgr.start()
    await mgr.install_tools()
    # Verify curl is installed
    result = await mgr.exec("which curl")
    assert result["exit_code"] == 0
    assert "curl" in result["stdout"]
    await mgr.stop()


@pytest.mark.asyncio
async def test_sandbox_exec_safe_timeout():
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    from backend.orchestrator.sandbox import SandboxManager
    mgr = SandboxManager()
    await mgr.start()
    with pytest.raises(RuntimeError, match="timed out"):
        await mgr.exec_safe("sleep 30", timeout=2)
    await mgr.stop()
```

- [ ] **Step 3: Run tests to verify they pass (Docker required)**

```bash
pytest tests/test_sandbox.py::test_sandbox_install_tools tests/test_sandbox.py::test_sandbox_exec_safe_timeout -v
```

Expected: 2 PASSED (or SKIPPED if Docker not available).

- [ ] **Step 4: Run all sandbox tests for regressions**

```bash
pytest tests/test_sandbox.py -v
```

Expected: All tests PASSED or SKIPPED (Docker check).

- [ ] **Step 5: Commit**

```bash
git add backend/orchestrator/sandbox.py tests/test_sandbox.py
git commit -m "feat: add sandbox tool execution (install_tools, exec_safe, build_tool_command)"
```

---

### Task 3: Implement SkepticAgent ReAct loop

**Files:**
- Modify: `backend/agents/skeptic.py` — multi-turn tool loop
- Test: `tests/test_agents.py` — add ReAct loop tests

- [ ] **Step 1: Write the failing ReAct loop tests**

Add to `tests/test_agents.py` at the end:

```python
class SkepticReActFakeClient:
    def __init__(self):
        self.call_count = 0

    async def chat(self, messages: list[dict], format: str = "", temperature: float = 0.0):
        self.call_count += 1
        if self.call_count == 1:
            content = (
                '{"tool_requests": [{"tool": "curl", "args": ["https://example.com"], '
                '"description": "Check endpoint"}], '
                '"thought": "Need to verify if this API exists"}'
            )
        else:
            content = (
                '{"scenarios": ["API could be unreachable"], '
                '"questions": ["Should we add offline fallback?"], '
                '"tool_evidence": ["curl https://example.com → 200 OK (0.4s)"]}'
            )
        return {"message": {"content": content}}


class SkepticNoToolFakeClient:
    async def chat(self, messages: list[dict], format: str = "", temperature: float = 0.0):
        return {
            "message": {
                "content": (
                    '{"scenarios": ["Users might not like it"], '
                    '"questions": ["Should we A/B test?"], '
                    '"tool_evidence": []}'
                )
            }
        }


@pytest.mark.asyncio
async def test_skeptic_react_loop_with_tools():
    from backend.agents.skeptic import SkepticAgent
    agent = SkepticAgent(ollama_client=SkepticReActFakeClient())
    understanding = Understanding(
        goal="Check API availability",
        assumptions=[Assumption(statement="API is public")],
        unknowns=[Unknown(question="What URL?")],
        mandatory_categories=MandatoryCategories(),
    )
    critique = await agent.generate_critique(understanding, sandbox=True)
    assert critique.understanding_id == understanding.id
    assert len(critique.tool_evidence) == 1
    assert "curl" in critique.tool_evidence[0]


@pytest.mark.asyncio
async def test_skeptic_react_loop_no_tools_needed():
    from backend.agents.skeptic import SkepticAgent
    agent = SkepticAgent(ollama_client=SkepticNoToolFakeClient())
    understanding = Understanding(
        goal="Simple app",
        assumptions=[Assumption(statement="It works")],
        unknowns=[],
        mandatory_categories=MandatoryCategories(),
    )
    critique = await agent.generate_critique(understanding, sandbox=True)
    assert len(critique.scenarios) == 1
    assert len(critique.tool_evidence) == 0


@pytest.mark.asyncio
async def test_skeptic_react_loop_fallback_no_sandbox():
    """When sandbox is None, should use single-round path."""
    from backend.agents.skeptic import SkepticAgent
    agent = SkepticAgent(ollama_client=SkepticReActFakeClient())
    understanding = Understanding(
        goal="Check API availability",
        assumptions=[Assumption(statement="API is public")],
        unknowns=[Unknown(question="What URL?")],
        mandatory_categories=MandatoryCategories(),
    )
    critique = await agent.generate_critique(understanding, sandbox=None)
    assert critique.understanding_id == understanding.id
    assert len(critique.tool_evidence) == 0  # No tools without sandbox


@pytest.mark.asyncio
async def test_skeptic_react_loop_exhausted():
    """After 4 tool-request rounds, should force-finalize."""
    from backend.agents.skeptic import SkepticAgent

    class AlwaysRequestTool:
        def __init__(self):
            self.call_count = 0

        async def chat(self, messages, format="", temperature=0.0):
            self.call_count += 1
            return {
                "message": {
                    "content": (
                        '{"tool_requests": [{"tool": "curl", "args": ["https://example.com"], '
                        '"description": "Keep checking"}], '
                        '"thought": "Still investigating"}'
                    )
                }
            }

    agent = SkepticAgent(ollama_client=AlwaysRequestTool())
    understanding = Understanding(
        goal="Test",
        assumptions=[],
        unknowns=[],
        mandatory_categories=MandatoryCategories(),
    )
    critique = await agent.generate_critique(understanding, sandbox="mock")
    assert critique is not None
    assert len(critique.scenarios) == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_agents.py::test_skeptic_react_loop_with_tools tests/test_agents.py::test_skeptic_react_loop_no_tools_needed tests/test_agents.py::test_skeptic_react_loop_fallback_no_sandbox tests/test_agents.py::test_skeptic_react_loop_exhausted -v
```

Expected: 4 FAILED.

- [ ] **Step 3: Implement the ReAct loop**

Rewrite `backend/agents/skeptic.py` entirely:

```python
import json
from backend.core.models import Understanding, SkepticCritique, ToolRequest, ToolResult, SkepticOutput
from backend.agents.specialist import OllamaClient

TOOL_DEFINITIONS = """
You have access to the following tools to investigate your doubts before reporting them.
Use them to gather real evidence before finalizing your critique.

TOOLS:
  curl <url>       — Make HTTP requests to check APIs, services, documentation
  npm_view <pkg>   — Check npm package metadata (version, size, dependencies)
  web_search <q>   — Search the web for information

When you need to investigate, output:
{"tool_requests": [{"tool": "<tool_name>", "args": ["arg1"], "description": "why"}],
 "thought": "your reasoning"}

When you have enough evidence, output the final critique:
{"scenarios": [...], "questions": [...], "tool_evidence": [...], "thought": ""}

You can use up to 4 rounds of tool investigation.
"""


class SkepticAgent:
    MAX_TOOL_ROUNDS = 4

    def __init__(self, ollama_client: OllamaClient | None = None):
        self.ollama = ollama_client or OllamaClient()
        self.system_prompt = (
            "You are the SkepticAgent. Given an Understanding document, produce a critique. "
            "Return ONLY valid JSON — no markdown, no explanation. "
            'Format: {"scenarios": ["plausible failure scenario 1", "scenario 2"], '
            '"questions": ["clarifying question for the human?"], '
            '"tool_evidence": ["evidence gathered from tools"]}'
        )

    async def generate_critique(
        self, understanding: Understanding, sandbox=None
    ) -> SkepticCritique:
        messages = [
            {"role": "system", "content": self.system_prompt + "\n\n" + TOOL_DEFINITIONS},
            {"role": "user", "content": f"Understanding: {understanding.model_dump_json(indent=2)}"},
        ]

        for round_num in range(1, self.MAX_TOOL_ROUNDS + 1):
            response = await self.ollama.chat(messages, format="json", temperature=0.3)
            raw = response["message"]["content"]
            try:
                output = SkepticOutput.model_validate_json(raw)
            except Exception:
                if round_num == self.MAX_TOOL_ROUNDS:
                    output = SkepticOutput()
                else:
                    continue

            if output.tool_requests and sandbox:
                for req in output.tool_requests:
                    cmd = self._build_command(req)
                    result = ToolResult(tool=req.tool, args=req.args)
                    if sandbox and sandbox is not True:
                        try:
                            from backend.orchestrator.sandbox import SandboxManager
                            if hasattr(sandbox, 'install_tools'):
                                await sandbox.install_tools()
                            exec_result = await sandbox.exec_safe(cmd)
                            result.stdout = exec_result.get("stdout", "")
                            result.stderr = exec_result.get("stderr", "")
                            result.exit_code = exec_result.get("exit_code", -1)
                        except Exception as e:
                            result.stderr = str(e)
                            result.exit_code = -1
                    messages.append({
                        "role": "user",
                        "content": f"Tool '{req.tool} {req.args}' result:\n{result.model_dump_json(indent=2)}",
                    })
                continue

            data = SkepticCritique(
                understanding_id=understanding.id,
                scenarios=output.scenarios,
                questions=output.questions,
                tool_evidence=output.tool_evidence,
            )
            return data

        return SkepticCritique(
            understanding_id=understanding.id,
            scenarios=[],
            questions=["Skeptic loop exhausted without finalizing"],
            tool_evidence=["Max rounds reached"],
        )

    @staticmethod
    def _build_command(req: ToolRequest) -> str:
        from backend.orchestrator.sandbox import SandboxManager
        return SandboxManager.build_tool_command(req.tool, req.args)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_agents.py::test_skeptic_react_loop_with_tools tests/test_agents.py::test_skeptic_react_loop_no_tools_needed tests/test_agents.py::test_skeptic_react_loop_fallback_no_sandbox tests/test_agents.py::test_skeptic_react_loop_exhausted -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Run all agent tests to confirm no regressions**

```bash
pytest tests/test_agents.py -v
```

Expected: All tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/agents/skeptic.py tests/test_agents.py
git commit -m "feat: implement SkepticAgent ReAct loop with tool access"
```

---

### Task 4: Wire sandbox into orchestrator

**Files:**
- Modify: `backend/orchestrator/gates.py` — pass sandbox to Skeptic

- [ ] **Step 1: Write a failing integration test**

Modify `tests/test_integration.py` to update `MockSkeptic` signature (it already takes optional kwargs, but ensure the new `sandbox` param is handled):

```python
class MockSkeptic:
    async def generate_critique(self, understanding: Understanding, sandbox=None) -> SkepticCritique:
        return SkepticCritique(
            understanding_id=understanding.id,
            scenarios=["Could be too complex for MVP"],
            questions=["Should we scope down?"],
            tool_evidence=[],
        )
```

- [ ] **Step 2: Update gates.py to inject sandbox**

In `backend/orchestrator/gates.py`, find this line in `run_loop`:

```python
critique = await _skeptic.generate_critique(understanding)
```

Change to:

```python
critique = await _skeptic.generate_critique(understanding, sandbox=shared_sandbox)
```

- [ ] **Step 3: Run integration tests**

```bash
pytest tests/test_integration.py -v
```

Expected: All 4 PASSED.

- [ ] **Step 4: Run the full test suite**

```bash
pytest -v
```

Expected: All existing + new tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/orchestrator/gates.py tests/test_integration.py
git commit -m "feat: wire sandbox into SkepticAgent via gates.py"
```

---

### Task 5: Create the branch and final verification

- [ ] **Step 1: Create the phase_2 branch**

```bash
git checkout -b phases/phase_2
```

- [ ] **Step 2: Run full test suite one final time**

```bash
pytest -v
```

Expected: All tests PASSED.

- [ ] **Step 3: Update docs**

Update `docs/MODULES.md` to reflect Phase 2 is in progress:

Change Phase 2 Status from `⬜ PLANNED` to `🔷 IN PROGRESS` in the Phase Registry table.

Update `docs/ACTIVE.md` to point to Phase 2:

```markdown
# ACTIVE WORKING MEMORY – Phase 2: Learning & State-Drift Prevention
...
```

- [ ] **Step 4: Final commit**

```bash
git add docs/MODULES.md docs/ACTIVE.md
git commit -m "chore: update docs for Phase 2 status"
```
