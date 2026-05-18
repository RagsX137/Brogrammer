import json
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.orchestrator.database import get_db, init_db
from backend.orchestrator.audit import append_event, get_events
from backend.agents.specialist import SpecialistAgent
from backend.agents.skeptic import SkepticAgent
from backend.agents.planner import PlannerAgent
from backend.agents.builder import BuilderAgent
from backend.agents.qa import QAAgent
from backend.core.confidence import compute_confidence
from backend.core.models import Understanding, Assumption


class RunLoopRequest(BaseModel):
    goal: str


class ResolveCritiqueRequest(BaseModel):
    critique_id: str
    resolution: str


class PlanRequest(BaseModel):
    understanding_id: str


class BuildRequest(BaseModel):
    plan_id: str


class TestRequest(BaseModel):
    build_id: str


class CommitRequest(BaseModel):
    build_id: str
    message: str


async def _get_understanding(db, understanding_id: str) -> Understanding:
    cursor = await db.execute(
        "SELECT payload FROM audit_events WHERE event_type='understanding_generated' AND understanding_id=?",
        (understanding_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Understanding not found")
    payload = json.loads(row["payload"])
    return Understanding(**payload)


async def _get_plan(db, plan_id: str):
    from backend.core.models import TechPlan
    cursor = await db.execute(
        "SELECT plan_json FROM tech_plans WHERE id=?",
        (plan_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Plan not found")
    return TechPlan.model_validate_json(row["plan_json"])


async def _get_plan_for_build(db, build_id: str):
    cursor = await db.execute(
        "SELECT plan_id FROM build_artifacts WHERE id=?",
        (build_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Build not found")
    return await _get_plan(db, row["plan_id"])


def create_app(db_path: str | None = None,
               specialist: SpecialistAgent | None = None,
               skeptic: SkepticAgent | None = None,
               planner: PlannerAgent | None = None,
               builder: BuilderAgent | None = None,
               qa: QAAgent | None = None) -> FastAPI:
    from backend.orchestrator.sandbox import SandboxManager
    shared_sandbox = SandboxManager()
    _specialist = specialist or SpecialistAgent()
    _skeptic = skeptic or SkepticAgent()
    _planner = planner or PlannerAgent()
    _builder = builder or BuilderAgent(sandbox=shared_sandbox)
    _qa = qa or QAAgent(sandbox=shared_sandbox)
    _db = None
    _db_path = db_path

    async def get_db_conn():
        nonlocal _db
        if _db is None:
            _db = await get_db(_db_path)
            await init_db(_db)
        return _db

    app = FastAPI()

    @app.get("/health")
    async def health_check():
        """Health check endpoint for monitoring and load balancing."""
        return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

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

    @app.post("/api/plan")
    async def create_plan(req: PlanRequest):
        db = await get_db_conn()
        understanding = await _get_understanding(db, req.understanding_id)
        plan = await _planner.generate_plan(understanding)
        await db.execute(
            "INSERT INTO tech_plans (id, understanding_id, plan_json, created_at) VALUES (?, ?, ?, ?)",
            (plan.plan_id, req.understanding_id, plan.model_dump_json(),
             datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
        await append_event(db, "plan_created", req.understanding_id, None,
                           {"plan_id": plan.plan_id})
        return {"plan": plan.model_dump(), "plan_id": plan.plan_id}

    @app.post("/api/build")
    async def create_build(req: BuildRequest):
        db = await get_db_conn()
        plan = await _get_plan(db, req.plan_id)
        artifact = await _builder.build(plan)
        await db.execute(
            "INSERT INTO build_artifacts (id, plan_id, artifact_json, created_at) VALUES (?, ?, ?, ?)",
            (artifact.build_id, req.plan_id, artifact.model_dump_json(),
             datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
        await append_event(db, "build_completed", None, None,
                           {"build_id": artifact.build_id, "status": artifact.status})
        return {"build": artifact.model_dump()}

    @app.post("/api/test")
    async def run_tests(req: TestRequest):
        db = await get_db_conn()
        plan = await _get_plan_for_build(db, req.build_id)
        test_plan = await _qa.generate_test_plan(plan)
        report = await _qa.run_tests(req.build_id)
        await db.execute(
            "INSERT INTO test_reports (id, build_id, report_json, created_at) VALUES (?, ?, ?, ?)",
            (report.report_id, req.build_id, report.model_dump_json(),
             datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
        await append_event(db, "test_completed", None, None,
                           {"build_id": req.build_id, "passed": report.passed, "failed": report.failed})
        return {"test_plan": test_plan.model_dump(), "test_report": report.model_dump()}

    @app.get("/api/ready")
    async def ready_check():
        """Readiness check with database verification."""
        try:
            db = await get_db_conn()
            await db.execute("SELECT 1")
            return {"status": "ready", "database": "connected", "timestamp": datetime.now(timezone.utc).isoformat()}
        except Exception as e:
            return {"status": "not ready", "database": str(e)}, 503

    @app.post("/api/commit")
    async def commit_build(req: CommitRequest):
        db = await get_db_conn()
        import subprocess, os

        git_dir = os.path.join(os.getcwd(), ".git")
        if not os.path.isdir(git_dir):
            raise HTTPException(status_code=400, detail="Not a git repository")

        cursor = await db.execute(
            "SELECT artifact_json FROM build_artifacts WHERE id=?",
            (req.build_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Build not found")

        build_data = json.loads(row["artifact_json"])
        artifact_files = build_data.get("files_created", []) + build_data.get("files_modified", [])

        for f in artifact_files:
            subprocess.run(["git", "add", f], capture_output=True)

        result = subprocess.run(
            ["git", "commit", "-m", req.message],
            capture_output=True, text=True,
        )
        sha = result.stdout.strip() if result.returncode == 0 else ""
        await append_event(db, "commit_created", None, None,
                           {"build_id": req.build_id, "sha": sha})
        return {"commit_sha": sha, "success": result.returncode == 0}

    return app
