import subprocess
from .app import BrogrammerApp
from backend.agents.specialist import SpecialistAgent
from backend.agents.skeptic import SkepticAgent
from backend.agents.planner import PlannerAgent
from backend.agents.builder import BuilderAgent
from backend.agents.qa import QAAgent
from backend.orchestrator.sandbox import SandboxManager
from backend.orchestrator.database import get_db, init_db


async def run():
    specialist = SpecialistAgent()
    skeptic = SkepticAgent()
    planner = PlannerAgent()
    qa = QAAgent()
    sandbox = SandboxManager()
    db = await get_db()
    await init_db(db)
    builder = BuilderAgent(sandbox=sandbox)
    app = BrogrammerApp(
        specialist=specialist,
        skeptic=skeptic,
        planner=planner,
        qa=qa,
        builder=builder,
        sandbox=sandbox,
        db=db,
    )
    await app.run_async()


def do_git_commit(message: str) -> str:
    subprocess.run(["git", "add", "-A"], capture_output=True)
    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def main():
    import asyncio
    asyncio.run(run())
