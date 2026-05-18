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
