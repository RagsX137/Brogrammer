import pytest
from httpx import AsyncClient, ASGITransport
from backend.core.models import Understanding, MandatoryCategories, Assumption, Unknown, SkepticCritique


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
    async def generate_critique(self, understanding: Understanding) -> SkepticCritique:
        return SkepticCritique(
            understanding_id=understanding.id,
            scenarios=["Could be too complex for MVP"],
            questions=["Should we scope down?"],
            tool_evidence=[],
        )


@pytest.fixture
def app():
    from backend.orchestrator.gates import create_app
    return create_app(
        db_path=":memory:",
        specialist=MockSpecialist(),
        skeptic=MockSkeptic(),
    )


@pytest.mark.asyncio
async def test_run_loop_endpoint(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/run-loop", json={"goal": "Build a habit tracker"})
    assert resp.status_code == 200
    data = resp.json()
    assert "understanding" in data
    assert "critique" in data
    assert "confidence" in data
    assert "critique_resolved" in data
    assert data["critique_resolved"] is False


@pytest.mark.asyncio
async def test_resolve_critique(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_resp = await client.post("/api/run-loop", json={"goal": "Test app"})
        critique_id = run_resp.json()["critique"]["critique_id"]

        resolve_resp = await client.post(
            "/api/resolve-critique",
            json={"critique_id": critique_id, "resolution": "Use CSS animations"},
        )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["success"] is True


@pytest.mark.asyncio
async def test_audit_events_endpoint(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/run-loop", json={"goal": "Test app"})
        resp = await client.get("/api/audit/events?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert len(data["events"]) > 0


@pytest.mark.asyncio
async def test_run_loop_missing_goal(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/run-loop", json={})
    assert resp.status_code == 422
