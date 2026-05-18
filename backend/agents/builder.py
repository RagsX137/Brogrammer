import json
from backend.core.models import TechPlan, BuildArtifact
from backend.agents.specialist import OllamaClient
from backend.orchestrator.sandbox import SandboxManager


class BuilderAgent:
    def __init__(self, ollama_client: OllamaClient | None = None,
                 sandbox: SandboxManager | None = None):
        self.ollama = ollama_client or OllamaClient()
        self.sandbox = sandbox or SandboxManager()
        self.system_prompt = (
            "You are the BuilderAgent. Given a TechPlan, generate the actual file contents. "
            "Return ONLY a JSON object mapping file paths to their content. "
            'Format: {"src/main.py": "print(\'hello\')", "src/config.py": "DEBUG=True"} '
            "No markdown, no explanation."
        )

    async def build(self, plan: TechPlan) -> BuildArtifact:
        if not await self.sandbox.is_running():
            await self.sandbox.start()

        logs = []
        created = []
        modified = []

        container_dir = "/workspace"
        for file_spec in plan.file_tree:
            mkdir_cmd = f"mkdir -p {container_dir}/{file_spec.path.rsplit('/', 1)[0] if '/' in file_spec.path else '.'}"
            result = await self._exec_with_retry(mkdir_cmd)
            logs.append(f"$ {mkdir_cmd}")
            logs.append(result["stdout"])

            content = await self._generate_file_content(plan, file_spec)
            write_cmd = f"cat > {container_dir}/{file_spec.path} << 'BROGRAMMER_EOF'\n{content}\nBROGRAMMER_EOF"
            result = await self._exec_with_retry(write_cmd)
            logs.append(f"$ Writing {file_spec.path}")
            logs.append(result["stdout"])
            created.append(file_spec.path)

        install_result = await self._exec_with_retry(
            f"cd {container_dir} && pip install -r requirements.txt 2>/dev/null; echo 'deps done'"
        )
        logs.append(install_result["stdout"])

        verify_result = await self._exec_with_retry(
            f"cd {container_dir} && python -c 'import sys; print(sys.version)'"
        )
        logs.append(verify_result["stdout"])
        status = "success" if verify_result["exit_code"] == 0 else "failed"

        return BuildArtifact(
            plan_id=plan.plan_id,
            files_created=created,
            files_modified=modified,
            docker_logs=logs,
            status=status,
        )

    async def _exec_with_retry(self, command: str, retries: int = 3) -> dict:
        for attempt in range(retries):
            result = await self.sandbox.exec(command)
            if result["exit_code"] == 0:
                return result
        return result

    async def _generate_file_content(self, plan: TechPlan, file_spec) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"Plan: {plan.model_dump_json(indent=2)}\n"
                    f"Generate content for: {file_spec.path}\n"
                    f"Purpose: {file_spec.purpose}\n"
                    f"Type: {file_spec.content_type}"
                ),
            },
        ]
        response = await self.ollama.chat(messages, format="json", temperature=0.1)
        raw = response["message"]["content"]
        try:
            data = json.loads(raw)
            return data.get(file_spec.path, "# placeholder")
        except json.JSONDecodeError:
            return raw
