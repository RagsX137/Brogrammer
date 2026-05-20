"""
Stress tests for API endpoints. Tests concurrency, large payloads,
invalid inputs, and race conditions.
"""
import asyncio
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
                accessibility=["screen reader"], performance=["fast"],
                security=["auth"], state_management=["redux"], persistence=["sqlite"],
            ),
        )

    async def generate_with_fragility_check(self, goal: str) -> tuple[Understanding, bool]:
        u = await self.generate_understanding(goal)
        return u, False


class MockSkeptic:
    async def generate_critique(self, understanding: Understanding, sandbox=None, **kwargs) -> SkepticCritique:
        return SkepticCritique(
            understanding_id=understanding.id,
            scenarios=[], questions=[], tool_evidence=[],
        )


@pytest.fixture
def app():
    from backend.orchestrator.gates import create_app
    return create_app(db_path=":memory:", specialist=MockSpecialist(), skeptic=MockSkeptic(), rate_limit=False)


@pytest.mark.asyncio
async def test_concurrent_run_loop_requests(app):
    """Multiple concurrent requests should not crash."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tasks = [
            client.post("/api/run-loop", json={"goal": f"Test {i}"})
            for i in range(10)
        ]
        responses = await asyncio.gather(*tasks)
        for r in responses:
            assert r.status_code == 200


@pytest.mark.asyncio
async def test_run_loop_with_very_long_goal(app):
    """Very long goal should be rejected (DoS protection)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/run-loop", json={"goal": "A" * 100000})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_run_loop_with_unicode_goal(app):
    """Unicode + emoji in goal should work."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/run-loop", json={"goal": "Hello \u263a \u2605"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_resolve_critique_with_invalid_id(app):
    """Resolving non-existent critique should be handled."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/resolve-critique", json={
            "critique_id": "non-existent-id-12345",
            "resolution": "Some resolution",
        })
    assert resp.status_code == 200  # Currently silently accepted
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_audit_events_with_zero_limit(app):
    """Limit of 0 should return empty."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/audit/events?limit=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["events"] == []


@pytest.mark.asyncio
async def test_audit_events_with_negative_limit(app):
    """Negative limit behavior is undefined."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/audit/events?limit=-1")
    # Negative limit in SQLite returns nothing
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_endpoint(app):
    """Health check should always return healthy."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_ready_endpoint(app):
    """Ready check should verify database."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"
