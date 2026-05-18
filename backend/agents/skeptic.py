from backend.core.models import Understanding, SkepticCritique, ToolRequest, ToolResult, SkepticOutput
from backend.agents.specialist import OllamaClient


TOOL_DEFINITIONS = """
You have access to the following tools to investigate your doubts before reporting them.
Use them to gather real evidence before finalizing your critique.

TOOLS:
  curl <url>       — Make HTTP requests to check APIs, services, documentation
  npm_view <pkg>   — Check npm package metadata (version, size, dependencies)
  web_search <q>   — Search the web for information

When you need to investigate, output:
{"tool_requests": [{"tool": "<tool_name>", "args": ["arg1"], "description": "why"}],
 "thought": "your reasoning"}

When you have enough evidence, output the final critique:
{"scenarios": [...], "questions": [...], "tool_evidence": [...], "thought": ""}

You can use up to 4 rounds of tool investigation.
"""


class SkepticAgent:
    MAX_TOOL_ROUNDS = 4

    def __init__(self, ollama_client: OllamaClient | None = None):
        self.ollama = ollama_client or OllamaClient()
        self.system_prompt = (
            "You are the SkepticAgent. Given an Understanding document, produce a critique. "
            "Return ONLY valid JSON — no markdown, no explanation. "
            'Format: {"scenarios": ["plausible failure scenario 1", "scenario 2"], '
            '"questions": ["clarifying question for the human?"], '
            '"tool_evidence": ["evidence gathered from tools"]}'
        )

    async def generate_critique(
        self, understanding: Understanding, sandbox=None
    ) -> SkepticCritique:
        if not sandbox:
            response = await self.ollama.chat(
                self._build_initial_messages(understanding), format="json", temperature=0.3,
            )
            raw = response["message"]["content"]
            data = SkepticCritique.model_validate_json(raw)
            data.understanding_id = understanding.id
            return data

        messages = self._build_initial_messages(understanding, with_tools=True)

        for round_num in range(1, self.MAX_TOOL_ROUNDS + 1):
            response = await self.ollama.chat(messages, format="json", temperature=0.3)
            raw = response["message"]["content"]
            try:
                output = SkepticOutput.model_validate_json(raw)
            except Exception:
                if round_num == self.MAX_TOOL_ROUNDS:
                    output = SkepticOutput()
                else:
                    continue

            if output.tool_requests:
                for req in output.tool_requests:
                    result = await self._execute_tool(req, sandbox)
                    messages.append({
                        "role": "user",
                        "content": f"Tool '{req.tool} {req.args}' result:\n{result.model_dump_json(indent=2)}",
                    })
                continue

            return SkepticCritique(
                understanding_id=understanding.id,
                scenarios=output.scenarios,
                questions=output.questions,
                tool_evidence=output.tool_evidence,
            )

        return SkepticCritique(
            understanding_id=understanding.id,
            scenarios=[],
            questions=["Skeptic loop exhausted without finalizing"],
            tool_evidence=["Max rounds reached"],
        )

    def _build_initial_messages(self, understanding: Understanding, with_tools: bool = False) -> list[dict]:
        content = self.system_prompt
        if with_tools:
            content += "\n\n" + TOOL_DEFINITIONS
        return [
            {"role": "system", "content": content},
            {"role": "user", "content": f"Understanding: {understanding.model_dump_json(indent=2)}"},
        ]

    @staticmethod
    def _build_command(req: ToolRequest) -> str:
        from backend.orchestrator.sandbox import SandboxManager
        return SandboxManager.build_tool_command(req.tool, req.args)

    async def _execute_tool(self, req: ToolRequest, sandbox) -> ToolResult:
        result = ToolResult(tool=req.tool, args=req.args)
        if sandbox is True:
            return result
        try:
            cmd = self._build_command(req)
            if hasattr(sandbox, 'install_tools'):
                await sandbox.install_tools()
            exec_result = await sandbox.exec_safe(cmd)
            result.stdout = exec_result.get("stdout", "")
            result.stderr = exec_result.get("stderr", "")
            result.exit_code = exec_result.get("exit_code", -1)
        except Exception as e:
            result.stderr = str(e)
            result.exit_code = -1
        return result
