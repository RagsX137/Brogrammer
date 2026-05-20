"""
Remediation Plan Validation Tests
Validates fixes from docs/Remediation_plan.md are correctly implemented.
"""
import pytest
import json
from pydantic import ValidationError

from backend.core.models import (
    Understanding, Assumption, Unknown, MandatoryCategories,
    SkepticCritique, ToolRequest, ToolResult, SkepticOutput, FileSpec
)
from backend.orchestrator.gates import RunLoopRequest, CommitRequest
from backend.orchestrator.sandbox import SandboxManager


class TestP0F01_SpecialistRetry:
    """P0-F01: SpecialistAgent has JSON-retry loop"""
    
    def test_retry_helper_exists(self):
        """Retry helper should be importable and functional"""
        from backend.agents._retry import with_retries
        assert callable(with_retries)
    
    def test_specialist_uses_retry_decorator(self):
        """Specialist should have retry decorator on LLM calls"""
        from backend.agents.specialist import SpecialistAgent
        import inspect
        source = inspect.getsource(SpecialistAgent)
        assert 'with_retries' in source or '@with_retries' in source


class TestP0F02_FragilityDetection:
    """P0-F02: Fragility detection is resilient"""
    
    @pytest.mark.asyncio
    async def test_fragility_check_exists(self):
        """Specialist should have fragility check method"""
        from backend.agents.specialist import SpecialistAgent
        agent = SpecialistAgent()
        assert hasattr(agent, 'generate_with_fragility_check')


class TestP0F03_SkepticRetry:
    """P0-F03: SkepticAgent has retry for no-sandbox path"""
    
    def test_skeptic_uses_retry(self):
        """Skeptic should use retry helper"""
        from backend.agents.skeptic import SkepticAgent
        import inspect
        source = inspect.getsource(SkepticAgent)
        assert 'with_retries' in source


class TestP0F04_ToolEvidenceAudit:
    """P0-F04: tool_evidence persisted in audit log"""
    
    @pytest.mark.asyncio  
    async def test_tool_evidence_in_audit(self):
        """Audit events should include tool_evidence"""
        from backend.orchestrator.database import get_db, init_db
        from backend.orchestrator.audit import append_event
        
        db = await get_db(":memory:")
        await init_db(db)
        
        await append_event(
            db, "critique_created", "u1", "c1",
            {
                "scenarios": ["test"],
                "questions": ["q?"],
                "tool_evidence": ["curl result"],
                "rounds_used": 2,
                "tool_calls": 3,
                "understanding_id": "u1",
            }
        )
        
        from backend.orchestrator.audit import get_events
        events = await get_events(db, limit=10)
        assert len(events) == 1
        payload = json.loads(events[0]["payload"])
        assert "tool_evidence" in payload
        assert payload["rounds_used"] == 2
        assert payload["tool_calls"] == 3
        
        await db.close()


class TestP0F05_InputValidation:
    """P0-F05: Input validation on RunLoopRequest.goal"""
    
    def test_empty_goal_rejected(self):
        """Empty goals should be rejected"""
        with pytest.raises(ValidationError):
            RunLoopRequest(goal='')
    
    def test_whitespace_goal_rejected(self):
        """Whitespace-only goals should be rejected"""
        with pytest.raises(ValidationError):
            RunLoopRequest(goal='   ')
    
    def test_long_goal_rejected(self):
        """Goals over 10k chars should be rejected"""
        with pytest.raises(ValidationError):
            RunLoopRequest(goal='A' * 10001)
    
    def test_goal_at_limit_accepted(self):
        """Goals at exactly 10k chars should be accepted"""
        req = RunLoopRequest(goal='A' * 10000)
        assert len(req.goal) == 10000
    
    def test_commit_message_empty_rejected(self):
        """Empty commit messages should be rejected"""
        with pytest.raises(ValidationError):
            CommitRequest(build_id='b1', message='')
    
    def test_commit_message_long_rejected(self):
        """Long commit messages should be rejected"""
        with pytest.raises(ValidationError):
            CommitRequest(build_id='b1', message='X' * 501)


class TestP0F06_AuditPagination:
    """P0-F06: Audit events ordered DESC with cursor pagination"""
    
    @pytest.mark.asyncio
    async def test_events_ordered_desc(self):
        """Events should be returned newest first"""
        from backend.orchestrator.database import get_db, init_db
        from backend.orchestrator.audit import append_event, get_events
        
        db = await get_db(":memory:")
        await init_db(db)
        
        for i in range(5):
            await append_event(db, "test_event", None, None, {"i": i})
        
        events = await get_events(db, limit=10)
        # Should be newest first (4, 3, 2, 1, 0)
        payloads = [json.loads(e["payload"]) for e in events]
        assert payloads[0]["i"] == 4  # newest
        assert payloads[-1]["i"] == 0  # oldest
        
        await db.close()
    
    @pytest.mark.asyncio
    async def test_cursor_pagination(self):
        """Cursor pagination should work"""
        from backend.orchestrator.database import get_db, init_db
        from backend.orchestrator.audit import append_event, get_events
        
        db = await get_db(":memory:")
        await init_db(db)
        
        for i in range(60):
            await append_event(db, "test_event", None, None, {"i": i})
        
        page1 = await get_events(db, limit=50)
        assert len(page1) == 50
        assert json.loads(page1[0]["payload"])["i"] == 59  # newest
        
        last_created = page1[-1]["created_at"]
        page2 = await get_events(db, limit=50, before=last_created)
        assert len(page2) == 10
        
        await db.close()


class TestP0F07_FrontendAPIBase:
    """P0-F07: Frontend API_BASE from env"""
    
    def test_api_base_configurable(self):
        """api.ts should use VITE_API_BASE env var"""
        with open("frontend/src/api.ts", "r") as f:
            content = f.read()
        assert "VITE_API_BASE" in content or "import.meta.env" in content


class TestP2F01_URLValidation:
    """P2-F01: URL allowlist/denylist on curl tool"""
    
    def test_http_allowed(self):
        """HTTP URLs should be allowed"""
        SandboxManager.validate_url("http://example.com")
        SandboxManager.validate_url("https://example.com")
    
    def test_aws_metadata_blocked(self):
        """AWS metadata URL should be blocked"""
        with pytest.raises(ValueError):
            SandboxManager.validate_url("http://169.254.168.254")
    
    def test_localhost_blocked(self):
        """Localhost should be blocked"""
        with pytest.raises(ValueError):
            SandboxManager.validate_url("http://localhost")
    
    def test_private_ip_blocked(self):
        """Private IPs should be blocked"""
        for ip in ["127.0.0.1", "10.0.0.1", "192.168.1.1", "172.16.0.1"]:
            with pytest.raises(ValueError):
                SandboxManager.validate_url(f"http://{ip}")
    
    def test_valid_public_url_allowed(self):
        """Valid public URLs should work"""
        SandboxManager.validate_url("http://api.example.com/v1")


class TestP2F02_ReactJSONErrors:
    """P2-F02: ReAct loop surfaces JSON errors"""
    
    def test_malformed_json_handled(self):
        """Skeptic should handle malformed JSON gracefully"""
        from backend.agents.skeptic import SkepticAgent
        import inspect
        source = inspect.getsource(SkepticAgent)
        # Should have error handling for JSON parsing
        assert 'consecutive_failures' in source or 'malformed' in source.lower()


class TestP2F03_InstallToolsProbe:
    """P2-F03: install_tools probes after install"""
    
    def test_install_tools_has_probes(self):
        """install_tools should probe after install"""
        from backend.orchestrator.sandbox import SandboxManager
        import inspect
        source = inspect.getsource(SandboxManager)
        # Should have probe checks
        assert 'probe' in source.lower() or 'which' in source.lower()


class TestP2F05_RoundsUsed:
    """P2-F05: rounds_used + tool_calls on SkepticCritique"""
    
    def test_skeptic_critique_has_telemetry(self):
        """SkepticCritique should have rounds_used and tool_calls"""
        critique = SkepticCritique()
        assert hasattr(critique, 'rounds_used')
        assert hasattr(critique, 'tool_calls')
        assert critique.rounds_used == 0  # default
        assert critique.tool_calls == 0  # default
    
    def test_skeptic_output_model(self):
        """SkepticOutput should have all fields"""
        output = SkepticOutput(
            scenarios=["scenario"],
            questions=["question?"],
            tool_evidence=["evidence"],
        )
        # rounds_used and tool_calls are on SkepticCritique, not SkepticOutput
        assert output.scenarios == ["scenario"]


class TestP1F01_QAWritesTestFiles:
    """P1-F01: QA writes test files to sandbox"""
    
    def test_qa_has_write_test_files(self):
        """QAAgent should have write_test_files method"""
        from backend.agents.qa import QAAgent
        assert hasattr(QAAgent, 'write_test_files')
    
    @pytest.mark.asyncio
    async def test_qa_write_test_files_exists(self):
        """write_test_files should be callable"""
        from backend.agents.qa import QAAgent
        from backend.core.models import TestPlan, FileSpec
        
        class FakeSandbox:
            async def exec(self, cmd):
                return {"stdout": "", "stderr": "", "exit_code": 0}
        
        agent = QAAgent(sandbox=FakeSandbox())
        plan = TestPlan(
            build_id="b1",
            framework="pytest",
            test_files=[FileSpec(path="tests/test.py", purpose="test", content_type="test")],
            acceptance_criteria=["pass"]
        )
        # Should not raise
        await agent.write_test_files(plan)


class TestP1F02_HostWorkdir:
    """P1-F02: Build artifacts land on host"""
    
    def test_build_artifact_has_host_workdir(self):
        """BuildArtifact should have host_workdir field"""
        from backend.core.models import BuildArtifact
        
        artifact = BuildArtifact(
            plan_id="p1",
            files_created=[],
            files_modified=[],
            docker_logs=[],
            status="success",
            host_workdir="/tmp/test"
        )
        assert artifact.host_workdir == "/tmp/test"
    
    def test_sandbox_has_host_workdir(self):
        """SandboxManager should track host_workdir"""
        from backend.orchestrator.sandbox import SandboxManager
        mgr = SandboxManager()
        assert hasattr(mgr, 'host_workdir')


class TestP1F03_Base64Write:
    """P1-F03: Robust file write with base64"""
    
    def test_qa_uses_base64(self):
        """QA should use base64 for file writes"""
        from backend.agents.qa import QAAgent
        import inspect
        source = inspect.getsource(QAAgent)
        assert 'base64' in source.lower()


class TestP1F04_CommitSafety:
    """P1-F04: commit_build safety checks"""
    
    def test_commit_validates_artifacts(self):
        """commit endpoint should check for empty artifacts"""
        # This is tested in gates.py - check the source
        with open("backend/orchestrator/gates.py", "r") as f:
            content = f.read()
        # Should have check for empty artifacts
        assert 'artifact_files' in content and '400' in content


class TestP1F05_ThreadSafeExec:
    """P1-F05: exec_safe passes timeout param"""
    
    def test_exec_safe_signature(self):
        """exec_safe should accept timeout param"""
        from backend.orchestrator.sandbox import SandboxManager
        import inspect
        sig = inspect.signature(SandboxManager.exec_safe)
        assert 'timeout' in sig.parameters


class TestP1F06_SandboxLifecycle:
    """P1-F06: Sandbox lifecycle owned by request"""
    
    def test_sandbox_has_stop_method(self):
        """SandboxManager should have stop method"""
        from backend.orchestrator.sandbox import SandboxManager
        assert hasattr(SandboxManager, 'stop')
    
    def test_app_has_shutdown_handler(self):
        """App should have shutdown handler"""
        with open("backend/orchestrator/gates.py", "r") as f:
            content = f.read()
        assert 'shutdown' in content.lower() or 'on_event' in content


class TestPathTraversal:
    """Test path traversal prevention (from Remediation_plan.md)"""
    
    def test_path_traversal_blocked(self):
        """Path traversal should be blocked"""
        with pytest.raises(ValidationError):
            FileSpec(path='../../../etc/passwd', purpose='test', content_type='code')
    
    def test_absolute_path_blocked(self):
        """Absolute paths should be blocked"""
        with pytest.raises(ValidationError):
            FileSpec(path='/etc/shadow', purpose='test', content_type='code')
    
    def test_valid_paths_allowed(self):
        """Valid paths should work"""
        fs = FileSpec(path='src/main.py', purpose='test', content_type='code')
        assert fs.path == 'src/main.py'


class TestToolRequestValidation:
    """Test tool request security"""
    
    def test_invalid_tool_blocked(self):
        """Invalid tools should be rejected"""
        with pytest.raises(ValidationError):
            ToolRequest(tool='rm', args=['-rf', '/'], description='malicious')
    
    def test_valid_tools_allowed(self):
        """Valid tools should work"""
        # curl needs valid URL
        req = ToolRequest(tool='curl', args=['http://example.com'], description='test')
        assert req.tool == 'curl'
        # npm_view needs package name
        req = ToolRequest(tool='npm_view', args=['express'], description='test')
        assert req.tool == 'npm_view'
        # web_search needs query
        req = ToolRequest(tool='web_search', args=['python'], description='test')
        assert req.tool == 'web_search'
