import base64
import json
import re
from backend.core.models import TechPlan, TestPlan, TestReport, TestResult
from backend.agents.specialist import OllamaClient
from backend.agents._retry import with_retries
from backend.orchestrator.sandbox import SandboxManager


class QAAgent:
    def __init__(self, ollama_client: OllamaClient | None = None,
                 sandbox: SandboxManager | None = None):
        self.ollama = ollama_client or OllamaClient()
        self.sandbox = sandbox or SandboxManager()
        self.system_prompt = (
            "You are the QAAgent. Given a TechPlan, generate a test plan. "
            "Return ONLY valid JSON — no markdown. "
            'Format: {"build_id": "", "framework": "pytest", '
            '"test_files": [{"path": "tests/test_app.py", "purpose": "Main tests", "content_type": "test"}], '
            '"acceptance_criteria": ["all tests pass", "coverage > 80%"]}'
        )
        self.content_prompt = (
            "You are the QAAgent. Given a TechPlan and a test file specification, produce the actual test code. "
            "Return ONLY valid JSON with a single key 'content' mapping to the file contents. "
            "No markdown, no explanation."
        )

    @with_retries(retries=3)
    async def generate_test_plan(self, plan: TechPlan) -> TestPlan:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"TechPlan: {plan.model_dump_json(indent=2)}"},
        ]
        response = await self.ollama.chat(messages, format="json", temperature=0.2)
        raw = response["message"]["content"]
        data = TestPlan.model_validate_json(raw)
        data.build_id = ""
        return data

    async def write_test_files(self, plan: TestPlan) -> None:
        for file_spec in plan.test_files:
            content = await self._generate_file_content(file_spec)
            parent_cmd = f"mkdir -p /workspace/{file_spec.path.rsplit('/', 1)[0]}" if "/" in file_spec.path else "true"
            await self.sandbox.exec(parent_cmd)
            b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
            write_cmd = f"echo '{b64}' | base64 -d > /workspace/{file_spec.path}"
            await self.sandbox.exec(write_cmd)

    async def run_tests(self, build_id: str, test_path: str = "tests") -> TestReport:
        result = await self.sandbox.exec(f"python -m pytest {test_path} -v 2>&1")
        report = self._parse_test_output(build_id, result["stdout"])
        if report.passed == 0 and report.failed == 0 and report.skipped == 0:
            report.failed = 1
            report.error_message = "no tests collected"
        return report

    def _parse_test_output(self, build_id: str, output: str) -> TestReport:
        passed = len(re.findall(r"PASSED", output))
        failed = len(re.findall(r"FAILED", output))
        skipped = len(re.findall(r"SKIPPED", output))

        details = []
        for line in output.split("\n"):
            for status in ("PASSED", "FAILED", "SKIPPED"):
                if status in line:
                    details.append(TestResult(
                        test_name=line.strip(),
                        status=status.lower(),
                    ))

        return TestReport(
            build_id=build_id,
            passed=passed,
            failed=failed,
            skipped=skipped,
            details=details,
        )

    @with_retries(retries=3)
    async def _generate_file_content(self, file_spec) -> str:
        messages = [
            {"role": "system", "content": self.content_prompt},
            {
                "role": "user",
                "content": (
                    f"Generate test content for: {file_spec.path}\n"
                    f"Purpose: {file_spec.purpose}\n"
                    f"Type: {file_spec.content_type}"
                ),
            },
        ]
        response = await self.ollama.chat(messages, format="json", temperature=0.2)
        raw = response["message"]["content"]
        data = json.loads(raw)
        return data.get("content", "# test placeholder")
