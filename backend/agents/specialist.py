from backend.core.models import Understanding


class OllamaClient:
    def __init__(self, model: str = "gemma4:latest", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

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

    async def generate_understanding(self, goal: str) -> Understanding:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Goal: {goal}"},
        ]
        response = await self.ollama.chat(messages, format="json", temperature=0.0)
        raw = response["message"]["content"]
        return Understanding.model_validate_json(raw)

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

        sets = []
        for _ in range(3):
            s = await self._single_understanding(goal, temperature=0.7)
            sets.append(s)

        first_set = sets[0]
        fragile = any(s != first_set for s in sets[1:])
        return result, fragile
