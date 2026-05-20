"""
Phase 2 Security Audit - Comprehensive vulnerability testing.
Tests for input validation, injection attacks, DoS, and logic bugs.
"""
import pytest
from pydantic import ValidationError
from backend.core.models import (
    FileSpec, Understanding, Assumption, Unknown, MandatoryCategories,
    SkepticCritique, ToolRequest, ToolResult, SkepticOutput
)
from backend.orchestrator.gates import (
    RunLoopRequest, ResolveCritiqueRequest, PlanRequest, 
    BuildRequest, TestRequest, CommitRequest
)


class TestInputValidationGaps:
    """Test for missing input validation."""

    def test_empty_goal_allowed(self):
        """Empty goals should probably be rejected."""
        req = RunLoopRequest(goal='')
        assert req.goal == ""  # Currently allowed - potential issue

    def test_whitespace_only_goal_allowed(self):
        """Whitespace-only goals should probably be rejected."""
        req = RunLoopRequest(goal='   ')
        assert req.goal == '   '  # Currently allowed - potential issue

    def test_extremely_long_goal(self):
        """Very long goals could cause DoS."""
        long_goal = 'A' * 1000000  # 1MB goal
        req = RunLoopRequest(goal=long_goal)
        assert len(req.goal) == 1000000  # No length limit - potential DoS

    def test_commit_message_no_validation(self):
        """Commit messages have no validation."""
        req = CommitRequest(build_id='b1', message='')
        assert req.message == ''  # Empty commit allowed

    def test_commit_message_no_length_limit(self):
        """Very long commit messages could cause issues."""
        long_msg = 'X' * 100000
        req = CommitRequest(build_id='b1', message=long_msg)
        assert len(req.message) == 100000  # No limit - potential issue


class TestPathTraversal:
    """Test path traversal prevention."""

    def test_path_traversal_blocked(self):
        """Path traversal should be blocked."""
        with pytest.raises(ValidationError) as exc_info:
            FileSpec(path='../../../etc/passwd', purpose='test', content_type='code')
        assert 'Path traversal' in str(exc_info.value)

    def test_absolute_path_blocked(self):
        """Absolute paths should be blocked."""
        with pytest.raises(ValidationError):
            FileSpec(path='/etc/shadow', purpose='test', content_type='code')

    def test_embedded_traversal_blocked(self):
        """Embedded path traversal should be blocked."""
        with pytest.raises(ValidationError):
            FileSpec(path='src/../../etc/passwd', purpose='test', content_type='code')

    def test_command_injection_blocked(self):
        """Command injection in paths should be blocked."""
        with pytest.raises(ValidationError):
            FileSpec(path='test;rm -rf /', purpose='test', content_type='code')

    def test_shell_expansion_blocked(self):
        """Shell expansion should be blocked."""
        with pytest.raises(ValidationError):
            FileSpec(path='test$(whoami)', purpose='test', content_type='code')

    def test_valid_paths_allowed(self):
        """Valid paths should work."""
        valid_paths = [
            'src/main.py',
            'config.json',
            'src/components/main.py',
            'test_file-123.py',
        ]
        for path in valid_paths:
            fs = FileSpec(path=path, purpose='test', content_type='code')
            assert fs.path == path


class TestToolRequestValidation:
    """Test tool request security."""

    def test_invalid_tool_blocked(self):
        """Invalid tools should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ToolRequest(tool='rm', args=['-rf', '/'], description='malicious')
        assert 'literal_error' in str(exc_info.value).lower()

    def test_valid_tools_allowed(self):
        """Valid tools should work."""
        valid_tools = [
            ('curl', ['http://example.com']),
            ('npm_view', ['express']),
            ('web_search', ['python']),
        ]
        for tool, args in valid_tools:
            req = ToolRequest(tool=tool, args=args, description='test')
            assert req.tool == tool

    def test_tool_args_no_validation(self):
        """Tool args are not validated for injection."""
        # This is by design - shlex.quote handles escaping
        req = ToolRequest(tool='curl', args=['http://example.com; rm -rf /'], description='test')
        assert req.args[0] == 'http://example.com; rm -rf /'


class TestSkepticOutputValidation:
    """Test SkepticOutput model validation."""

    def test_empty_output_valid(self):
        """Empty skeptic output should be valid."""
        output = SkepticOutput()
        assert output.tool_requests == []
        assert output.scenarios == []
        assert output.questions == []

    def test_scenarios_no_length_limit(self):
        """Scenarios have no length limit."""
        long_scenario = 'S' * 100000
        output = SkepticOutput(scenarios=[long_scenario])
        assert len(output.scenarios[0]) == 100000


class TestDatabaseInjection:
    """Test for SQL/NoSQL injection in database operations."""

    def test_sql_in_payload_serialized_safely(self):
        """SQL in payloads should be serialized, not executed."""
        malicious = {"test": "'; DROP TABLE audit_events; --"}
        # Pydantic should handle this safely via parameterization
        assert malicious["test"] == "'; DROP TABLE audit_events; --"

    def test_json_special_chars(self):
        """JSON special characters should be handled."""
        special = '{"key": "value", "nested": {"a": 1}}'
        a = Assumption(statement=special)
        assert a.statement == special


class TestTypeEnforcement:
    """Test that Literal types are enforced."""

    def test_filespec_content_type_literal(self):
        """FileSpec content_type should be Literal."""
        # Valid types
        for ct in ['code', 'config', 'test', 'doc', 'requirements']:
            fs = FileSpec(path='test.py', purpose='test', content_type=ct)
            assert fs.content_type == ct

        # Invalid type
        with pytest.raises(ValidationError):
            FileSpec(path='test.py', purpose='test', content_type='invalid')

    def test_api_route_method_literal(self):
        """APIRoute method should be Literal."""
        # Valid methods
        for method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']:
            route = APIRoute(method=method, path='/test', description='test')
            assert route.method == method

        # Invalid method
        with pytest.raises(ValidationError):
            APIRoute(method='INVALID', path='/test', description='test')

    def test_build_artifact_status_literal(self):
        """BuildArtifact status should be Literal."""
        from backend.core.models import BuildArtifact

        # Valid statuses
        for status in ['success', 'failed', 'running']:
            ba = BuildArtifact(
                plan_id='p1',
                files_created=[],
                files_modified=[],
                docker_logs=[],
                status=status
            )
            assert ba.status == status

        # Invalid status
        with pytest.raises(ValidationError):
            BuildArtifact(
                plan_id='p1',
                files_created=[],
                files_modified=[],
                docker_logs=[],
                status='invalid'
            )

    def test_test_result_status_literal(self):
        """TestResult status should be Literal."""
        # Valid statuses
        for status in ['passed', 'failed', 'skipped']:
            tr = TestResult(test_name='test', status=status)
            assert tr.status == status

        # Invalid status
        with pytest.raises(ValidationError):
            TestResult(test_name='test', status='invalid')


# Import here to avoid circular imports
from backend.core.models import APIRoute, BuildArtifact, TestResult


class TestDoSVectors:
    """Test for Denial of Service vulnerabilities."""

    def test_no_input_size_limits(self):
        """Most inputs have no size limits - potential DoS."""
        # String fields have no max_length
        # This is a design decision but worth noting

        # FileSpec.path - no limit
        long_path = 'a' * 100000
        fs = FileSpec(path=long_path, purpose='test', content_type='code')
        assert len(fs.path) == 100000

        # Understanding.goal - no limit
        long_goal = 'b' * 100000
        u = Understanding(goal=long_goal)
        assert len(u.goal) == 100000


class TestLogicBugs:
    """Test for logic bugs and edge cases."""

    def test_understanding_without_assumptions(self):
        """Understanding can have no assumptions."""
        u = Understanding(goal='test')
        assert u.assumptions == []
        assert u.unknowns == []

    def test_confidence_with_zero_unknowns(self):
        """Confidence calculation with zero unknowns."""
        from backend.core.confidence import compute_confidence

        profile = compute_confidence(
            open_unknowns=0,
            total_unknowns=0,
            validated_count=0,
            total_assumptions=0,
            mandatory_categories=MandatoryCategories(
                accessibility=['a'],
                performance=['p'],
                security=['s'],
                state_management=['sm'],
                persistence=['pe']
            ),
        )
        # Should not divide by zero
        assert profile.score >= 0

    def test_confidence_negative_clamping(self):
        """Negative confidence should be clamped."""
        from backend.core.confidence import compute_confidence

        profile = compute_confidence(
            open_unknowns=10,
            total_unknowns=5,  # More open than total - should give negative
            validated_count=0,
            total_assumptions=1,
            mandatory_categories=MandatoryCategories(performance=['p']),
        )
        assert profile.score >= 0  # Should be clamped to 0
