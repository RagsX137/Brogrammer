import pytest
from backend.core.models import TechPlan, FileSpec, ComponentSpec


class FakeOllamaClient:
    async def chat(self, messages, format="", temperature=0.0):
        return {
            "message": {
                "content": '{"src/main.py": "print(\'hello\')", "src/config.py": "DEBUG=True"}'
            }
        }


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

    async def is_running(self):
        return True


@pytest.mark.asyncio
async def test_builder_creates_files():
    from backend.agents.builder import BuilderAgent

    agent = BuilderAgent(ollama_client=FakeOllamaClient(), sandbox=FakeSandbox())
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

        async def is_running(self):
            return True

    from backend.agents.builder import BuilderAgent

    agent = BuilderAgent(ollama_client=FakeOllamaClient(), sandbox=BrokenSandbox())
    plan = TechPlan(
        understanding_id="u1",
        tech_stack=["Python"],
        file_tree=[FileSpec(path="src/main.py", purpose="Entry", content_type="code")],
        components=[],
        markdown_summary="#",
    )
    artifact = await agent.build(plan)
    assert artifact.status == "failed"
