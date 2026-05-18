# Brogrammer Phase 1: Full Role Separation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Phase 0's dual-agent loop with Planner, Builder, QA agents, Docker sandbox, and Git commit workflow.

**Architecture:** New agent classes (PlannerAgent, BuilderAgent, QAAgent) follow Phase 0's direct-call pattern. Docker sandbox managed via `docker-py` with streaming logs. New gates endpoints at `/api/plan`, `/api/build`, `/api/test`, `/api/commit`. Frontend gets three new components and a multi-step gate flow.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, docker-py, React 18, TypeScript, Vite.

---

### Task 1: Add docker-py dependency

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add docker-py to dependencies**

```toml
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "ollama>=0.1.0",
    "docker>=7.0.0",
]
```

Modify `backend/pyproject.toml` to add `"docker>=7.0.0"` to the dependencies list.

- [ ] **Step 2: Install updated deps**

Run:
```bash
source .venv/bin/activate && pip install -e ".[dev]" 2>&1 | tail -5
```
Expected: `Successfully installed ... docker`

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml
git commit -m "chore: add docker-py dependency for Phase 1 sandbox"
```

---

### Task 2: Add Phase 1 data models

**Files:**
- Modify: `backend/core/models.py`
- Create: `tests/test_models_phase1.py`

- [ ] **Step 1: Write the failing test**

```python
from backend.core.models import (
    FileSpec, ComponentSpec, APIRoute, TechPlan,
    BuildArtifact, TestPlan, TestReport, TestResult,
)


def test_file_spec():
    f = FileSpec(path="src/main.py", purpose="Entry point", content_type="code")
    assert f.path == "src/main.py"
    assert f.content_type == "code"


def test_component_spec():
    c = ComponentSpec(name="Auth", responsibility="Handle login", depends_on=["DB"])
    assert c.name == "Auth"
    assert "DB" in c.depends_on


def test_api_route():
    r = APIRoute(method="GET", path="/users", description="List users")
    assert r.method == "GET"
    assert r.path == "/users"


def test_tech_plan():
    plan = TechPlan(
        understanding_id="u1",
        tech_stack=["FastAPI", "SQLite"],
        file_tree=[FileSpec(path="src/main.py", purpose="Entry", content_type="code")],
        components=[ComponentSpec(name="API", responsibility="Routes")],
        markdown_summary="# Plan",
    )
    assert plan.plan_id is not None
    assert len(plan.tech_stack) == 2
    assert plan.markdown_summary == "# Plan"


def test_build_artifact():
    b = BuildArtifact(plan_id="p1", files_created=["main.py"], files_modified=[], docker_logs=["build ok"], status="success")
    assert b.build_id is not None
    assert b.status == "success"


def test_test_plan():
    tp = TestPlan(build_id="b1", framework="pytest", test_files=[], acceptance_criteria=["tests pass"])
    assert tp.plan_id is not None
    assert tp.framework == "pytest"


def test_test_result():
    tr = TestResult(test_name="test_auth", status="passed")
    assert tr.status == "passed"
    assert tr.error_message is None


def test_test_report():
    report = TestReport(
        build_id="b1",
        passed=5, failed=0, skipped=1,
        details=[TestResult(test_name="test_auth", status="passed")],
    )
    assert report.report_id is not None
    assert report.passed == 5
    assert report.coverage_pct is None
```

Write to `tests/test_models_phase1.py`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_models_phase1.py -v
```
Expected: FAIL with ImportError

- [ ] **Step 3: Add models to core/models.py**

Append at the end of `backend/core/models.py`:

```python
class FileSpec(BaseModel):
    path: str
    purpose: str
    content_type: str  # "code" | "config" | "test" | "doc"


class ComponentSpec(BaseModel):
    name: str
    responsibility: str
    depends_on: list[str] = []


class APIRoute(BaseModel):
    method: str  # GET | POST | PUT | DELETE
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
    status: str  # "success" | "failed"


class TestPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    build_id: str
    framework: str
    test_files: list[FileSpec]
    acceptance_criteria: list[str]


class TestResult(BaseModel):
    test_name: str
    status: str  # "passed" | "failed" | "skipped"
    error_message: str | None = None


class TestReport(BaseModel):
    report_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    build_id: str
    passed: int
    failed: int
    skipped: int
    coverage_pct: float | None = None
    details: list[TestResult] = []
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_models_phase1.py -v
```
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/core/models.py tests/test_models_phase1.py
git commit -m "feat: add Phase 1 data models (TechPlan, BuildArtifact, TestReport)"
```

---

### Task 3: Docker sandbox module

**Files:**
- Create: `backend/orchestrator/sandbox.py`
- Create: `tests/test_sandbox.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest


@pytest.mark.asyncio
async def test_sandbox_exec():
    """Integration test requires Docker. Skip if not available."""
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    from backend.orchestrator.sandbox import SandboxManager
    mgr = SandboxManager()
    container_id = await mgr.start()
    assert container_id is not None

    result = await mgr.exec("echo hello")
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]

    await mgr.stop()


@pytest.mark.asyncio
async def test_sandbox_exec_failure():
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    from backend.orchestrator.sandbox import SandboxManager
    mgr = SandboxManager()
    container_id = await mgr.start()
    result = await mgr.exec("exit 42")
    assert result["exit_code"] == 42
    await mgr.stop()


@pytest.mark.asyncio
async def test_sandbox_state():
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    from backend.orchestrator.sandbox import SandboxManager
    mgr = SandboxManager()
    assert mgr.container_id is None

    await mgr.start()
    assert mgr.container_id is not None
    assert mgr.is_running() is True

    await mgr.stop()
    assert mgr.is_running() is False
```

Write to `tests/test_sandbox.py`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_sandbox.py -v
```
Expected: FAIL with ImportError

- [ ] **Step 3: Write sandbox.py**

```python
import asyncio
import docker
from docker.errors import DockerException


class SandboxManager:
    def __init__(self, image: str = "python:3.11-slim", workdir: str = "/workspace"):
        self.image = image
        self.workdir = workdir
        self.container_id: str | None = None
        self._client = docker.from_env()

    async def start(self) -> str:
        def _create():
            container = self._client.containers.run(
                self.image,
                command="tail -f /dev/null",
                detach=True,
                working_dir=self.workdir,
                stdin_open=True,
                tty=True,
            )
            return container.id

        loop = asyncio.get_event_loop()
        self.container_id = await loop.run_in_executor(None, _create)
        return self.container_id

    async def exec(self, command: str) -> dict:
        if not self.container_id:
            raise RuntimeError("Sandbox not started")

        def _exec():
            container = self._client.containers.get(self.container_id)
            exit_code, output = container.exec_run(
                ["/bin/sh", "-c", command],
                demux=False,
            )
            text = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else str(output)
            return {"stdout": text, "stderr": "", "exit_code": exit_code}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _exec)

    def is_running(self) -> bool:
        if not self.container_id:
            return False
        try:
            container = self._client.containers.get(self.container_id)
            return container.status == "running"
        except DockerException:
            return False

    async def stop(self):
        if not self.container_id:
            return

        def _stop():
            try:
                container = self._client.containers.get(self.container_id)
                container.remove(force=True)
            except DockerException:
                pass

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _stop)
        self.container_id = None
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_sandbox.py -v
```
If Docker is unavailable, tests will skip gracefully.

Expected: All 3 tests PASS or SKIP

- [ ] **Step 5: Commit**

```bash
git add backend/orchestrator/sandbox.py tests/test_sandbox.py
git commit -m "feat: implement Docker SandboxManager with exec lifecycle"
```

---

### Task 4: PlannerAgent

**Files:**
- Create: `backend/agents/planner.py`
- Create: `tests/test_planner.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from backend.core.models import Understanding, TechPlan, MandatoryCategories, Assumption


class PlannerFakeClient:
    async def chat(self, messages, format="", temperature=0.0):
        return {
            "message": {
                "content": (
                    '{"understanding_id": "u1", '
                    '"tech_stack": ["FastAPI", "SQLite"], '
                    '"file_tree": [{"path": "src/main.py", "purpose": "Entry point", "content_type": "code"}], '
                    '"components": [{"name": "API", "responsibility": "Routes", "depends_on": []}], '
                    '"api_routes": [{"method": "GET", "path": "/health", "description": "Health check"}], '
                    '"markdown_summary": "# Project Plan\\n\\nBuild a simple app"}'
                )
            }
        }


@pytest.mark.asyncio
async def test_planner_generates_plan():
    from backend.agents.planner import PlannerAgent

    agent = PlannerAgent(ollama_client=PlannerFakeClient())
    understanding = Understanding(
        goal="Build a habit tracker",
        assumptions=[Assumption(statement="Users want streaks")],
        mandatory_categories=MandatoryCategories(),
    )
    plan = await agent.generate_plan(understanding)
    assert isinstance(plan, TechPlan)
    assert plan.understanding_id == understanding.id
    assert "FastAPI" in plan.tech_stack
    assert len(plan.file_tree) == 1
    assert plan.file_tree[0].path == "src/main.py"
    assert len(plan.api_routes) == 1
    assert plan.markdown_summary.startswith("# Project Plan")


@pytest.mark.asyncio
async def test_planner_retries_on_bad_json():
    class FlakyClient:
        def __init__(self):
            self.attempt = 0

        async def chat(self, messages, format="", temperature=0.0):
            self.attempt += 1
            content = (
                '{"tech_stack": ["FastAPI"], "file_tree": [], "components": [], "markdown_summary": "ok"}'
                if self.attempt > 1
                else "not json"
            )
            return {"message": {"content": content}}

    from backend.agents.planner import PlannerAgent

    agent = PlannerAgent(ollama_client=FlakyClient())
    plan = await agent.generate_plan(
        Understanding(goal="test", mandatory_categories=MandatoryCategories())
    )
    assert "FastAPI" in plan.tech_stack
    assert agent.ollama.attempt > 1  # noqa
```

Write to `tests/test_planner.py`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_planner.py -v
```
Expected: FAIL with ImportError

- [ ] **Step 3: Write planner.py**

```python
import json
from backend.core.models import Understanding, TechPlan
from backend.agents.specialist import OllamaClient


class PlannerAgent:
    def __init__(self, ollama_client: OllamaClient | None = None):
        self.ollama = ollama_client or OllamaClient()
        self.system_prompt = (
            "You are the PlannerAgent. Given an Understanding document, produce a TechPlan. "
            "Return ONLY valid JSON — no markdown, no explanation. "
            'Format: {"understanding_id": "...", '
            '"tech_stack": ["Python", "FastAPI"], '
            '"file_tree": [{"path": "src/main.py", "purpose": "Entry point", "content_type": "code"}], '
            '"components": [{"name": "API", "responsibility": "Handle requests", "depends_on": []}], '
            '"api_routes": [{"method": "GET", "path": "/health", "description": "Health check"}], '
            '"markdown_summary": "# Plan summary in markdown"}'
        )

    async def generate_plan(self, understanding: Understanding) -> TechPlan:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Understanding: {understanding.model_dump_json(indent=2)}"},
        ]

        for attempt in range(3):
            response = await self.ollama.chat(messages, format="json", temperature=0.2)
            raw = response["message"]["content"]
            try:
                data = json.loads(raw)
                data["understanding_id"] = understanding.id
                return TechPlan(**data)
            except (json.JSONDecodeError, Exception):
                if attempt == 2:
                    raise

        raise RuntimeError("Planner failed after 3 retries")
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_planner.py -v
```
Expected: Both tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agents/planner.py tests/test_planner.py
git commit -m "feat: implement PlannerAgent with retry logic"
```

---

### Task 5: BuilderAgent

**Files:**
- Create: `backend/agents/builder.py`
- Create: `tests/test_builder.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from backend.core.models import TechPlan, FileSpec, ComponentSpec


class FakeSandbox:
    def __init__(self):
        self.commands = []

    async def start(self):
        return "container-1"

    async def exec(self, command):
        self.commands.append(command)
        if "mkdir" in command or "cat" in command or "pip" in command:
            return {"stdout": "done", "stderr": "", "exit_code": 0}
        if "python -c" in command:
            return {"stdout": "ok", "stderr": "", "exit_code": 0}
        return {"stdout": "", "stderr": "unknown command", "exit_code": 1}


@pytest.mark.asyncio
async def test_builder_creates_files():
    from backend.agents.builder import BuilderAgent

    agent = BuilderAgent(sandbox=FakeSandbox())
    plan = TechPlan(
        understanding_id="u1",
        tech_stack=["Python"],
        file_tree=[
            FileSpec(path="src/main.py", purpose="Entry", content_type="code"),
            FileSpec(path="src/config.py", purpose="Config", content_type="code"),
        ],
        components=[ComponentSpec(name="App", responsibility="Run")],
        markdown_summary="# Plan",
    )
    artifact = await agent.build(plan)
    assert artifact.status == "success"
    assert len(artifact.files_created) == 2
    assert "src/main.py" in artifact.files_created
    assert "src/config.py" in artifact.files_created


@pytest.mark.asyncio
async def test_builder_handles_failure():
    class BrokenSandbox:
        async def start(self):
            return "c1"

        async def exec(self, command):
            return {"stdout": "", "stderr": "disk full", "exit_code": 1}

    from backend.agents.builder import BuilderAgent

    agent = BuilderAgent(sandbox=BrokenSandbox())
    plan = TechPlan(
        understanding_id="u1",
        tech_stack=["Python"],
        file_tree=[FileSpec(path="src/main.py", purpose="Entry", content_type="code")],
        components=[],
        markdown_summary="#",
    )
    artifact = await agent.build(plan)
    assert artifact.status == "failed"
```

Write to `tests/test_builder.py`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_builder.py -v
```
Expected: FAIL with ImportError

- [ ] **Step 3: Write builder.py**

```python
import json
from backend.core.models import TechPlan, BuildArtifact
from backend.agents.specialist import OllamaClient
from backend.orchestrator.sandbox import SandboxManager


class BuilderAgent:
    def __init__(self, ollama_client: OllamaClient | None = None,
                 sandbox: SandboxManager | None = None):
        self.ollama = ollama_client or OllamaClient()
        self.sandbox = sandbox or SandboxManager()
        self.system_prompt = (
            "You are the BuilderAgent. Given a TechPlan, generate the actual file contents. "
            "Return ONLY a JSON object mapping file paths to their content. "
            'Format: {"src/main.py": "print(\'hello\')", "src/config.py": "DEBUG=True"} '
            "No markdown, no explanation."
        )

    async def build(self, plan: TechPlan) -> BuildArtifact:
        if not self.sandbox.is_running():
            await self.sandbox.start()

        logs = []
        created = []
        modified = []

        container_dir = "/workspace"
        for file_spec in plan.file_tree:
            mkdir_cmd = f"mkdir -p {container_dir}/{file_spec.path.rsplit('/', 1)[0] if '/' in file_spec.path else '.'}"
            result = await self._exec_with_retry(mkdir_cmd)
            logs.append(f"$ {mkdir_cmd}")
            logs.append(result["stdout"])

            content = await self._generate_file_content(plan, file_spec)
            write_cmd = f"cat > {container_dir}/{file_spec.path} << 'BROGRAMMER_EOF'\n{content}\nBROGRAMMER_EOF"
            result = await self._exec_with_retry(write_cmd)
            logs.append(f"$ Writing {file_spec.path}")
            logs.append(result["stdout"])
            created.append(file_spec.path)

        install_result = await self._exec_with_retry(
            f"cd {container_dir} && pip install -r requirements.txt 2>/dev/null; echo 'deps done'"
        )
        logs.append(install_result["stdout"])

        verify_result = await self._exec_with_retry(
            f"cd {container_dir} && python -c 'import sys; print(sys.version)'"
        )
        logs.append(verify_result["stdout"])
        status = "success" if verify_result["exit_code"] == 0 else "failed"

        return BuildArtifact(
            plan_id=plan.plan_id,
            files_created=created,
            files_modified=modified,
            docker_logs=logs,
            status=status,
        )

    async def _exec_with_retry(self, command: str, retries: int = 3) -> dict:
        for attempt in range(retries):
            result = await self.sandbox.exec(command)
            if result["exit_code"] == 0:
                return result
        return result

    async def _generate_file_content(self, plan: TechPlan, file_spec) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"Plan: {plan.model_dump_json(indent=2)}\n"
                    f"Generate content for: {file_spec.path}\n"
                    f"Purpose: {file_spec.purpose}\n"
                    f"Type: {file_spec.content_type}"
                ),
            },
        ]
        response = await self.ollama.chat(messages, format="json", temperature=0.1)
        raw = response["message"]["content"]
        try:
            data = json.loads(raw)
            return data.get(file_spec.path, "# placeholder")
        except json.JSONDecodeError:
            return raw
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_builder.py -v
```
Expected: Both tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agents/builder.py tests/test_builder.py
git commit -m "feat: implement BuilderAgent with Docker sandbox code generation"
```

---

### Task 6: QAAgent

**Files:**
- Create: `backend/agents/qa.py`
- Create: `tests/test_qa.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from backend.core.models import TechPlan, FileSpec, ComponentSpec, TestReport


class FakeSandbox:
    async def exec(self, command):
        if "pytest" in command:
            return {
                "stdout": "collected 3 items\nmain.py::test_auth PASSED\nmain.py::test_api PASSED\nmain.py::test_db FAILED\n\n1 failed, 2 passed",
                "stderr": "",
                "exit_code": 1,
            }
        return {"stdout": "done", "stderr": "", "exit_code": 0}


@pytest.mark.asyncio
async def test_qa_generates_test_plan():
    from backend.agents.qa import QAAgent

    agent = QAAgent()
    plan = TechPlan(
        understanding_id="u1",
        tech_stack=["Python", "FastAPI"],
        file_tree=[FileSpec(path="src/main.py", purpose="Entry", content_type="code")],
        components=[ComponentSpec(name="App", responsibility="Run")],
        markdown_summary="#",
    )
    test_plan = await agent.generate_test_plan(plan)
    assert test_plan.build_id == ""
    assert test_plan.framework == "pytest"
    assert len(test_plan.acceptance_criteria) > 0


@pytest.mark.asyncio
async def test_qa_runs_tests():
    from backend.agents.qa import QAAgent

    agent = QAAgent(sandbox=FakeSandbox())
    report = await agent.run_tests("b1", "test_app.py")
    assert isinstance(report, TestReport)
    assert report.build_id == "b1"
    assert report.passed == 2
    assert report.failed == 1
    assert report.skipped == 0
```

Write to `tests/test_qa.py`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_qa.py -v
```
Expected: FAIL with ImportError

- [ ] **Step 3: Write qa.py**

```python
import re
from backend.core.models import TechPlan, TestPlan, TestReport, TestResult, FileSpec
from backend.agents.specialist import OllamaClient
from backend.orchestrator.sandbox import SandboxManager


class QAAgent:
    def __init__(self, ollama_client: OllamaClient | None = None,
                 sandbox: SandboxManager | None = None):
        self.ollama = ollama_client or OllamaClient()
        self.sandbox = sandbox or SandboxManager()
        self.system_prompt = (
            "You are the QAAgent. Given a TechPlan, generate a test plan. "
            "Return ONLY valid JSON — no markdown. "
            'Format: {"framework": "pytest", '
            '"test_files": [{"path": "tests/test_app.py", "purpose": "Main tests", "content_type": "test"}], '
            '"acceptance_criteria": ["all tests pass", "coverage > 80%"]}'
        )

    async def generate_test_plan(self, plan: TechPlan) -> TestPlan:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"TechPlan: {plan.model_dump_json(indent=2)}"},
        ]
        response = await self.ollama.chat(messages, format="json", temperature=0.2)
        raw = response["message"]["content"]
        data = TestPlan.model_validate_json(raw)
        data.build_id = ""
        return data

    async def run_tests(self, build_id: str, test_path: str = "tests") -> TestReport:
        result = await self.sandbox.exec(f"python -m pytest {test_path} -v 2>&1")
        return self._parse_test_output(build_id, result["stdout"])

    def _parse_test_output(self, build_id: str, output: str) -> TestReport:
        passed = len(re.findall(r"PASSED", output))
        failed = len(re.findall(r"FAILED", output))
        skipped = len(re.findall(r"SKIPPED", output))

        details = []
        for line in output.split("\n"):
            for status in ("PASSED", "FAILED", "SKIPPED"):
                if status in line:
                    details.append(TestResult(
                        test_name=line.strip(),
                        status=status.lower(),
                    ))

        return TestReport(
            build_id=build_id,
            passed=passed,
            failed=failed,
            skipped=skipped,
            details=details,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_qa.py -v
```
Expected: Both tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agents/qa.py tests/test_qa.py
git commit -m "feat: implement QAAgent with test plan generation and execution"
```

---

### Task 7: Database tables for Phase 1 artifacts

**Files:**
- Modify: `backend/orchestrator/database.py`
- Modify: `tests/test_audit.py`

- [ ] **Step 1: Add test for new tables**

Append to `tests/test_audit.py`:

```python
@pytest.mark.asyncio
async def test_tech_plans_table(db):
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tech_plans'")
    row = await cursor.fetchone()
    assert row is not None, "tech_plans table should exist"


@pytest.mark.asyncio
async def test_build_artifacts_table(db):
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='build_artifacts'")
    row = await cursor.fetchone()
    assert row is not None, "build_artifacts table should exist"


@pytest.mark.asyncio
async def test_test_reports_table(db):
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_reports'")
    row = await cursor.fetchone()
    assert row is not None, "test_reports table should exist"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_audit.py::test_tech_plans_table ../tests/test_audit.py::test_build_artifacts_table ../tests/test_audit.py::test_test_reports_table -v
```
Expected: FAIL (table doesn't exist)

- [ ] **Step 3: Add tables to init_db**

Modify `backend/orchestrator/database.py` — add these tables after the existing audit_events table creation:

```python
    await db.execute("""
        CREATE TABLE IF NOT EXISTS tech_plans (
            id TEXT PRIMARY KEY,
            understanding_id TEXT NOT NULL,
            plan_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS build_artifacts (
            id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            artifact_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS test_reports (
            id TEXT PRIMARY KEY,
            build_id TEXT NOT NULL,
            report_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_audit.py::test_tech_plans_table ../tests/test_audit.py::test_build_artifacts_table ../tests/test_audit.py::test_test_reports_table -v
```
Expected: All 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/orchestrator/database.py tests/test_audit.py
git commit -m "feat: add tech_plans, build_artifacts, test_reports tables"
```

---

### Task 8: Store full Understanding in audit payload

**Files:**
- Modify: `backend/orchestrator/gates.py`

The current audit payload for `understanding_generated` doesn't store `unknowns` or `mandatory_categories`. Phase 1 needs the full Understanding to reconstruct it. We extend the payload to include all Understanding fields.

- [ ] **Step 1: Modify the run_loop endpoint to store full Understanding**

In `backend/orchestrator/gates.py`, change the audit event for understanding_generated to store the full model dump:

```python
        await append_event(
            db, "understanding_generated", understanding.id, None,
            understanding.model_dump(),
        )
```

Replace the current dict literal `{"goal": ..., "assumptions": ..., "fragile": ...}` with `understanding.model_dump()`. This stores `goal`, `assumptions`, `unknowns`, `mandatory_categories`, and `id` in the payload.

- [ ] **Step 2: Run existing tests to verify the change doesn't break anything**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_integration.py -v
```
Expected: All 4 tests PASS (the integration tests don't inspect the understanding payload directly)

- [ ] **Step 3: Commit**

```bash
git add backend/orchestrator/gates.py
git commit -m "feat: store full Understanding in audit event payload for Phase 1 planner"
```

---

### Task 9: API endpoints for Phase 1 gates

**Files:**
- Modify: `backend/orchestrator/gates.py`
- Create: `tests/test_integration_phase1.py`

- [ ] **Step 1: Write a failing integration test with mock agents**

Write to `tests/test_integration_phase1.py`:

```python
import pytest
import json
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock
from datetime import datetime, timezone
from backend.orchestrator.database import get_db, init_db
from backend.orchestrator.audit import append_event
from backend.core.models import (
    TechPlan, FileSpec, ComponentSpec, BuildArtifact,
    TestReport, TestResult, TestPlan,
)


@pytest.fixture
async def db_with_understanding():
    db = await get_db(":memory:")
    await init_db(db)
    await append_event(db, "understanding_generated", "u1", None, {
        "id": "u1",
        "goal": "Build a habit tracker",
        "assumptions": [{"id": "a1", "statement": "Users want streaks", "status": "open", "validated_by": None}],
        "unknowns": [],
        "mandatory_categories": {
            "accessibility": [],
            "performance": ["fast"],
            "security": [],
            "state_management": [],
            "persistence": [],
        },
    })
    await append_event(db, "plan_created", "u1", None, {"plan_id": "p1"})
    await db.execute(
        "INSERT INTO tech_plans (id, understanding_id, plan_json, created_at) VALUES (?, ?, ?, ?)",
        ("p1", "u1", TechPlan(
            understanding_id="u1",
            tech_stack=["Python"],
            file_tree=[FileSpec(path="main.py", purpose="Entry", content_type="code")],
            components=[ComponentSpec(name="App", responsibility="Run")],
            markdown_summary="# test",
        ).model_dump_json(), datetime.now(timezone.utc).isoformat()),
    )
    await db.commit()
    await db.execute(
        "INSERT INTO build_artifacts (id, plan_id, artifact_json, created_at) VALUES (?, ?, ?, ?)",
        ("b1", "p1", BuildArtifact(
            plan_id="p1", files_created=["main.py"], files_modified=[],
            docker_logs=["ok"], status="success",
        ).model_dump_json(), datetime.now(timezone.utc).isoformat()),
    )
    await db.commit()
    return db


def make_app_with_mocks():
    from backend.agents.planner import PlannerAgent
    from backend.agents.builder import BuilderAgent
    from backend.agents.qa import QAAgent
    from backend.orchestrator.gates import create_app

    mock_planner = AsyncMock(spec=PlannerAgent)
    mock_planner.generate_plan.return_value = TechPlan(
        understanding_id="u1",
        tech_stack=["Python"],
        file_tree=[FileSpec(path="main.py", purpose="Entry", content_type="code")],
        components=[ComponentSpec(name="App", responsibility="Run")],
        markdown_summary="# test",
    )

    mock_builder = AsyncMock(spec=BuilderAgent)
    mock_builder.build.return_value = BuildArtifact(
        plan_id="p1", files_created=["main.py"], files_modified=[],
        docker_logs=["build ok"], status="success",
    )

    mock_qa = AsyncMock(spec=QAAgent)
    mock_qa.generate_test_plan.return_value = TestPlan(
        build_id="b1", framework="pytest", test_files=[], acceptance_criteria=["pass"],
    )
    mock_qa.run_tests.return_value = TestReport(
        build_id="b1", passed=2, failed=0, skipped=0,
        details=[TestResult(test_name="test_a", status="passed")],
    )

    return create_app(
        db_path=":memory:",
        planner=mock_planner,
        builder=mock_builder,
        qa=mock_qa,
    )


@pytest.mark.asyncio
async def test_plan_endpoint():
    app = make_app_with_mocks()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/plan", json={"understanding_id": "u1"})
    assert resp.status_code == 200
    data = resp.json()
    assert "plan" in data


@pytest.mark.asyncio
async def test_build_endpoint():
    app = make_app_with_mocks()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/build", json={"plan_id": "p1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["build"]["status"] == "success"


@pytest.mark.asyncio
async def test_test_endpoint():
    app = make_app_with_mocks()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/test", json={"build_id": "b1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["test_report"]["passed"] == 2


@pytest.mark.asyncio
async def test_commit_endpoint():
    app = make_app_with_mocks()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/commit", json={"build_id": "b1", "message": "feat: initial build"})
    assert resp.status_code == 200
    data = resp.json()
    assert "commit_sha" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_integration_phase1.py -v
```
Expected: FAIL with 404 or ImportError (no /api/plan route yet)

- [ ] **Step 3: Add new endpoints to gates.py**

Modify `backend/orchestrator/gates.py`:

**Update imports** at the top:

```python
import json
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from backend.orchestrator.database import get_db, init_db
from backend.orchestrator.audit import append_event, get_events
from backend.agents.specialist import SpecialistAgent
from backend.agents.skeptic import SkepticAgent
from backend.agents.planner import PlannerAgent
from backend.agents.builder import BuilderAgent
from backend.agents.qa import QAAgent
from backend.core.confidence import compute_confidence
from backend.core.models import Understanding, Assumption
```

**Add request models** after `ResolveCritiqueRequest`:

```python
class PlanRequest(BaseModel):
    understanding_id: str


class BuildRequest(BaseModel):
    plan_id: str


class TestRequest(BaseModel):
    build_id: str


class CommitRequest(BaseModel):
    build_id: str
    message: str
```

**Update create_app signature** and add agent injection:

```python
def create_app(db_path: str | None = None,
               specialist: SpecialistAgent | None = None,
               skeptic: SkepticAgent | None = None,
               planner: PlannerAgent | None = None,
               builder: BuilderAgent | None = None,
               qa: QAAgent | None = None) -> FastAPI:
    _specialist = specialist or SpecialistAgent()
    _skeptic = skeptic or SkepticAgent()
    _planner = planner or PlannerAgent()
    _builder = builder or BuilderAgent()
    _qa = qa or QAAgent()
```

**Add helper functions** (before or after `create_app` — they must be at module level for FastAPI route handlers to reference):

```python
async def _get_understanding(db, understanding_id: str) -> Understanding:
    cursor = await db.execute(
        "SELECT payload FROM audit_events WHERE event_type='understanding_generated' AND understanding_id=?",
        (understanding_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Understanding not found")
    payload = json.loads(row["payload"])
    return Understanding(**payload)


async def _get_plan(db, plan_id: str) -> TechPlan:
    from backend.core.models import TechPlan
    cursor = await db.execute(
        "SELECT plan_json FROM tech_plans WHERE id=?",
        (plan_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Plan not found")
    return TechPlan.model_validate_json(row["plan_json"])


async def _get_plan_for_build(db, build_id: str) -> TechPlan:
    cursor = await db.execute(
        "SELECT plan_id FROM build_artifacts WHERE id=?",
        (build_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Build not found")
    return await _get_plan(db, row["plan_id"])
```

**Add endpoints** inside `create_app` (after existing endpoints):

```python
    @app.post("/api/plan")
    async def create_plan(req: PlanRequest):
        db = await get_db_conn()
        understanding = await _get_understanding(db, req.understanding_id)
        plan = await _planner.generate_plan(understanding)
        await db.execute(
            "INSERT INTO tech_plans (id, understanding_id, plan_json, created_at) VALUES (?, ?, ?, ?)",
            (plan.plan_id, req.understanding_id, plan.model_dump_json(),
             datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
        await append_event(db, "plan_created", req.understanding_id, None,
                           {"plan_id": plan.plan_id})
        return {"plan": plan.model_dump(), "plan_id": plan.plan_id}

    @app.post("/api/build")
    async def create_build(req: BuildRequest):
        db = await get_db_conn()
        plan = await _get_plan(db, req.plan_id)
        artifact = await _builder.build(plan)
        await db.execute(
            "INSERT INTO build_artifacts (id, plan_id, artifact_json, created_at) VALUES (?, ?, ?, ?)",
            (artifact.build_id, req.plan_id, artifact.model_dump_json(),
             datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
        await append_event(db, "build_completed", None, None,
                           {"build_id": artifact.build_id, "status": artifact.status})
        return {"build": artifact.model_dump()}

    @app.post("/api/test")
    async def run_tests(req: TestRequest):
        db = await get_db_conn()
        plan = await _get_plan_for_build(db, req.build_id)
        test_plan = await _qa.generate_test_plan(plan)
        report = await _qa.run_tests(req.build_id)
        await db.execute(
            "INSERT INTO test_reports (id, build_id, report_json, created_at) VALUES (?, ?, ?, ?)",
            (report.report_id, req.build_id, report.model_dump_json(),
             datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
        await append_event(db, "test_completed", None, None,
                           {"build_id": req.build_id, "passed": report.passed, "failed": report.failed})
        return {"test_plan": test_plan.model_dump(), "test_report": report.model_dump()}

    @app.post("/api/commit")
    async def commit_build(req: CommitRequest):
        db = await get_db_conn()
        import subprocess
        subprocess.run(["git", "add", "-A"], capture_output=True)
        result = subprocess.run(
            ["git", "commit", "-m", req.message],
            capture_output=True, text=True,
        )
        sha = result.stdout.strip() if result.returncode == 0 else ""
        await append_event(db, "commit_created", None, None,
                           {"build_id": req.build_id, "sha": sha})
        return {"commit_sha": sha, "success": result.returncode == 0}
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_integration_phase1.py -v
```
Expected: All 4 tests PASS

- [ ] **Step 5: Run Phase 0 integration tests to ensure no regressions**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_integration.py -v
```
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/orchestrator/gates.py tests/test_integration_phase1.py
git commit -m "feat: add Phase 1 gate endpoints (/api/plan, /api/build, /api/test, /api/commit)"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_integration_phase1.py -v
```
Expected: FAIL with 404 or ImportError

- [ ] **Step 3: Add new endpoints to gates.py**

Add new endpoint classes and endpoints to `backend/orchestrator/gates.py`:

After the existing `ResolveCritiqueRequest`, add:

```python
class PlanRequest(BaseModel):
    understanding_id: str


class BuildRequest(BaseModel):
    plan_id: str


class TestRequest(BaseModel):
    build_id: str


class CommitRequest(BaseModel):
    build_id: str
    message: str
```

Update the `create_app` function to accept additional agents:

```python
def create_app(db_path: str | None = None,
               specialist: SpecialistAgent | None = None,
               skeptic: SkepticAgent | None = None,
               planner: PlannerAgent | None = None,
               builder: BuilderAgent | None = None,
               qa: QAAgent | None = None) -> FastAPI:
```

And inject them:
```python
    _planner = planner or PlannerAgent()
    _builder = builder or BuilderAgent()
    _qa = qa or QAAgent()
```

Add new endpoints inside `create_app`:

```python
    @app.post("/api/plan")
    async def create_plan(req: PlanRequest):
        db = app.state.db
        understanding_json = await _get_understanding(db, req.understanding_id)
        understanding = Understanding.model_validate_json(understanding_json)
        plan = await _planner.generate_plan(understanding)
        await db.execute(
            "INSERT INTO tech_plans (id, understanding_id, plan_json, created_at) VALUES (?, ?, ?, ?)",
            (plan.plan_id, req.understanding_id, plan.model_dump_json(),
             datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
        await append_event(db, "plan_created", req.understanding_id, None,
                           {"plan_id": plan.plan_id})
        return {"plan": plan.model_dump(), "plan_id": plan.plan_id}

    @app.post("/api/build")
    async def create_build(req: BuildRequest):
        db = app.state.db
        plan = await _get_plan(db, req.plan_id)
        artifact = await _builder.build(plan)
        await db.execute(
            "INSERT INTO build_artifacts (id, plan_id, artifact_json, created_at) VALUES (?, ?, ?, ?)",
            (artifact.build_id, req.plan_id, artifact.model_dump_json(),
             datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
        await append_event(db, "build_completed", None, None,
                           {"build_id": artifact.build_id, "status": artifact.status})
        return {"build": artifact.model_dump()}

    @app.post("/api/test")
    async def run_tests(req: TestRequest):
        db = app.state.db
        plan = await _get_plan_for_build(db, req.build_id)
        test_plan = await _qa.generate_test_plan(plan)
        report = await _qa.run_tests(req.build_id)
        await db.execute(
            "INSERT INTO test_reports (id, build_id, report_json, created_at) VALUES (?, ?, ?, ?)",
            (report.report_id, req.build_id, report.model_dump_json(),
             datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
        await append_event(db, "test_completed", None, None,
                           {"build_id": req.build_id, "passed": report.passed, "failed": report.failed})
        return {"test_plan": test_plan.model_dump(), "test_report": report.model_dump()}

    @app.post("/api/commit")
    async def commit_build(req: CommitRequest):
        db = app.state.db
        import subprocess
        subprocess.run(["git", "add", "-A"], capture_output=True)
        result = subprocess.run(
            ["git", "commit", "-m", req.message],
            capture_output=True, text=True,
        )
        sha = result.stdout.strip() if result.returncode == 0 else ""
        await append_event(db, "commit_created", None, None,
                           {"build_id": req.build_id, "sha": sha})
        return {"commit_sha": sha, "success": result.returncode == 0}
```

Add helper methods inside the file:

```python
async def _get_understanding(db, understanding_id: str) -> str:
    cursor = await db.execute(
        "SELECT payload FROM audit_events WHERE event_type='understanding_generated' AND understanding_id=?",
        (understanding_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Understanding not found")
    payload = json.loads(row["payload"])
    return Understanding(
        id=understanding_id,
        goal=payload.get("goal", ""),
        assumptions=[Assumption(**a) for a in payload.get("assumptions", [])],
        mandatory_categories=payload.get("mandatory_categories", {}),
    ).model_dump_json()


async def _get_plan(db, plan_id: str):
    from backend.core.models import TechPlan
    cursor = await db.execute(
        "SELECT plan_json FROM tech_plans WHERE id=?",
        (plan_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Plan not found")
    return TechPlan.model_validate_json(row["plan_json"])


async def _get_plan_for_build(db, build_id: str):
    cursor = await db.execute(
        "SELECT plan_id FROM build_artifacts WHERE id=?",
        (build_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Build not found")
    return await _get_plan(db, row["plan_id"])
```

Add imports at top:
```python
from datetime import datetime, timezone
from backend.agents.planner import PlannerAgent
from backend.agents.builder import BuilderAgent
from backend.agents.qa import QAAgent
from backend.core.models import Understanding, Assumption
```

Note: Some existing imports need updating (add `Understanding`, `Assumption`).

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_integration_phase1.py -v
```
Expected: All 4 tests PASS (build may 500 without Docker, others 200)

- [ ] **Step 5: Commit**

```bash
git add backend/orchestrator/gates.py tests/test_integration_phase1.py
git commit -m "feat: add Phase 1 gate endpoints (/api/plan, /api/build, /api/test, /api/commit)"
```

---

### Task 10: Frontend API client updates

**Files:**
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Add new types and client methods**

Add to `frontend/src/api.ts`:

```typescript
// Phase 1 types
export interface FileSpec {
  path: string;
  purpose: string;
  content_type: string;
}

export interface ComponentSpec {
  name: string;
  responsibility: string;
  depends_on: string[];
}

export interface APIRoute {
  method: string;
  path: string;
  description: string;
}

export interface TechPlan {
  plan_id: string;
  understanding_id: string;
  tech_stack: string[];
  file_tree: FileSpec[];
  components: ComponentSpec[];
  api_routes: APIRoute[];
  markdown_summary: string;
}

export interface BuildArtifact {
  build_id: string;
  plan_id: string;
  files_created: string[];
  files_modified: string[];
  docker_logs: string[];
  status: string;
}

export interface TestResult {
  test_name: string;
  status: string;
  error_message: string | null;
}

export interface TestReport {
  report_id: string;
  build_id: string;
  passed: number;
  failed: number;
  skipped: number;
  coverage_pct: number | null;
  details: TestResult[];
}

export interface TestPlan {
  plan_id: string;
  build_id: string;
  framework: string;
  test_files: FileSpec[];
  acceptance_criteria: string[];
}

// Phase 1 API methods
export async function createPlan(understandingId: string): Promise<{ plan: TechPlan; plan_id: string }> {
  const res = await fetch(`${API_BASE}/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ understanding_id: understandingId }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function createBuild(planId: string): Promise<{ build: BuildArtifact }> {
  const res = await fetch(`${API_BASE}/build`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan_id: planId }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function runTests(buildId: string): Promise<{ test_plan: TestPlan; test_report: TestReport }> {
  const res = await fetch(`${API_BASE}/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ build_id: buildId }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function commitBuild(buildId: string, message: string): Promise<{ commit_sha: string; success: boolean }> {
  const res = await fetch(`${API_BASE}/commit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ build_id: buildId, message }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.ts
git commit -m "feat: add Phase 1 API types and client methods"
```

---

### Task 11: TechPlanView component

**Files:**
- Create: `frontend/src/components/TechPlanView.tsx`

- [ ] **Step 1: Create TechPlanView.tsx**

```tsx
import { TechPlan } from '../api';

interface Props {
  plan: TechPlan;
  onApprove?: () => void;
  onRetry?: () => void;
  approved?: boolean;
}

export default function TechPlanView({ plan, onApprove, onRetry, approved }: Props) {
  const typeLabels: Record<string, string> = {
    code: '💻',
    config: '⚙️',
    test: '🧪',
    doc: '📝',
  };

  return (
    <div className="section">
      <h2>Tech Plan {approved && <span style={{ color: '#16a34a' }}>✅ Approved</span>}</h2>

      <h3 style={{ marginTop: 8, fontSize: '1rem' }}>Tech Stack</h3>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
        {plan.tech_stack.map((t) => (
          <span key={t} className="tag tag-validated">{t}</span>
        ))}
      </div>

      <h3 style={{ fontSize: '1rem' }}>File Tree</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #e0e0e0' }}>
            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Path</th>
            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Purpose</th>
            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Type</th>
          </tr>
        </thead>
        <tbody>
          {plan.file_tree.map((f, i) => (
            <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}>
              <td style={{ padding: '4px 8px', fontFamily: 'monospace' }}>{f.path}</td>
              <td style={{ padding: '4px 8px' }}>{f.purpose}</td>
              <td style={{ padding: '4px 8px' }}>{typeLabels[f.content_type] || f.content_type}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {plan.api_routes.length > 0 && (
        <>
          <h3 style={{ marginTop: 12, fontSize: '1rem' }}>API Routes</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e0e0e0' }}>
                <th style={{ textAlign: 'left', padding: '6px 8px' }}>Method</th>
                <th style={{ textAlign: 'left', padding: '6px 8px' }}>Path</th>
                <th style={{ textAlign: 'left', padding: '6px 8px' }}>Description</th>
              </tr>
            </thead>
            <tbody>
              {plan.api_routes.map((r, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '4px 8px' }}>
                    <span className={`tag ${r.method === 'GET' ? 'tag-validated' : 'tag-open'}`}>
                      {r.method}
                    </span>
                  </td>
                  <td style={{ padding: '4px 8px', fontFamily: 'monospace' }}>{r.path}</td>
                  <td style={{ padding: '4px 8px' }}>{r.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Summary</h3>
      <div style={{ background: '#f9f9f9', padding: 12, borderRadius: 6, fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>
        {plan.markdown_summary}
      </div>

      {!approved && onApprove && (
        <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" onClick={onApprove}>✅ Approve Plan</button>
          {onRetry && <button className="btn" onClick={onRetry}>🔄 Retry</button>}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TechPlanView.tsx
git commit -m "feat: add TechPlanView component for Design Gate"
```

---

### Task 12: BuildView component

**Files:**
- Create: `frontend/src/components/BuildView.tsx`

- [ ] **Step 1: Create BuildView.tsx**

```tsx
import { BuildArtifact } from '../api';

interface Props {
  build: BuildArtifact;
  loading?: boolean;
}

export default function BuildView({ build, loading }: Props) {
  const statusColor = build.status === 'success' ? '#16a34a' : '#dc2626';

  return (
    <div className="section">
      <h2>
        Build Artifact
        {!loading && (
          <span style={{ color: statusColor, marginLeft: 8 }}>
            {build.status === 'success' ? '✅ Success' : '❌ Failed'}
          </span>
        )}
        {loading && <span style={{ color: '#ca8a04', marginLeft: 8 }}>⏳ Building...</span>}
      </h2>

      <h3 style={{ marginTop: 8, fontSize: '1rem' }}>Files Created</h3>
      {build.files_created.length === 0 && <p style={{ color: '#999' }}>None</p>}
      <ul style={{ paddingLeft: 20 }}>
        {build.files_created.map((f, i) => (
          <li key={i} style={{ fontFamily: 'monospace', fontSize: '0.9rem' }}>+ {f}</li>
        ))}
      </ul>

      {build.files_modified.length > 0 && (
        <>
          <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Files Modified</h3>
          <ul style={{ paddingLeft: 20 }}>
            {build.files_modified.map((f, i) => (
              <li key={i} style={{ fontFamily: 'monospace', fontSize: '0.9rem', color: '#ca8a04' }}>✏️ {f}</li>
            ))}
          </ul>
        </>
      )}

      <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Docker Logs</h3>
      <div className="log-panel">
        {build.docker_logs.map((line, i) => (
          <div key={i} className="log-line">{line}</div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/BuildView.tsx
git commit -m "feat: add BuildView component with Docker log panel"
```

---

### Task 13: TestReportView component

**Files:**
- Create: `frontend/src/components/TestReportView.tsx`

- [ ] **Step 1: Create TestReportView.tsx**

```tsx
import { useState } from 'react';
import { TestReport } from '../api';

interface Props {
  report: TestReport;
  onApprove?: () => void;
  onRetry?: () => void;
  approved?: boolean;
}

export default function TestReportView({ report, onApprove, onRetry, approved }: Props) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const total = report.passed + report.failed + report.skipped;
  const statusColor = report.failed === 0 ? '#16a34a' : '#dc2626';

  return (
    <div className="section">
      <h2>
        Test Report
        {!approved && (
          <span style={{ color: statusColor, marginLeft: 8 }}>
            {report.failed === 0 ? '✅ All Passing' : `❌ ${report.failed} Failed`}
          </span>
        )}
        {approved && <span style={{ color: '#16a34a', marginLeft: 8 }}>✅ Approved</span>}
      </h2>

      <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
        <div className="stat-box" style={report.passed > 0 ? { borderColor: '#16a34a' } : {}}>
          <span className="stat-value" style={{ color: '#16a34a' }}>{report.passed}</span>
          <span className="stat-label">Passed</span>
        </div>
        <div className="stat-box" style={report.failed > 0 ? { borderColor: '#dc2626' } : {}}>
          <span className="stat-value" style={{ color: '#dc2626' }}>{report.failed}</span>
          <span className="stat-label">Failed</span>
        </div>
        <div className="stat-box">
          <span className="stat-value" style={{ color: '#666' }}>{report.skipped}</span>
          <span className="stat-label">Skipped</span>
        </div>
        {report.coverage_pct !== null && (
          <div className="stat-box">
            <span className="stat-value">{report.coverage_pct}%</span>
            <span className="stat-label">Coverage</span>
          </div>
        )}
      </div>

      {report.details.length > 0 && (
        <>
          <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Details</h3>
          {report.details.map((d, i) => (
            <div key={i} className="test-detail-item">
              <span
                className={`tag ${d.status === 'passed' ? 'tag-validated' : 'tag-open'}`}
                onClick={() => setExpanded(expanded === i ? null : i)}
                style={{ cursor: d.error_message ? 'pointer' : 'default' }}
              >
                {d.status === 'passed' ? '✅' : d.status === 'failed' ? '❌' : '⏭️'} {d.status}
              </span>
              <span style={{ fontSize: '0.9rem' }}>{d.test_name}</span>
              {expanded === i && d.error_message && (
                <div className="error-detail">{d.error_message}</div>
              )}
            </div>
          ))}
        </>
      )}

      {!approved && onApprove && (
        <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" onClick={onApprove}>✅ Approve Build</button>
          {onRetry && <button className="btn" onClick={onRetry}>🔄 Retry Build</button>}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TestReportView.tsx
git commit -m "feat: add TestReportView component for Prototype Gate"
```

---

### Task 14: Updated App.tsx with Phase 1 gate flow

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Replace App.tsx**

```tsx
import { useState } from 'react';
import { runLoop, resolveCritique, createPlan, createBuild, runTests, commitBuild, RunLoopResponse, TechPlan, BuildArtifact, TestReport } from './api';
import UnderstandingView from './components/UnderstandingView';
import CritiquePanel from './components/CritiquePanel';
import ConfidenceBadge from './components/ConfidenceBadge';
import TechPlanView from './components/TechPlanView';
import BuildView from './components/BuildView';
import TestReportView from './components/TestReportView';

type GateStep = 'goal' | 'understanding' | 'design' | 'build' | 'test' | 'commit' | 'done';

function App() {
  const [step, setStep] = useState<GateStep>('goal');
  const [goal, setGoal] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RunLoopResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [plan, setPlan] = useState<TechPlan | null>(null);
  const [build, setBuild] = useState<BuildArtifact | null>(null);
  const [testReport, setTestReport] = useState<TestReport | null>(null);
  const [commitSha, setCommitSha] = useState<string | null>(null);

  const handleRun = async () => {
    if (!goal.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await runLoop(goal.trim());
      setResult(data);
      setStep('understanding');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async (critiqueId: string, resolution: string) => {
    try {
      await resolveCritique(critiqueId, resolution);
      setResult((prev) => prev ? { ...prev, critique_resolved: true } : prev);
    } catch (e) {
      console.error('Resolve failed', e);
    }
  };

  const handlePlan = async () => {
    if (!result) return;
    setLoading(true);
    setError(null);
    try {
      const data = await createPlan(result.understanding.id);
      setPlan(data.plan);
      setStep('design');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Plan failed');
    } finally {
      setLoading(false);
    }
  };

  const handleBuild = async () => {
    if (!plan) return;
    setLoading(true);
    setError(null);
    try {
      const data = await createBuild(plan.plan_id);
      setBuild(data.build);
      setStep('build');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Build failed');
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async () => {
    if (!build) return;
    setLoading(true);
    setError(null);
    try {
      const data = await runTests(build.build_id);
      setTestReport(data.test_report);
      setStep('test');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Tests failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCommit = async () => {
    if (!build) return;
    const msg = `Brogrammer build ${build.build_id.slice(0, 8)}`;
    setLoading(true);
    setError(null);
    try {
      const data = await commitBuild(build.build_id, msg);
      if (data.success) {
        setCommitSha(data.commit_sha);
        setStep('done');
      } else {
        setError('Git commit failed');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Commit failed');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setStep('goal');
    setResult(null);
    setPlan(null);
    setBuild(null);
    setTestReport(null);
    setCommitSha(null);
    setError(null);
  };

  return (
    <div className="app">
      <h1>Brogrammer — Gate Flow</h1>

      {/* Gate indicators */}
      <div className="gate-steps">
        {(['goal', 'understanding', 'design', 'build', 'test', 'commit', 'done'] as GateStep[]).map((s, i) => (
          <div key={s} className={`gate-step ${step === s ? 'active' : ''} ${['done', 'commit'].includes(step) && i <= ['goal', 'understanding', 'design', 'build', 'test', 'commit', 'done'].indexOf(step) ? 'completed' : ''}`}>
            <div className="gate-step-number">
              {['done', 'commit'].includes(step) && i <= ['goal', 'understanding', 'design', 'build', 'test', 'commit', 'done'].indexOf(step) - 1 ? '✓' : i + 1}
            </div>
            <div className="gate-step-label">{s.charAt(0).toUpperCase() + s.slice(1)}</div>
          </div>
        ))}
      </div>

      <div className="goal-input">
        <input
          type="text"
          placeholder="Describe what you want to build..."
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleRun()}
          disabled={step !== 'goal'}
        />
        <button onClick={handleRun} disabled={loading || step !== 'goal'}>
          {loading ? 'Running...' : 'Start'}
        </button>
      </div>

      {error && <div className="section" style={{ color: '#dc2626' }}>❌ {error}</div>}

      {result && (
        <>
          <UnderstandingView understanding={result.understanding} />
          <CritiquePanel
            critique={result.critique}
            resolved={result.critique_resolved}
            onResolve={handleResolve}
          />
          <div className="section">
            <ConfidenceBadge profile={result.confidence} />
            {result.critique_resolved && step === 'understanding' && (
              <button className="btn btn-primary" onClick={handlePlan} style={{ marginTop: 12 }} disabled={loading}>
                {loading ? 'Planning...' : 'Proceed to Design Gate →'}
              </button>
            )}
          </div>
        </>
      )}

      {plan && (
        <TechPlanView
          plan={plan}
          onApprove={() => { handleBuild(); }}
          onRetry={handlePlan}
          approved={step !== 'design'}
        />
      )}

      {build && (
        <BuildView build={build} loading={loading && step === 'build'} />
      )}

      {build && step === 'build' && !loading && (
        <div className="section">
          <button className="btn btn-primary" onClick={handleTest} disabled={loading}>
            {loading ? 'Testing...' : 'Proceed to Test Gate →'}
          </button>
        </div>
      )}

      {testReport && (
        <TestReportView
          report={testReport}
          onApprove={handleCommit}
          onRetry={handleBuild}
          approved={step !== 'test'}
        />
      )}

      {step === 'commit' && !loading && (
        <div className="section">
          <p style={{ marginBottom: 8 }}>Ready to commit to Git?</p>
          <button className="btn btn-primary" onClick={handleCommit}>Commit Build</button>
        </div>
      )}

      {step === 'done' && (
        <div className="section">
          <h2>✅ Phase Complete</h2>
          {commitSha && <p>Committed: <code>{commitSha}</code></p>}
          <button className="btn" onClick={handleReset} style={{ marginTop: 8 }}>Start New</button>
        </div>
      )}
    </div>
  );
}

export default App;
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: implement Phase 1 multi-step gate flow"
```

---

### Task 15: CSS for new components

**Files:**
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Add new CSS classes**

Append to `frontend/src/App.css`:

```css
/* Gate steps bar */
.gate-steps {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  overflow-x: auto;
}

.gate-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  min-width: 60px;
}

.gate-step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #e0e0e0;
  color: #999;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.85rem;
  margin-bottom: 4px;
}

.gate-step.active .gate-step-number {
  background: #2563eb;
  color: #fff;
}

.gate-step.completed .gate-step-number {
  background: #16a34a;
  color: #fff;
}

.gate-step-label {
  font-size: 0.7rem;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.gate-step.active .gate-step-label {
  color: #2563eb;
  font-weight: 600;
}

/* Buttons */
.btn {
  padding: 8px 16px;
  border: 1px solid #ccc;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 0.9rem;
}

.btn:hover {
  background: #f0f0f0;
}

.btn-primary {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}

.btn-primary:hover {
  background: #1d4ed8;
}

/* Log panel */
.log-panel {
  background: #1e1e1e;
  color: #d4d4d4;
  font-family: 'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  padding: 12px;
  border-radius: 6px;
  max-height: 300px;
  overflow-y: auto;
  margin-top: 8px;
}

.log-line {
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.4;
}

/* Stats boxes */
.stat-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 20px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  min-width: 80px;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
}

.stat-label {
  font-size: 0.75rem;
  color: #666;
  text-transform: uppercase;
}

/* Test details */
.test-detail-item {
  padding: 6px 0;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
}

.error-detail {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 4px;
  padding: 8px;
  margin-top: 4px;
  font-family: monospace;
  font-size: 0.85rem;
  white-space: pre-wrap;
}
```

- [ ] **Step 2: Verify TypeScript compiles (CSS doesn't affect compilation)**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.css
git commit -m "feat: add CSS for Phase 1 gate flow and components"
```

---

### Task 16: Integration tests for full Phase 1 flow

**Files:**
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Add Phase 1 integration test**

Append to `tests/test_integration.py`:

```python
@pytest.mark.asyncio
async def test_full_gate_flow_with_mocks():
    """Test the full gate flow with mock agents."""
    from unittest.mock import AsyncMock
    from backend.agents.planner import PlannerAgent
    from backend.agents.builder import BuilderAgent
    from backend.agents.qa import QAAgent
    from backend.core.models import (
        Understanding, MandatoryCategories, TechPlan,
        FileSpec, ComponentSpec, BuildArtifact, TestReport, TestResult, TestPlan,
    )

    mock_planner = AsyncMock(spec=PlannerAgent)
    mock_planner.generate_plan.return_value = TechPlan(
        understanding_id="u1",
        tech_stack=["Python"],
        file_tree=[FileSpec(path="main.py", purpose="Entry", content_type="code")],
        components=[ComponentSpec(name="App", responsibility="Run")],
        markdown_summary="test",
    )

    mock_builder = AsyncMock(spec=BuilderAgent)
    mock_builder.build.return_value = BuildArtifact(
        plan_id="p1",
        files_created=["main.py"],
        files_modified=[],
        docker_logs=["build ok"],
        status="success",
    )

    mock_qa = AsyncMock(spec=QAAgent)
    mock_qa.generate_test_plan.return_value = TestPlan(
        build_id="b1",
        framework="pytest",
        test_files=[],
        acceptance_criteria=["pass"],
    )
    mock_qa.run_tests.return_value = TestReport(
        build_id="b1",
        passed=2,
        failed=0,
        skipped=0,
        details=[TestResult(test_name="test_a", status="passed")],
    )

    from backend.orchestrator.gates import create_app
    app = create_app(
        db_path=":memory:",
        planner=mock_planner,
        builder=mock_builder,
        qa=mock_qa,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        plan_resp = await client.post("/api/plan", json={"understanding_id": "u1"})
        assert plan_resp.status_code == 200

        build_resp = await client.post("/api/build", json={"plan_id": "p1"})
        assert build_resp.status_code == 200
        build_data = build_resp.json()
        assert build_data["build"]["status"] == "success"

        test_resp = await client.post("/api/test", json={"build_id": "b1"})
        assert test_resp.status_code == 200
        test_data = test_resp.json()
        assert test_data["test_report"]["passed"] == 2
        assert test_data["test_report"]["failed"] == 0

        commit_resp = await client.post("/api/commit", json={"build_id": "b1", "message": "test"})
        assert commit_resp.status_code == 200
```

- [ ] **Step 2: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/test_integration.py::test_full_gate_flow_with_mocks -v
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add Phase 1 full gate flow integration test"
```

---

### Task 17: Final verification

- [ ] **Step 1: Run all backend tests**

Run:
```bash
source .venv/bin/activate && python -m pytest ../tests/ -v 2>&1 | tail -5
```
Expected: All tests pass

- [ ] **Step 2: Verify frontend compiles**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: No type errors

- [ ] **Step 3: Verify all new files are tracked**

Run:
```bash
git status
```
Expected: All new files committed, no dirty state
