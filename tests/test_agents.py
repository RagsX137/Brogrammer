import pytest
from backend.core.models import Understanding, MandatoryCategories, Assumption, Unknown


class FakeOllamaClient:
    def __init__(self):
        pass

    async def chat(self, messages: list[dict], format: str = "", temperature: float = 0.0):
        return {
            "message": {
                "content": (
                    '{"goal": "Build a habit tracker", '
                    '"assumptions": [{"statement": "Users want streaks", "status": "open"}], '
                    '"unknowns": [{"question": "What platform?"}], '
                    '"mandatory_categories": {"accessibility": [], "performance": ["fast"], '
                    '"security": [], "state_management": [], "persistence": []}}'
                )
            }
        }


@pytest.mark.asyncio
async def test_specialist_generates_understanding():
    from backend.agents.specialist import SpecialistAgent

    agent = SpecialistAgent(ollama_client=FakeOllamaClient())
    result = await agent.generate_understanding("Build a habit tracker")
    assert isinstance(result, Understanding)
    assert result.goal == "Build a habit tracker"
    assert len(result.assumptions) == 1
    assert result.assumptions[0].statement == "Users want streaks"
    assert len(result.unknowns) == 1
    assert result.unknowns[0].question == "What platform?"


class FragileFakeClient:
    def __init__(self):
        self.call_count = 0

    async def chat(self, messages: list[dict], format: str = "", temperature: float = 0.0):
        self.call_count += 1
        goals = {
            1: "Build a habit tracker",
            2: "Create a workout app",
            3: "Make a todo list",
        }
        return {
            "message": {
                "content": (
                    '{"goal": "' + goals.get(self.call_count, "Unknown") + '", '
                    '"assumptions": [{"statement": "assumption ' + str(self.call_count) + '", "status": "open"}], '
                    '"unknowns": [], '
                    '"mandatory_categories": {"accessibility": [], "performance": [], '
                    '"security": [], "state_management": [], "persistence": []}}'
                )
            }
        }


@pytest.mark.asyncio
async def test_specialist_fragility_detection():
    from backend.agents.specialist import SpecialistAgent

    agent = SpecialistAgent(ollama_client=FragileFakeClient())
    result, fragile = await agent.generate_with_fragility_check("Build a habit tracker")
    assert fragile is True


class StableFakeClient:
    def __init__(self):
        self.call_count = 0

    async def chat(self, messages: list[dict], format: str = "", temperature: float = 0.0):
        return {
            "message": {
                "content": (
                    '{"goal": "Build a habit tracker", '
                    '"assumptions": [{"statement": "Users want streaks", "status": "open"}], '
                    '"unknowns": [], '
                    '"mandatory_categories": {"accessibility": [], "performance": [], '
                    '"security": [], "state_management": [], "persistence": []}}'
                )
            }
        }


@pytest.mark.asyncio
async def test_specialist_no_fragility():
    from backend.agents.specialist import SpecialistAgent

    agent = SpecialistAgent(ollama_client=StableFakeClient())
    result, fragile = await agent.generate_with_fragility_check("Build a habit tracker")
    assert fragile is False


class SkepticFakeClient:
    async def chat(self, messages: list[dict], format: str = "", temperature: float = 0.0):
        return {
            "message": {
                "content": (
                    '{"scenarios": ["Fireworks library adds 6MB bloat"], '
                    '"questions": ["Should we use CSS animations instead?"], '
                    '"tool_evidence": ["npm view react-native-fireworks unpackedSize -> 6MB"]}'
                )
            }
        }


@pytest.mark.asyncio
async def test_skeptic_generates_critique():
    from backend.agents.skeptic import SkepticAgent

    agent = SkepticAgent(ollama_client=SkepticFakeClient())
    understanding = Understanding(
        goal="Build a habit tracker",
        assumptions=[Assumption(statement="Users want fireworks")],
        unknowns=[Unknown(question="What library?")],
        mandatory_categories=MandatoryCategories(),
    )
    critique = await agent.generate_critique(understanding)
    assert critique.understanding_id == understanding.id
    assert len(critique.scenarios) == 1
    assert "6MB" in critique.scenarios[0]
    assert len(critique.questions) == 1
    assert len(critique.tool_evidence) == 1


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
    """When sandbox is None, should use single-round path with old prompt (no tool defs)."""
    from backend.agents.skeptic import SkepticAgent
    agent = SkepticAgent(ollama_client=SkepticFakeClient())
    understanding = Understanding(
        goal="Build a habit tracker",
        assumptions=[Assumption(statement="Users want fireworks")],
        unknowns=[Unknown(question="What library?")],
        mandatory_categories=MandatoryCategories(),
    )
    critique = await agent.generate_critique(understanding, sandbox=None)
    assert critique.understanding_id == understanding.id
    assert len(critique.scenarios) == 1
    assert "6MB" in critique.scenarios[0]
    assert len(critique.tool_evidence) == 1


@pytest.mark.asyncio
async def test_skeptic_react_loop_exhausted():
    """After max tool-request rounds, should force-finalize."""
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
