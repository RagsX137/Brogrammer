import json
from backend.core.models import Understanding, TechPlan
from backend.agents.specialist import OllamaClient


class PlannerAgent:
    def __init__(self, ollama_client: OllamaClient | None = None):
        self.ollama = ollama_client or OllamaClient()
        self.system_prompt = (
            "You are the PlannerAgent. Given an Understanding document, produce a TechPlan. "
            "Return ONLY valid JSON — no markdown, no explanation. "
            'Format: {"understanding_id": "...", '
            '"tech_stack": ["Python", "FastAPI"], '
            '"file_tree": [{"path": "src/main.py", "purpose": "Entry point", "content_type": "code"}], '
            '"components": [{"name": "API", "responsibility": "Handle requests", "depends_on": []}], '
            '"api_routes": [{"method": "GET", "path": "/health", "description": "Health check"}], '
            '"markdown_summary": "# Plan summary in markdown"}'
        )

    async def generate_plan(self, understanding: Understanding) -> TechPlan:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Understanding: {understanding.model_dump_json(indent=2)}"},
        ]

        for attempt in range(3):
            response = await self.ollama.chat(messages, format="json", temperature=0.2)
            raw = response["message"]["content"]
            try:
                data = json.loads(raw)
                data["understanding_id"] = understanding.id
                return TechPlan(**data)
            except (json.JSONDecodeError, Exception):
                if attempt == 2:
                    raise

        raise RuntimeError("Planner failed after 3 retries")
