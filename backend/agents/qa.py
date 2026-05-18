import re
from backend.core.models import TechPlan, TestPlan, TestReport, TestResult
from backend.agents.specialist import OllamaClient
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

    async def run_tests(self, build_id: str, test_path: str = "tests") -> TestReport:
        result = await self.sandbox.exec(f"python -m pytest {test_path} -v 2>&1")
        return self._parse_test_output(build_id, result["stdout"])

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
