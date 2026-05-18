import uvicorn
from backend.orchestrator.gates import create_app
from backend.orchestrator.sandbox import SandboxManager

app = create_app()

@app.on_event("startup")
async def cleanup_stale_containers():
    SandboxManager.cleanup_orphans()

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
