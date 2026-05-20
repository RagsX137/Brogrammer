from backend.core.models import Understanding
from backend.core import config
from backend.agents._retry import with_retries


class OllamaClient:
    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model = model or config.get("OLLAMA_MODEL", "gemma4:latest")
        self.base_url = base_url or config.get("OLLAMA_BASE_URL", "http://localhost:11434")

    async def chat(self, messages: list[dict], format: str = "", temperature: float = 0.0):
        import ollama
        client = ollama.AsyncClient(host=self.base_url)
        kwargs = {"model": self.model, "messages": messages, "options": {"temperature": temperature}}
        if format:
            kwargs["format"] = format
        response = await client.chat(**kwargs)
        return response


class SpecialistAgent:
    def __init__(self, ollama_client: OllamaClient | None = None):
        self.ollama = ollama_client or OllamaClient()
        self.system_prompt = (
            "You are the SpecialistAgent. Given a user's goal, produce a structured Understanding document. "
            "Return ONLY valid JSON — no markdown, no explanation. "
            'Format: {"goal": "...", "assumptions": [{"statement": "...", "status": "open"}], '
            '"unknowns": [{"question": "..."}], '
            '"mandatory_categories": {"accessibility": [...], "performance": [...], '
            '"security": [...], "state_management": [...], "persistence": [...]}}'
        )

    @with_retries(retries=3)
    async def generate_understanding(self, goal: str) -> Understanding:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Goal: {goal}"},
        ]
        response = await self.ollama.chat(messages, format="json", temperature=0.0)
        raw = response["message"]["content"]
        return Understanding.model_validate_json(raw)

    @with_retries(retries=3)
    async def _single_understanding(self, goal: str, temperature: float) -> set[str]:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Goal: {goal}"},
        ]
        response = await self.ollama.chat(messages, format="json", temperature=temperature)
        raw = response["message"]["content"]
        u = Understanding.model_validate_json(raw)
        return {a.statement for a in u.assumptions}

    async def generate_with_fragility_check(self, goal: str) -> tuple[Understanding, bool]:
        result = await self.generate_understanding(goal)

        try:
            resample = await self._single_understanding(goal, temperature=0.7)
            fragile = resample != {a.statement for a in result.assumptions}
        except RuntimeError:
            fragile = True

        return result, fragile
