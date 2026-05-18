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
    assert agent.ollama.attempt > 1
