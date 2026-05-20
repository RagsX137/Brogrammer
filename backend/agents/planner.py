from backend.core.models import Understanding, TechPlan
from backend.agents.specialist import OllamaClient
from backend.agents._retry import with_retries


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

    @with_retries(retries=3)
    async def _call_llm(self, messages: list, understanding_id: str) -> TechPlan:
        import json
        response = await self.ollama.chat(messages, format="json", temperature=0.2)
        raw = response["message"]["content"]
        data = json.loads(raw)
        data["understanding_id"] = understanding_id
        return TechPlan.model_validate(data)

    async def generate_plan(self, understanding: Understanding) -> TechPlan:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Understanding: {understanding.model_dump_json(indent=2)}"},
        ]
        return await self._call_llm(messages, understanding.id)
