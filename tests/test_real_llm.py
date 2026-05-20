"""
Real-LLM smoke tests. Run with: RUN_REAL_LLM=1 pytest -m real_llm -q

These tests hit a real Ollama instance and real Docker sandbox.
Skipped by default. Marked 'slow' because each takes 60-120s.
"""
import os
import pytest
from httpx import AsyncClient, ASGITransport

pytestmark = [
    pytest.mark.real_llm,
    pytest.mark.slow,
    pytest.mark.skipif(
        not os.environ.get("RUN_REAL_LLM"),
        reason="Set RUN_REAL_LLM=1 to run real-LLM integration tests",
    ),
]

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:latest")


@pytest.fixture
def app():
    from backend.orchestrator.gates import create_app
    return create_app(db_path=":memory:", rate_limit=False)


@pytest.mark.asyncio
async def test_phase0_run_loop_end_to_end(app):
    """Phase 0: /api/run-loop returns understanding + critique + confidence."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/run-loop", json={"goal": "word count CLI"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:500]}"
    data = resp.json()
    assert "understanding" in data
    assert "critique" in data
    assert "confidence" in data
    assert data["confidence"]["score"] >= 0


@pytest.mark.asyncio
async def test_phase1_build_test_loop(app):
    """Phase 1: /api/plan -> /api/build -> /api/test returns >=1 test item."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rl = await client.post("/api/run-loop", json={"goal": "word count CLI"})
        assert rl.status_code == 200, f"run-loop: {rl.status_code}"
        u_id = rl.json()["understanding"]["id"]

        plan_resp = await client.post("/api/plan", json={"understanding_id": u_id})
        assert plan_resp.status_code == 200, f"plan: {plan_resp.status_code}"
        plan_id = plan_resp.json()["plan_id"]

        build_resp = await client.post("/api/build", json={"plan_id": plan_id})
        assert build_resp.status_code == 200, f"build: {build_resp.status_code}"
        build_id = build_resp.json()["build"]["build_id"]

        test_resp = await client.post("/api/test", json={"build_id": build_id})
        assert test_resp.status_code == 200, f"test: {test_resp.status_code}"
        report = test_resp.json()["test_report"]
        assert report["passed"] > 0 or report["failed"] > 0, (
            f"Expected non-zero test count, got passed={report['passed']} failed={report['failed']}"
        )


@pytest.mark.asyncio
async def test_phase2_skeptic_tool_evidence(app):
    """Phase 2: Skeptic ReAct loop with sandbox produces tool_evidence."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/run-loop", json={"goal": "word count CLI"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    critique = resp.json()["critique"]
    assert critique.get("tool_evidence") is not None, "Expected tool_evidence in critique"
