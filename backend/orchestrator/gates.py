import json
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.orchestrator.database import get_db, init_db
from backend.orchestrator.audit import append_event, get_events, append_tool_call, get_tool_calls
from backend.core.logging import setup_logging
from backend.agents.specialist import SpecialistAgent
from backend.agents.skeptic import SkepticAgent
from backend.agents.planner import PlannerAgent
from backend.agents.builder import BuilderAgent
from backend.agents.qa import QAAgent
from backend.core.confidence import compute_confidence
from backend.core.models import Understanding, Assumption


class RunLoopRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=10_000)

    @field_validator("goal")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Goal cannot be empty after whitespace stripping")
        return stripped


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
    message: str = Field(min_length=1, max_length=500)

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Commit message cannot be empty after whitespace stripping")
        return stripped


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
               qa: QAAgent | None = None,
               rate_limit: bool = True) -> FastAPI:
    import asyncio
    import os as _os
    from backend.orchestrator.sandbox import SandboxManager
    shared_sandbox = SandboxManager()
    _specialist = specialist or SpecialistAgent()
    _skeptic = skeptic or SkepticAgent()
    _planner = planner or PlannerAgent()
    _builder = builder or BuilderAgent(sandbox=shared_sandbox)
    _qa = qa or QAAgent(sandbox=shared_sandbox)
    _db = None
    _db_path = db_path
    _cleanup_task = None

    async def get_db_conn():
        nonlocal _db
        if _db is None:
            _db = await get_db(_db_path)
            await init_db(_db)
        return _db

    from starlette.requests import Request
    if rate_limit:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.util import get_remote_address
        from slowapi.errors import RateLimitExceeded
        limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
    else:
        class _NoopLimiter:
            @staticmethod
            def limit(*a, **kw):
                def decorator(f):
                    return f
                return decorator
        limiter = _NoopLimiter()
    app = FastAPI()
    if rate_limit:
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.on_event("shutdown")
    async def shutdown():
        nonlocal _cleanup_task
        if _cleanup_task:
            _cleanup_task.cancel()
        await shared_sandbox.stop()

    @app.on_event("startup")
    async def startup():
        nonlocal _cleanup_task
        interval = int(_os.environ.get("SANDBOX_CLEANUP_INTERVAL", "600"))

        async def _periodic_cleanup():
            while True:
                shared_sandbox.cleanup_orphans()
                await asyncio.sleep(interval)

        _cleanup_task = asyncio.create_task(_periodic_cleanup())

    @app.get("/health")
    async def health_check():
        """Health check endpoint for monitoring and load balancing."""
        return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

    _log = setup_logging()

    @app.post("/api/run-loop")
    @limiter.limit("5/minute")
    async def run_loop(request: Request, req: RunLoopRequest):
        import time as _time
        t0 = _time.monotonic()
        db = await get_db_conn()
        _log.info("event=run_loop ok=true goal=%.80s", req.goal)
        try:
            understanding, fragile = await _specialist.generate_with_fragility_check(req.goal)
        except Exception as e:
            ms = (_time.monotonic() - t0) * 1000
            _log.error("event=run_loop ok=false error=%s ms=%.0f goal=%.80s", type(e).__name__, ms, req.goal)
            raise

        await append_event(
            db, "understanding_generated", understanding.id, None,
            understanding.model_dump(),
        )

        tool_call_ids = []

        async def _on_tool_call(critique_id, round, tool, args, exit_code, stdout, stderr):
            event_id = await append_tool_call(
                db, critique_id or "pending", round, tool, args, exit_code, stdout, stderr,
            )
            tool_call_ids.append(event_id)

        critique = await _skeptic.generate_critique(
            understanding, sandbox=shared_sandbox, on_tool_call=_on_tool_call,
        )

        if tool_call_ids:
            for eid in tool_call_ids:
                await db.execute(
                    "UPDATE tool_call_events SET critique_id=? WHERE id=?",
                    (critique.critique_id, eid),
                )
            await db.commit()

        await append_event(
            db, "critique_created", understanding.id, critique.critique_id,
            {
                "scenarios": critique.scenarios,
                "questions": critique.questions,
                "tool_evidence": critique.tool_evidence,
                "rounds_used": critique.rounds_used,
                "tool_calls": critique.tool_calls,
                "understanding_id": understanding.id,
            },
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
    @limiter.limit("30/minute")
    async def resolve_critique(request: Request, req: ResolveCritiqueRequest):
        db = await get_db_conn()
        _log.info("event=resolve_critique critique_id=%s", req.critique_id)
        await append_event(
            db, "human_resolution", None, req.critique_id,
            {"resolution": req.resolution},
        )
        return {"success": True}

    @app.get("/api/audit/events")
    async def list_events(limit: int = 50, before: str | None = None):
        db = await get_db_conn()
        events = await get_events(db, limit=limit, before=before)
        return {"events": events}

    @app.post("/api/plan")
    @limiter.limit("10/minute")
    async def create_plan(request: Request, req: PlanRequest):
        import time as _time
        t0 = _time.monotonic()
        db = await get_db_conn()
        _log.info("event=create_plan understanding_id=%s", req.understanding_id)
        try:
            understanding = await _get_understanding(db, req.understanding_id)
            plan = await _planner.generate_plan(understanding)
        except Exception as e:
            _log.error("event=create_plan ok=false error=%s ms=%.0f", type(e).__name__, (_time.monotonic() - t0) * 1000)
            raise
        await db.execute(
            "INSERT INTO tech_plans (id, understanding_id, plan_json, created_at) VALUES (?, ?, ?, ?)",
            (plan.plan_id, req.understanding_id, plan.model_dump_json(),
             datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
        await append_event(db, "plan_created", req.understanding_id, None,
                           {"plan_id": plan.plan_id})
        _log.info("event=create_plan ok=true plan_id=%s ms=%.0f", plan.plan_id, (_time.monotonic() - t0) * 1000)
        return {"plan": plan.model_dump(), "plan_id": plan.plan_id}

    @app.post("/api/build")
    @limiter.limit("5/minute")
    async def create_build(request: Request, req: BuildRequest):
        import time as _time
        t0 = _time.monotonic()
        db = await get_db_conn()
        _log.info("event=create_build plan_id=%s", req.plan_id)
        try:
            plan = await _get_plan(db, req.plan_id)
            artifact = await _builder.build(plan)
        except Exception as e:
            _log.error("event=create_build ok=false error=%s ms=%.0f", type(e).__name__, (_time.monotonic() - t0) * 1000)
            raise
        await db.execute(
            "INSERT INTO build_artifacts (id, plan_id, artifact_json, created_at) VALUES (?, ?, ?, ?)",
            (artifact.build_id, req.plan_id, artifact.model_dump_json(),
             datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
        await append_event(db, "build_completed", None, None,
                           {"build_id": artifact.build_id, "status": artifact.status})
        _log.info("event=create_build ok=true build_id=%s status=%s ms=%.0f",
                  artifact.build_id, artifact.status, (_time.monotonic() - t0) * 1000)
        return {"build": artifact.model_dump()}

    @app.post("/api/test")
    @limiter.limit("10/minute")
    async def run_tests(request: Request, req: TestRequest):
        import time as _time
        t0 = _time.monotonic()
        db = await get_db_conn()
        _log.info("event=run_tests build_id=%s", req.build_id)
        try:
            plan = await _get_plan_for_build(db, req.build_id)
            test_plan = await _qa.generate_test_plan(plan)
            await _qa.write_test_files(test_plan)
            report = await _qa.run_tests(req.build_id)
        except Exception as e:
            _log.error("event=run_tests ok=false error=%s ms=%.0f", type(e).__name__, (_time.monotonic() - t0) * 1000)
            raise
        await db.execute(
            "INSERT INTO test_reports (id, build_id, report_json, created_at) VALUES (?, ?, ?, ?)",
            (report.report_id, req.build_id, report.model_dump_json(),
             datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
        await append_event(db, "test_completed", None, None,
                           {"build_id": req.build_id, "passed": report.passed, "failed": report.failed})
        _log.info("event=run_tests ok=true build_id=%s passed=%d failed=%d ms=%.0f",
                  req.build_id, report.passed, report.failed, (_time.monotonic() - t0) * 1000)
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

    @app.get("/api/critique/{critique_id}/tools")
    async def list_tool_calls(critique_id: str):
        db = await get_db_conn()
        calls = await get_tool_calls(db, critique_id)
        return {"tool_calls": calls}

    @app.post("/api/commit")
    @limiter.limit("30/minute")
    async def commit_build(request: Request, req: CommitRequest):
        import subprocess, os, time as _time
        t0 = _time.monotonic()
        db = await get_db_conn()
        _log.info("event=commit build_id=%s", req.build_id)

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
        host_workdir = build_data.get("host_workdir", "")

        if not artifact_files:
            raise HTTPException(status_code=400, detail="No files to commit — build produced no artifacts")

        import shutil

        for f in artifact_files:
            src_path = os.path.join(host_workdir, f) if host_workdir else f
            dest_path = f
            dest_dir = os.path.dirname(dest_path)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)
            if os.path.exists(src_path):
                shutil.copy2(src_path, dest_path)
            add_result = subprocess.run(
                ["git", "add", dest_path],
                capture_output=True, text=True,
            )
            if add_result.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"git add failed for {dest_path}: {add_result.stderr.strip()}",
                )

        result = subprocess.run(
            ["git", "commit", "-m", req.message],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"git commit failed: {result.stderr.strip()}",
            )

        sha_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True,
        )
        sha = sha_result.stdout.strip()

        await append_event(db, "commit_created", None, None,
                           {"build_id": req.build_id, "sha": sha, "files": artifact_files, "message": req.message})
        _log.info("event=commit ok=true build_id=%s sha=%s ms=%.0f",
                  req.build_id, sha, (_time.monotonic() - t0) * 1000)
        return {"commit_sha": sha, "success": True}

    return app
