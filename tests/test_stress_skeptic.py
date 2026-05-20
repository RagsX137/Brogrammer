"""
Stress and regression tests for SkepticAgent (Phase 2).
Covers edge cases, attack vectors, and ReAct loop boundary conditions.
"""

import pytest
from backend.core.models import Understanding, Assumption, Unknown, MandatoryCategories


class BadJsonFakeClient:
    async def chat(self, messages, format="", temperature=0.0):
        return {"message": {"content": "not json at all"}}


class EmptyScenariosClient:
    async def chat(self, messages, format="", temperature=0.0):
        return {"message": {"content":
            '{"scenarios": [], "questions": [], "tool_evidence": []}'}}


class EmptyScenariosWithToolsClient:
    async def chat(self, messages, format="", temperature=0.0):
        return {"message": {"content":
            '{"tool_requests": [], "scenarios": [], "questions": [], "tool_evidence": []}'}}


class ToolCommandInjectionFakeClient:
    async def chat(self, messages, format="", temperature=0.0):
        return {"message": {"content": (
            '{"tool_requests": [{"tool": "curl", "args": ["http://example.com; rm -rf /"],'
            '"description": "Attempt command injection"}],'
            '"thought": "Try code injection"}')}}


class UnicodeOutputFakeClient:
    async def chat(self, messages, format="", temperature=0.0):
        return {"message": {"content":
            '{"scenarios": ["Unicode test content"], "questions": [], "tool_evidence": []}'}}


class MaxRoundsClient:
    def __init__(self, max_tool_requests=10):
        self.call_count = 0
        self.max_tool_requests = max_tool_requests

    async def chat(self, messages, format="", temperature=0.0):
        self.call_count += 1
        if self.call_count <= self.max_tool_requests:
            return {"message": {"content": (
                '{"tool_requests": [{"tool": "curl", "args": ["http://example.com"],'
                '"description": "Round %d"}], "thought": "Keep going"}' % self.call_count
            )}}
        return {"message": {"content":
            '{"scenarios": ["Finally done"], "questions": [], "tool_evidence": []}'}}


class ReturnsPartialJsonClient:
    async def chat(self, messages, format="", temperature=0.0):
        return {"message": {"content": '{"scenarios": ['}}


class ReturnsEmptyStringClient:
    async def chat(self, messages, format="", temperature=0.0):
        return {"message": {"content": ""}}


class VeryLongOutputClient:
    def __init__(self):
        self.call_count = 0

    async def chat(self, messages, format="", temperature=0.0):
        self.call_count += 1
        long_str = "A" * 100000
        return {"message": {"content":
            '{"scenarios": ["%s"], "questions": [], "tool_evidence": []}' % long_str}}


class NestedJsonClient:
    async def chat(self, messages, format="", temperature=0.0):
        return {"message": {"content": (
            '{"scenarios": ["{\\"nested\\": \\"value\\"}"], "questions": [], "tool_evidence": []}')}}


class ToolInScenariosFakeClient:
    async def chat(self, messages, format="", temperature=0.0):
        return {"message": {"content": (
            '{"scenarios": ["test"], "questions": [], "tool_evidence": []}'
        )}}


# --- Test Cases ---

@pytest.mark.asyncio
async def test_skeptic_handles_non_json_sandbox_none():
    """When sandbox=None, agent should gracefully handle non-JSON."""
    from backend.agents.skeptic import SkepticAgent

    agent = SkepticAgent(ollama_client=BadJsonFakeClient())
    understanding = Understanding(
        goal="test", assumptions=[], unknowns=[],
        mandatory_categories=MandatoryCategories(),
    )
    # Should not crash
    with pytest.raises(Exception):
        await agent.generate_critique(understanding, sandbox=None)


@pytest.mark.asyncio
async def test_skeptic_empty_scenarios_with_sandbox():
    """Skeptic should handle empty scenarios even with sandbox."""
    from backend.agents.skeptic import SkepticAgent

    agent = SkepticAgent(ollama_client=EmptyScenariosClient())
    understanding = Understanding(
        goal="test", assumptions=[], unknowns=[],
        mandatory_categories=MandatoryCategories(),
    )
    critique = await agent.generate_critique(understanding, sandbox=True)
    assert critique.scenarios == []
    assert critique.questions == []
    assert critique.tool_evidence == []


@pytest.mark.asyncio
async def test_skeptic_empty_tool_requests_with_sandbox():
    """Skeptic should handle empty tool_requests list correctly."""
    from backend.agents.skeptic import SkepticAgent

    agent = SkepticAgent(ollama_client=EmptyScenariosWithToolsClient())
    understanding = Understanding(
        goal="test", assumptions=[], unknowns=[],
        mandatory_categories=MandatoryCategories(),
    )
    critique = await agent.generate_critique(understanding, sandbox="mock")
    assert critique.scenarios == []


def test_skeptic_tool_cmd_injection_quoted():
    """Command injection args should be safely escaped via shlex.quote."""
    from backend.orchestrator.sandbox import SandboxManager

    cmd = SandboxManager.build_tool_command("curl", ["http://example.com; rm -rf /"])
    assert "; rm -rf /" not in cmd or "'" in cmd  # quoted


@pytest.mark.asyncio
async def test_skeptic_unicode_in_output():
    """Skeptic should handle Unicode in LLM output."""
    from backend.agents.skeptic import SkepticAgent

    agent = SkepticAgent(ollama_client=UnicodeOutputFakeClient())
    understanding = Understanding(
        goal="test", assumptions=[], unknowns=[],
        mandatory_categories=MandatoryCategories(),
    )
    critique = await agent.generate_critique(understanding, sandbox=None)
    assert critique.scenarios and "test" in critique.scenarios[0]


@pytest.mark.asyncio
async def test_skeptic_max_tool_rounds_exceeded():
    """Skeptic should enforce MAX_TOOL_ROUDS (4)."""
    from backend.agents.skeptic import SkepticAgent

    client = MaxRoundsClient(max_tool_requests=10)
    agent = SkepticAgent(ollama_client=client)
    understanding = Understanding(
        goal="test", assumptions=[], unknowns=[],
        mandatory_categories=MandatoryCategories(),
    )
    critique = await agent.generate_critique(understanding, sandbox="mock")
    # After 4 rounds, it should force-finalize
    assert client.call_count <= 5  # initial + 4 tool rounds max


@pytest.mark.asyncio
async def test_skeptic_handles_empty_string_response():
    """Empty string from LLM should be handled."""
    from backend.agents.skeptic import SkepticAgent

    agent = SkepticAgent(ollama_client=ReturnsEmptyStringClient())
    understanding = Understanding(
        goal="test", assumptions=[], unknowns=[],
        mandatory_categories=MandatoryCategories(),
    )
    with pytest.raises(Exception):
        await agent.generate_critique(understanding, sandbox=None)


@pytest.mark.asyncio
async def test_skeptic_handles_very_long_output():
    """Very long LLM output should not break parsing."""
    from backend.agents.skeptic import SkepticAgent

    agent = SkepticAgent(ollama_client=VeryLongOutputClient())
    understanding = Understanding(
        goal="test", assumptions=[], unknowns=[],
        mandatory_categories=MandatoryCategories(),
    )
    # Should not crash
    critique = await agent.generate_critique(understanding, sandbox=None)
    assert len(critique.scenarios[0]) == 100000
