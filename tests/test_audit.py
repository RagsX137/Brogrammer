import json
import pytest
from backend.orchestrator.database import get_db, init_db
from backend.orchestrator.audit import append_event, get_events


@pytest.fixture
async def db():
    db = await get_db(":memory:")
    await init_db(db)
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_append_and_read_events(db):
    await append_event(
        db,
        event_type="critique_created",
        understanding_id="u1",
        critique_id="c1",
        payload={"scenarios": ["failure"]},
    )
    events = await get_events(db, limit=10)
    assert len(events) == 1
    assert events[0]["event_type"] == "critique_created"
    assert events[0]["understanding_id"] == "u1"
    assert events[0]["critique_id"] == "c1"
    data = json.loads(events[0]["payload"])
    assert data["scenarios"] == ["failure"]


@pytest.mark.asyncio
async def test_events_ordered_by_time_desc(db):
    await append_event(db, "understanding_generated", "u1", None, {"a": 1})
    await append_event(db, "critique_created", "u1", "c1", {"b": 2})
    await append_event(db, "human_resolution", "u1", "c1", {"c": 3})
    events = await get_events(db, limit=10)
    assert len(events) == 3
    types = [e["event_type"] for e in events]
    assert types == ["human_resolution", "critique_created", "understanding_generated"]


@pytest.mark.asyncio
async def test_get_events_limit(db):
    for i in range(5):
        await append_event(db, "test_event", None, None, {"i": i})
    events = await get_events(db, limit=2)
    assert len(events) == 2


@pytest.mark.asyncio
async def test_pagination_with_cursor(db):
    for i in range(60):
        await append_event(db, "test_event", None, None, {"i": i})
    page1 = await get_events(db, limit=50)
    assert len(page1) == 50
    assert page1[0]["payload"] == '{"i": 59}'  # newest first
    assert page1[-1]["payload"] == '{"i": 10}'

    last_created = page1[-1]["created_at"]
    page2 = await get_events(db, limit=50, before=last_created)
    assert len(page2) == 10
    assert page2[0]["payload"] == '{"i": 9}'


@pytest.mark.asyncio
async def test_tool_evidence_in_audit(db):
    await append_event(
        db, "critique_created", "u1", "c1",
        {
            "scenarios": ["test"],
            "questions": ["q?"],
            "tool_evidence": ["curl result: 200"],
            "rounds_used": 2,
            "tool_calls": 3,
            "understanding_id": "u1",
        },
    )
    events = await get_events(db, limit=10)
    assert len(events) == 1
    payload = json.loads(events[0]["payload"])
    assert payload["tool_evidence"] == ["curl result: 200"]
    assert payload["rounds_used"] == 2
    assert payload["tool_calls"] == 3
    assert payload["understanding_id"] == "u1"


@pytest.mark.asyncio
async def test_event_id_is_unique(db):
    ids = set()
    for _ in range(20):
        await append_event(db, "test", None, None, {})
    events = await get_events(db, limit=100)
    for e in events:
        ids.add(e["id"])
    assert len(ids) == 20


@pytest.mark.asyncio
async def test_tech_plans_table(db):
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tech_plans'")
    row = await cursor.fetchone()
    assert row is not None, "tech_plans table should exist"


@pytest.mark.asyncio
async def test_build_artifacts_table(db):
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='build_artifacts'")
    row = await cursor.fetchone()
    assert row is not None, "build_artifacts table should exist"


@pytest.mark.asyncio
async def test_test_reports_table(db):
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_reports'")
    row = await cursor.fetchone()
    assert row is not None, "test_reports table should exist"
