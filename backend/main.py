import uvicorn
from backend.core import config
from backend.orchestrator.gates import create_app
from backend.orchestrator.sandbox import SandboxManager

app = create_app()

@app.on_event("startup")
async def cleanup_stale_containers():
    SandboxManager.cleanup_orphans()

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=config.get("BROGRAMMER_HOST", "0.0.0.0"),
        port=config.get_int("BROGRAMMER_PORT", 8000),
        reload=True,
    )
