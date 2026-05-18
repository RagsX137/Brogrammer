from fastapi import FastAPI
from pydantic import BaseModel

from backend.orchestrator.database import get_db, init_db
from backend.orchestrator.audit import append_event, get_events
from backend.agents.specialist import SpecialistAgent
from backend.agents.skeptic import SkepticAgent
from backend.core.confidence import compute_confidence


class RunLoopRequest(BaseModel):
    goal: str


class ResolveCritiqueRequest(BaseModel):
    critique_id: str
    resolution: str


def create_app(db_path: str | None = None, specialist: SpecialistAgent | None = None,
               skeptic: SkepticAgent | None = None) -> FastAPI:
    _specialist = specialist or SpecialistAgent()
    _skeptic = skeptic or SkepticAgent()
    _db = None
    _db_path = db_path

    async def get_db_conn():
        nonlocal _db
        if _db is None:
            _db = await get_db(_db_path)
            await init_db(_db)
        return _db

    app = FastAPI()

    @app.post("/api/run-loop")
    async def run_loop(req: RunLoopRequest):
        db = await get_db_conn()

        understanding, fragile = await _specialist.generate_with_fragility_check(req.goal)

        await append_event(
            db, "understanding_generated", understanding.id, None,
            understanding.model_dump(),
        )

        critique = await _skeptic.generate_critique(understanding)

        await append_event(
            db, "critique_created", understanding.id, critique.critique_id,
            {"scenarios": critique.scenarios, "questions": critique.questions},
        )

        profile = compute_confidence(
            open_unknowns=len([u for u in understanding.unknowns if u.resolution is None]),
            total_unknowns=len(understanding.unknowns),
            validated_count=len([a for a in understanding.assumptions if a.status == "validated"]),
            total_assumptions=len(understanding.assumptions),
            mandatory_categories=understanding.mandatory_categories,
            fragility_flag=fragile,
        )

        return {
            "understanding": understanding.model_dump(),
            "critique": critique.model_dump(),
            "confidence": profile.model_dump(),
            "critique_resolved": False,
        }

    @app.post("/api/resolve-critique")
    async def resolve_critique(req: ResolveCritiqueRequest):
        db = await get_db_conn()
        await append_event(
            db, "human_resolution", None, req.critique_id,
            {"resolution": req.resolution},
        )
        return {"success": True}

    @app.get("/api/audit/events")
    async def list_events(limit: int = 50):
        db = await get_db_conn()
        events = await get_events(db, limit=limit)
        return {"events": events}

    return app
