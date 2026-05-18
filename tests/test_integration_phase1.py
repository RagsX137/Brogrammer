import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock
from backend.core.models import (
    Understanding, MandatoryCategories, Assumption, Unknown, SkepticCritique,
    TechPlan, FileSpec, ComponentSpec, BuildArtifact,
    TestReport, TestResult, TestPlan,
)


class MockSpecialist:
    async def generate_understanding(self, goal: str) -> Understanding:
        return Understanding(
            goal=goal,
            assumptions=[Assumption(statement="Users will engage daily")],
            unknowns=[Unknown(question="What platform?")],
            mandatory_categories=MandatoryCategories(
                accessibility=["screen reader"],
                performance=["fast"],
                security=["auth"],
                state_management=["redux"],
                persistence=["sqlite"],
            ),
        )

    async def generate_with_fragility_check(self, goal: str) -> tuple[Understanding, bool]:
        u = await self.generate_understanding(goal)
        return u, False


class MockSkeptic:
    async def generate_critique(self, understanding: Understanding, sandbox=None) -> SkepticCritique:
        return SkepticCritique(
            understanding_id=understanding.id,
            scenarios=["Could be too complex for MVP"],
            questions=["Should we scope down?"],
            tool_evidence=[],
        )


async def mock_generate_plan(understanding):
    return TechPlan(
        understanding_id=understanding.id,
        tech_stack=["Python"],
        file_tree=[FileSpec(path="main.py", purpose="Entry", content_type="code")],
        components=[ComponentSpec(name="App", responsibility="Run")],
        markdown_summary="# test",
    )


async def mock_build(plan):
    return BuildArtifact(
        plan_id=plan.plan_id,
        files_created=["main.py"],
        files_modified=[],
        docker_logs=["build ok"],
        status="success",
    )


async def mock_generate_test_plan(plan):
    return TestPlan(
        build_id="",
        framework="pytest",
        test_files=[],
        acceptance_criteria=["pass"],
    )


async def mock_run_tests(build_id, test_path="tests"):
    return TestReport(
        build_id=build_id,
        passed=2,
        failed=0,
        skipped=0,
        details=[TestResult(test_name="test_a", status="passed")],
    )


@pytest.fixture
def app():
    from backend.agents.planner import PlannerAgent
    from backend.agents.builder import BuilderAgent
    from backend.agents.qa import QAAgent
    from backend.orchestrator.gates import create_app

    mock_planner = AsyncMock(spec=PlannerAgent)
    mock_planner.generate_plan.side_effect = mock_generate_plan

    mock_builder = AsyncMock(spec=BuilderAgent)
    mock_builder.build.side_effect = mock_build

    mock_qa = AsyncMock(spec=QAAgent)
    mock_qa.generate_test_plan.side_effect = mock_generate_test_plan
    mock_qa.run_tests.side_effect = mock_run_tests

    return create_app(
        db_path=":memory:",
        specialist=MockSpecialist(),
        skeptic=MockSkeptic(),
        planner=mock_planner,
        builder=mock_builder,
        qa=mock_qa,
    )


@pytest.mark.asyncio
async def test_plan_endpoint(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rl_resp = await client.post("/api/run-loop", json={"goal": "Build a habit tracker"})
        assert rl_resp.status_code == 200
        u_id = rl_resp.json()["understanding"]["id"]

        resp = await client.post("/api/plan", json={"understanding_id": u_id})
    assert resp.status_code == 200
    data = resp.json()
    assert "plan" in data
    assert "plan_id" in data


@pytest.mark.asyncio
async def test_build_endpoint(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rl_resp = await client.post("/api/run-loop", json={"goal": "Build a habit tracker"})
        u_id = rl_resp.json()["understanding"]["id"]

        plan_resp = await client.post("/api/plan", json={"understanding_id": u_id})
        plan_id = plan_resp.json()["plan_id"]

        resp = await client.post("/api/build", json={"plan_id": plan_id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["build"]["status"] == "success"


@pytest.mark.asyncio
async def test_test_endpoint(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rl_resp = await client.post("/api/run-loop", json={"goal": "Build a habit tracker"})
        u_id = rl_resp.json()["understanding"]["id"]

        plan_resp = await client.post("/api/plan", json={"understanding_id": u_id})
        plan_id = plan_resp.json()["plan_id"]

        build_resp = await client.post("/api/build", json={"plan_id": plan_id})
        build_id = build_resp.json()["build"]["build_id"]

        resp = await client.post("/api/test", json={"build_id": build_id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["test_report"]["passed"] == 2


@pytest.mark.asyncio
async def test_commit_endpoint(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rl_resp = await client.post("/api/run-loop", json={"goal": "Build a habit tracker"})
        u_id = rl_resp.json()["understanding"]["id"]

        plan_resp = await client.post("/api/plan", json={"understanding_id": u_id})
        plan_id = plan_resp.json()["plan_id"]

        build_resp = await client.post("/api/build", json={"plan_id": plan_id})
        build_id = build_resp.json()["build"]["build_id"]

        resp = await client.post("/api/commit", json={"build_id": build_id, "message": "feat: initial build"})
    assert resp.status_code == 200
    data = resp.json()
    assert "commit_sha" in data
