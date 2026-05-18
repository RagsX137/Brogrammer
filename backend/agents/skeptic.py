from backend.core.models import Understanding, SkepticCritique
from backend.agents.specialist import OllamaClient


class SkepticAgent:
    def __init__(self, ollama_client: OllamaClient | None = None):
        self.ollama = ollama_client or OllamaClient()
        self.system_prompt = (
            "You are the SkepticAgent. Given an Understanding document, produce a critique. "
            "Return ONLY valid JSON — no markdown, no explanation. "
            'Format: {"scenarios": ["plausible failure scenario 1", "scenario 2"], '
            '"questions": ["clarifying question for the human?"], '
            '"tool_evidence": ["evidence gathered from tools"]}'
        )

    async def generate_critique(self, understanding: Understanding) -> SkepticCritique:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Understanding: {understanding.model_dump_json(indent=2)}"},
        ]
        response = await self.ollama.chat(messages, format="json", temperature=0.3)
        raw = response["message"]["content"]
        data = SkepticCritique.model_validate_json(raw)
        data.understanding_id = understanding.id
        return data
