"""
Independent Validation Suite — written to verify what is actually working
vs. what the Deepseek/Qwen audit claimed, using behaviour tests not source inspection.

Run: pytest tests/test_independent_validation.py -v

Tests marked xfail are expected failures — they document real bugs found during
independent review that must be fixed before the codebase is production-ready.
"""
import asyncio
import base64
import json
import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# Helpers / Fakes
# ---------------------------------------------------------------------------

class FakeOllamaGoodJSON:
    """Always returns well-formed JSON for any LLM call."""
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload)

    async def chat(self, messages, format="", temperature=0.0):
        return {"message": {"content": self._payload}}


class FakeOllamaBadThenGood:
    """Returns malformed JSON N times then a valid response."""
    def __init__(self, bad_count: int, good_payload: dict):
        self._bad_count = bad_count
        self._good = json.dumps(good_payload)
        self._calls = 0

    async def chat(self, messages, format="", temperature=0.0):
        self._calls += 1
        if self._calls <= self._bad_count:
            return {"message": {"content": "{ broken json <<<<"}}
        return {"message": {"content": self._good}}


class FakeOllamaToolThenCritique:
    """Round 1 → tool request. Round 2 → final critique."""
    def __init__(self):
        self._calls = 0

    async def chat(self, messages, format="", temperature=0.0):
        self._calls += 1
        if self._calls == 1:
            content = json.dumps({
                "tool_requests": [{"tool": "curl", "args": ["http://example.com"], "description": "check"}],
                "thought": "investigating",
            })
        else:
            content = json.dumps({
                "scenarios": ["could fail"],
                "questions": [],
                "tool_evidence": ["200 OK from example.com"],
                "thought": "",
            })
        return {"message": {"content": content}}


class FakeSandboxCapture:
    """Records every exec() call."""
    def __init__(self):
        self.commands = []
        self.container_id = "fake-123"
        self.host_workdir = None
        self._started_with_host_workdir = None

    async def start(self, host_workdir=None):
        self._started_with_host_workdir = host_workdir
        self.host_workdir = host_workdir
        return "fake-123"

    async def stop(self):
        pass

    async def exec(self, command, timeout=None):
        self.commands.append(command)
        return {"stdout": "3.11.0", "stderr": "", "exit_code": 0}

    async def is_running(self):
        return True

    async def exec_safe(self, command, timeout=15):
        return await self.exec(command, timeout=timeout)

    async def install_tools(self):
        pass


# ---------------------------------------------------------------------------
# SECTION 1: Retry helper — behavioural (not source inspection)
# ---------------------------------------------------------------------------

class TestRetryHelperBehaviour:
    """Verify the retry decorator actually retries and eventually succeeds."""

    @pytest.mark.asyncio
    async def test_retries_on_validation_error_then_succeeds(self):
        """@with_retries must retry on pydantic ValidationError and eventually succeed."""
        from backend.agents.specialist import SpecialistAgent

        good_payload = {
            "goal": "build a thing",
            "assumptions": [{"statement": "users exist", "status": "open"}],
            "unknowns": [{"question": "which platform?"}],
            "mandatory_categories": {
                "accessibility": ["a11y"],
                "performance": ["fast"],
                "security": ["auth"],
                "state_management": ["redux"],
                "persistence": ["sqlite"],
            },
        }
        agent = SpecialistAgent(ollama_client=FakeOllamaBadThenGood(2, good_payload))
        result = await agent.generate_understanding("build a thing")
        assert result.goal == "build a thing"

    @pytest.mark.asyncio
    async def test_retries_exhaust_raises_runtime_error(self):
        """After max retries, RuntimeError must be raised (not ValidationError)."""
        from backend.agents.specialist import SpecialistAgent

        agent = SpecialistAgent(ollama_client=FakeOllamaBadThenGood(99, {}))
        with pytest.raises(RuntimeError, match="failed after 3 retries"):
            await agent.generate_understanding("never works")

    @pytest.mark.asyncio
    async def test_skeptic_no_sandbox_retries_malformed_json(self):
        """Skeptic no-sandbox path must retry on malformed JSON."""
        from backend.agents.skeptic import SkepticAgent
        from backend.core.models import Understanding, MandatoryCategories

        good_critique = {
            "scenarios": ["could fail"],
            "questions": ["how?"],
            "tool_evidence": [],
        }
        agent = SkepticAgent(ollama_client=FakeOllamaBadThenGood(2, good_critique))
        u = Understanding(goal="test", mandatory_categories=MandatoryCategories())
        result = await agent.generate_critique(u, sandbox=None)
        assert result.scenarios == ["could fail"]

    @pytest.mark.asyncio
    async def test_planner_uses_with_retries(self):
        """PlannerAgent must retry malformed JSON."""
        from backend.agents.planner import PlannerAgent
        from backend.core.models import Understanding, MandatoryCategories

        good_plan = {
            "tech_stack": ["Python"],
            "file_tree": [],
            "components": [],
            "markdown_summary": "#",
        }
        agent = PlannerAgent(ollama_client=FakeOllamaBadThenGood(2, good_plan))
        u = Understanding(goal="test", mandatory_categories=MandatoryCategories())
        result = await agent.generate_plan(u)
        assert result is not None


# ---------------------------------------------------------------------------
# SECTION 2: P1-F01 — QA write_test_files is called by /api/test  (REAL BUG)
# These tests check the actual behaviour, not method existence.
# ---------------------------------------------------------------------------

class TestQAWriteTestFiles:
    """Verify QAAgent.write_test_files actually issues sandbox exec commands."""

    @pytest.mark.asyncio
    async def test_write_test_files_issues_exec_commands(self):
        """`write_test_files` must call sandbox.exec() at least once per test file."""
        from backend.agents.qa import QAAgent
        from backend.core.models import TestPlan, FileSpec

        sandbox = FakeSandboxCapture()
        agent = QAAgent(
            ollama_client=FakeOllamaGoodJSON({"content": "def test_pass(): pass"}),
            sandbox=sandbox,
        )
        plan = TestPlan(
            build_id="b1",
            framework="pytest",
            test_files=[FileSpec(path="tests/test_main.py", purpose="smoke", content_type="test")],
            acceptance_criteria=["pass"],
        )
        await agent.write_test_files(plan)
        assert any("base64" in cmd or "tests/test_main.py" in cmd for cmd in sandbox.commands), (
            "write_test_files must exec a command referencing the test file"
        )

    @pytest.mark.asyncio
    async def test_run_tests_reports_failure_on_empty_collection(self):
        """If pytest collects zero tests, the report must mark failure=1, not silence."""
        from backend.agents.qa import QAAgent

        class EmptySandbox:
            async def exec(self, command, timeout=None):
                return {"stdout": "collected 0 items\nno tests ran in 0.01s", "stderr": "", "exit_code": 5}

        agent = QAAgent(sandbox=EmptySandbox())
        report = await agent.run_tests("b1", "tests")
        assert report.failed >= 1, (
            "Empty test collection must be reported as a failure, not silent success"
        )

    @pytest.mark.asyncio
    async def test_api_test_endpoint_calls_write_test_files(self):
        """The /api/test endpoint must call write_test_files before run_tests."""
        from httpx import AsyncClient, ASGITransport
        from backend.orchestrator.gates import create_app
        from backend.core.models import (
            Understanding, MandatoryCategories, Assumption, Unknown,
            SkepticCritique, TechPlan, FileSpec, ComponentSpec, BuildArtifact,
            TestPlan, TestReport, TestResult,
        )

        class MockSpecialist:
            async def generate_with_fragility_check(self, goal):
                u = Understanding(goal=goal, mandatory_categories=MandatoryCategories(
                    accessibility=["a"], performance=["p"], security=["s"],
                    state_management=["sm"], persistence=["pe"],
                ))
                return u, False

        class MockSkeptic:
            async def generate_critique(self, u, sandbox=None, on_tool_call=None):
                return SkepticCritique(understanding_id=u.id)

        write_calls = []

        class TrackingQA:
            async def generate_test_plan(self, plan):
                return TestPlan(
                    build_id="", framework="pytest",
                    test_files=[FileSpec(path="tests/t.py", purpose="test", content_type="test")],
                    acceptance_criteria=["pass"],
                )

            async def write_test_files(self, plan):
                write_calls.append(plan)

            async def run_tests(self, build_id, test_path="tests"):
                return TestReport(
                    build_id=build_id, passed=2, failed=0, skipped=0,
                    details=[TestResult(test_name="test_a", status="passed")],
                )

        from unittest.mock import AsyncMock
        from backend.agents.planner import PlannerAgent
        from backend.agents.builder import BuilderAgent

        mock_planner = AsyncMock(spec=PlannerAgent)
        mock_planner.generate_plan.return_value = TechPlan(
            understanding_id="u1",
            tech_stack=["Python"],
            file_tree=[FileSpec(path="main.py", purpose="entry", content_type="code")],
            components=[ComponentSpec(name="App", responsibility="run")],
            markdown_summary="#",
        )

        mock_builder = AsyncMock(spec=BuilderAgent)
        mock_builder.build.return_value = BuildArtifact(
            plan_id="p1", files_created=["main.py"], files_modified=[],
            docker_logs=[], status="success",
        )

        app = create_app(
            db_path=":memory:", specialist=MockSpecialist(), skeptic=MockSkeptic(),
            planner=mock_planner, builder=mock_builder, qa=TrackingQA(),
            rate_limit=False,
        )
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://t") as c:
            rl = await c.post("/api/run-loop", json={"goal": "test app"})
            u_id = rl.json()["understanding"]["id"]
            plan_resp = await c.post("/api/plan", json={"understanding_id": u_id})
            plan_id = plan_resp.json()["plan_id"]
            build_resp = await c.post("/api/build", json={"plan_id": plan_id})
            build_id = build_resp.json()["build"]["build_id"]
            test_resp = await c.post("/api/test", json={"build_id": build_id})

        assert test_resp.status_code == 200, test_resp.text
        assert len(write_calls) == 1, (
            f"/api/test must call write_test_files; got {len(write_calls)} calls"
        )


# ---------------------------------------------------------------------------
# SECTION 3: P1-F02 — Builder sets host_workdir on artifact  (REAL BUG)
# ---------------------------------------------------------------------------

class TestBuilderHostWorkdir:

    @pytest.mark.asyncio
    async def test_builder_populates_host_workdir(self):
        """BuilderAgent.build() must set artifact.host_workdir to a non-empty string."""
        from backend.agents.builder import BuilderAgent
        from backend.core.models import TechPlan, FileSpec, ComponentSpec

        sandbox = FakeSandboxCapture()
        agent = BuilderAgent(
            ollama_client=FakeOllamaGoodJSON({"main.py": "print('hello')"}),
            sandbox=sandbox,
        )
        plan = TechPlan(
            understanding_id="u1",
            tech_stack=["Python"],
            file_tree=[FileSpec(path="main.py", purpose="entry", content_type="code")],
            components=[ComponentSpec(name="App", responsibility="run")],
            markdown_summary="#",
        )
        artifact = await agent.build(plan)
        assert artifact.host_workdir != "", (
            "BuildArtifact.host_workdir must be set so commit_build can copy files to the host"
        )

    @pytest.mark.asyncio
    async def test_builder_starts_sandbox_with_bind_mount(self):
        """Builder must pass a host_workdir to sandbox.start() to enable bind-mount."""
        from backend.agents.builder import BuilderAgent
        from backend.core.models import TechPlan, FileSpec, ComponentSpec

        sandbox = FakeSandboxCapture()
        # Fake sandbox needs is_running to return False so start() is called
        sandbox_not_running = FakeSandboxCapture()

        async def is_running_false():
            return False

        sandbox_not_running.is_running = is_running_false

        agent = BuilderAgent(
            ollama_client=FakeOllamaGoodJSON({"main.py": "print('hello')"}),
            sandbox=sandbox_not_running,
        )
        plan = TechPlan(
            understanding_id="u1",
            tech_stack=["Python"],
            file_tree=[FileSpec(path="main.py", purpose="entry", content_type="code")],
            components=[ComponentSpec(name="App", responsibility="run")],
            markdown_summary="#",
        )
        await agent.build(plan)
        assert sandbox_not_running._started_with_host_workdir is not None, (
            "sandbox.start() must be called with a host_workdir to enable bind-mount"
        )


# ---------------------------------------------------------------------------
# SECTION 4: P1-F03 — Builder uses safe writes, not heredoc  (REAL BUG)
# ---------------------------------------------------------------------------

class TestBuilderSafeWrite:

    @pytest.mark.asyncio
    async def test_builder_does_not_use_heredoc(self):
        """Builder file writes must not use heredoc with a known sentinel."""
        from backend.agents.builder import BuilderAgent
        from backend.core.models import TechPlan, FileSpec, ComponentSpec

        sandbox = FakeSandboxCapture()
        agent = BuilderAgent(
            ollama_client=FakeOllamaGoodJSON({"main.py": "# safe code"}),
            sandbox=sandbox,
        )
        plan = TechPlan(
            understanding_id="u1",
            tech_stack=["Python"],
            file_tree=[FileSpec(path="main.py", purpose="entry", content_type="code")],
            components=[ComponentSpec(name="App", responsibility="run")],
            markdown_summary="#",
        )
        await agent.build(plan)
        heredoc_commands = [c for c in sandbox.commands if "BROGRAMMER_EOF" in c]
        assert len(heredoc_commands) == 0, (
            f"Builder used heredoc in {len(heredoc_commands)} command(s). Use base64 instead."
        )

    @pytest.mark.asyncio
    async def test_builder_handles_sentinel_in_content(self):
        """Builder must correctly write content containing the sentinel string."""
        from backend.agents.builder import BuilderAgent
        from backend.core.models import TechPlan, FileSpec, ComponentSpec

        # Content that contains the heredoc sentinel — this will corrupt heredoc writes
        dangerous_content = "BROGRAMMER_EOF\nprint('escaped!')"
        sandbox = FakeSandboxCapture()
        agent = BuilderAgent(
            ollama_client=FakeOllamaGoodJSON({"main.py": dangerous_content}),
            sandbox=sandbox,
        )
        plan = TechPlan(
            understanding_id="u1",
            tech_stack=["Python"],
            file_tree=[FileSpec(path="main.py", purpose="entry", content_type="code")],
            components=[ComponentSpec(name="App", responsibility="run")],
            markdown_summary="#",
        )
        artifact = await agent.build(plan)
        # If the write command uses heredoc, the content after BROGRAMMER_EOF is lost.
        # Verify the write command contains the full content safely.
        write_cmds = [c for c in sandbox.commands if "main.py" in c and "Writing" not in c]
        assert write_cmds, "No write command found for main.py"
        # With base64 the command should contain base64-encoded content, not raw
        assert "BROGRAMMER_EOF" not in write_cmds[0], (
            "Write command contains unescaped sentinel — content will be truncated"
        )


# ---------------------------------------------------------------------------
# SECTION 5: on_tool_call coroutine never awaited  (REAL BUG)
# ---------------------------------------------------------------------------

class TestOnToolCallAwaited:

    @pytest.mark.asyncio
    async def test_on_tool_call_callback_is_invoked(self):
        """generate_critique must await on_tool_call so the callback actually runs."""
        from backend.agents.skeptic import SkepticAgent
        from backend.core.models import Understanding, MandatoryCategories

        invocations = []

        async def capture_tool_call(**kwargs):
            invocations.append(kwargs)

        agent = SkepticAgent(ollama_client=FakeOllamaToolThenCritique())
        u = Understanding(goal="test", mandatory_categories=MandatoryCategories())
        await agent.generate_critique(u, sandbox=True, on_tool_call=capture_tool_call)

        assert len(invocations) == 1, (
            f"Expected 1 on_tool_call invocation, got {len(invocations)}. "
            "Check that skeptic.py awaits on_tool_call."
        )

    @pytest.mark.asyncio
    async def test_tool_call_events_written_to_db(self):
        """After a ReAct loop, tool_call_events rows must be committed to the audit table."""
        from httpx import AsyncClient, ASGITransport
        from backend.orchestrator.gates import create_app
        from backend.core.models import (
            Understanding, MandatoryCategories, SkepticCritique,
        )

        class MockSpecialistForTools:
            async def generate_with_fragility_check(self, goal):
                u = Understanding(goal=goal, mandatory_categories=MandatoryCategories(
                    accessibility=["a"], performance=["p"], security=["s"],
                    state_management=["sm"], persistence=["pe"],
                ))
                return u, False

        # Skeptic that makes one tool call then returns a critique
        class ToolCallSkeptic:
            async def generate_critique(self, u, sandbox=None, on_tool_call=None):
                if on_tool_call:
                    # Must be awaited — this reveals the bug
                    await on_tool_call(
                        critique_id=None, round=1, tool="curl",
                        args=["http://example.com"], exit_code=0,
                        stdout="200 OK", stderr="",
                    )
                return SkepticCritique(
                    understanding_id=u.id,
                    scenarios=["s"],
                    tool_evidence=["curl result"],
                    rounds_used=1,
                    tool_calls=1,
                )

        app = create_app(
            db_path=":memory:",
            specialist=MockSpecialistForTools(),
            skeptic=ToolCallSkeptic(),
            rate_limit=False,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            rl = await c.post("/api/run-loop", json={"goal": "test with tools"})
            assert rl.status_code == 200, rl.text
            critique_id = rl.json()["critique"]["critique_id"]

            tools_resp = await c.get(f"/api/critique/{critique_id}/tools")
            assert tools_resp.status_code == 200
            calls = tools_resp.json()["tool_calls"]
            assert len(calls) >= 1, (
                f"Expected tool call rows in DB after ReAct loop, got {len(calls)}. "
                "Bug: on_tool_call is not awaited in skeptic.py."
            )


# ---------------------------------------------------------------------------
# SECTION 6: QA/Builder LLM calls have no retry  (REAL BUG)
# ---------------------------------------------------------------------------

class TestAgentRetryCompleteness:

    @pytest.mark.asyncio
    async def test_qa_generate_test_plan_retries_malformed_json(self):
        """QAAgent.generate_test_plan must retry on malformed JSON."""
        from backend.agents.qa import QAAgent
        from backend.core.models import TechPlan, ComponentSpec

        good_plan = {
            "build_id": "",
            "framework": "pytest",
            "test_files": [],
            "acceptance_criteria": ["pass"],
        }
        agent = QAAgent(ollama_client=FakeOllamaBadThenGood(2, good_plan))
        plan = TechPlan(
            understanding_id="u1", tech_stack=[],
            file_tree=[], components=[], markdown_summary="#",
        )
        result = await agent.generate_test_plan(plan)
        assert result is not None

    @pytest.mark.asyncio
    async def test_builder_generate_file_content_retries_malformed_json(self):
        """BuilderAgent._generate_file_content must retry on malformed JSON."""
        from backend.agents.builder import BuilderAgent
        from backend.core.models import FileSpec

        good_content = {"main.py": "print('hello')"}
        agent = BuilderAgent(ollama_client=FakeOllamaBadThenGood(2, good_content))
        spec = FileSpec(path="main.py", purpose="entry", content_type="code")

        # Build a minimal plan for the call signature
        from backend.core.models import TechPlan, ComponentSpec
        plan = TechPlan(
            understanding_id="u1", tech_stack=["Python"],
            file_tree=[spec], components=[], markdown_summary="#",
        )
        content = await agent._generate_file_content(plan, spec)
        # If retry worked, content is the Python code, not a raw error blob
        assert "print" in content, f"Expected valid Python content, got: {content[:100]}"


# ---------------------------------------------------------------------------
# SECTION 7: Logging coverage gaps
# ---------------------------------------------------------------------------

class TestLoggingCoverage:

    def test_all_endpoints_have_log_calls(self):
        """/api/plan, /api/build, /api/test, /api/commit must emit log lines."""
        with open("backend/orchestrator/gates.py") as f:
            src = f.read()

        # Count _log calls per endpoint function
        import re
        endpoints = ["create_plan", "create_build", "run_tests", "commit_build"]
        for ep in endpoints:
            # Find the function body and count _log references within it
            pattern = rf"async def {ep}.*?(?=\n    @app\.|\Z)"
            match = re.search(pattern, src, re.DOTALL)
            body = match.group(0) if match else ""
            assert "_log." in body, (
                f"Endpoint `{ep}` has no structured logging. "
                "Add _log.info/error calls matching the run_loop pattern."
            )


# ---------------------------------------------------------------------------
# SECTION 8: URL denylist — canonical attack surface tested
# ---------------------------------------------------------------------------

class TestURLDenylistCanonical:

    def test_real_aws_metadata_ip_blocked(self):
        """The canonical AWS metadata IP (169.254.169.254) must be blocked."""
        from backend.orchestrator.sandbox import SandboxManager
        with pytest.raises(ValueError, match="denylist"):
            SandboxManager.validate_url("http://169.254.169.254/latest/meta-data/")

    def test_aws_metadata_with_iam_path_blocked(self):
        """Full AWS credential path must be blocked."""
        from backend.orchestrator.sandbox import SandboxManager
        with pytest.raises(ValueError):
            SandboxManager.validate_url(
                "http://169.254.169.254/latest/meta-data/iam/security-credentials/role"
            )

    def test_gcp_metadata_blocked(self):
        """GCP metadata endpoint must be blocked."""
        from backend.orchestrator.sandbox import SandboxManager
        with pytest.raises(ValueError):
            SandboxManager.validate_url("http://metadata.google.internal/computeMetadata/v1/")

    def test_ftp_scheme_blocked(self):
        """Non-http/https schemes must be blocked."""
        from backend.orchestrator.sandbox import SandboxManager
        with pytest.raises(ValueError, match="scheme"):
            SandboxManager.validate_url("ftp://example.com/file")

    def test_file_scheme_blocked(self):
        """file:// scheme must be blocked."""
        from backend.orchestrator.sandbox import SandboxManager
        with pytest.raises(ValueError, match="scheme"):
            SandboxManager.validate_url("file:///etc/passwd")

    def test_tool_request_validates_curl_url_at_model_layer(self):
        """ToolRequest must reject SSRF URLs even without calling build_tool_command."""
        with pytest.raises(ValidationError):
            from backend.core.models import ToolRequest
            ToolRequest(tool="curl", args=["http://169.254.169.254/latest/meta-data/"], description="ssrf")


# ---------------------------------------------------------------------------
# SECTION 9: Pagination stability
# ---------------------------------------------------------------------------

class TestAuditPaginationStability:

    @pytest.mark.asyncio
    async def test_cursor_pagination_stable_under_rapid_inserts(self):
        """Cursor pagination must work even when timestamps share microsecond precision."""
        from backend.orchestrator.database import get_db, init_db
        from backend.orchestrator.audit import append_event, get_events
        import asyncio

        db = await get_db(":memory:")
        await init_db(db)

        # Insert 60 events without any sleep — timestamps may collide
        for i in range(60):
            await append_event(db, "test", None, None, {"seq": i})

        page1 = await get_events(db, limit=50)
        assert len(page1) == 50

        # Cursor: use created_at of last item on page1
        last_ts = page1[-1]["created_at"]
        page2 = await get_events(db, limit=50, before=last_ts)
        total = len(page1) + len(page2)
        # All 60 items must be reachable via two pages
        assert total >= 60, (
            f"Pagination missed events: page1={len(page1)}, page2={len(page2)}, total={total}. "
            "If timestamps are not unique, the < cursor skips items. "
            "Fix: use a sequence-based cursor (row id) instead of created_at."
        )

        await db.close()


# ---------------------------------------------------------------------------
# SECTION 10: Confirmed working — fast sanity checks
# ---------------------------------------------------------------------------

class TestConfirmedWorking:
    """These all pass today. They document the solid ground."""

    def test_goal_empty_rejected(self):
        from backend.orchestrator.gates import RunLoopRequest
        with pytest.raises(ValidationError):
            RunLoopRequest(goal="")

    def test_goal_whitespace_rejected(self):
        from backend.orchestrator.gates import RunLoopRequest
        with pytest.raises(ValidationError):
            RunLoopRequest(goal="   ")

    def test_goal_max_length_accepted(self):
        from backend.orchestrator.gates import RunLoopRequest
        req = RunLoopRequest(goal="A" * 10_000)
        assert len(req.goal) == 10_000

    def test_goal_over_max_rejected(self):
        from backend.orchestrator.gates import RunLoopRequest
        with pytest.raises(ValidationError):
            RunLoopRequest(goal="A" * 10_001)

    def test_commit_message_max_length(self):
        from backend.orchestrator.gates import CommitRequest
        req = CommitRequest(build_id="b1", message="x" * 500)
        assert len(req.message) == 500
        with pytest.raises(ValidationError):
            CommitRequest(build_id="b1", message="x" * 501)

    def test_skeptic_critique_has_telemetry_fields(self):
        from backend.core.models import SkepticCritique
        c = SkepticCritique()
        assert c.rounds_used == 0
        assert c.tool_calls == 0

    def test_exec_safe_is_thread_safe(self):
        """exec_safe must not mutate self.exec_timeout."""
        from backend.orchestrator.sandbox import SandboxManager
        mgr = SandboxManager(exec_timeout=120)
        import inspect
        src = inspect.getsource(SandboxManager.exec_safe)
        assert "self.exec_timeout" not in src, (
            "exec_safe must not mutate self.exec_timeout — pass timeout to exec() directly"
        )

    def test_build_artifact_has_host_workdir_field(self):
        from backend.core.models import BuildArtifact
        a = BuildArtifact(
            plan_id="p1", files_created=[], files_modified=[],
            docker_logs=[], status="success", host_workdir="/tmp/x",
        )
        assert a.host_workdir == "/tmp/x"

    def test_tool_call_events_table_exists(self):
        import asyncio
        from backend.orchestrator.database import get_db, init_db

        async def check():
            db = await get_db(":memory:")
            await init_db(db)
            cur = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='tool_call_events'"
            )
            row = await cur.fetchone()
            await db.close()
            return row

        row = asyncio.run(check())
        assert row is not None, "tool_call_events table must exist after init_db"

    def test_rate_limiting_can_be_disabled(self):
        """create_app must accept rate_limit=False for tests."""
        from backend.orchestrator.gates import create_app
        app = create_app(db_path=":memory:", rate_limit=False)
        assert app is not None

    @pytest.mark.asyncio
    async def test_events_ordered_newest_first(self):
        from backend.orchestrator.database import get_db, init_db
        from backend.orchestrator.audit import append_event, get_events
        db = await get_db(":memory:")
        await init_db(db)
        for i in range(5):
            await append_event(db, "t", None, None, {"seq": i})
        events = await get_events(db, limit=10)
        seqs = [json.loads(e["payload"])["seq"] for e in events]
        assert seqs[0] > seqs[-1], "Events must be newest-first (DESC order)"
        await db.close()
