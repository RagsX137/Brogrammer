from backend.core.models import (
    FileSpec, ComponentSpec, APIRoute, TechPlan,
    BuildArtifact, TestPlan, TestReport, TestResult,
)


def test_file_spec():
    f = FileSpec(path="src/main.py", purpose="Entry point", content_type="code")
    assert f.path == "src/main.py"
    assert f.content_type == "code"


def test_component_spec():
    c = ComponentSpec(name="Auth", responsibility="Handle login", depends_on=["DB"])
    assert c.name == "Auth"
    assert "DB" in c.depends_on


def test_api_route():
    r = APIRoute(method="GET", path="/users", description="List users")
    assert r.method == "GET"
    assert r.path == "/users"


def test_tech_plan():
    plan = TechPlan(
        understanding_id="u1",
        tech_stack=["FastAPI", "SQLite"],
        file_tree=[FileSpec(path="src/main.py", purpose="Entry", content_type="code")],
        components=[ComponentSpec(name="API", responsibility="Routes")],
        markdown_summary="# Plan",
    )
    assert plan.plan_id is not None
    assert len(plan.tech_stack) == 2
    assert plan.markdown_summary == "# Plan"


def test_build_artifact():
    b = BuildArtifact(plan_id="p1", files_created=["main.py"], files_modified=[], docker_logs=["build ok"], status="success")
    assert b.build_id is not None
    assert b.status == "success"


def test_test_plan():
    tp = TestPlan(build_id="b1", framework="pytest", test_files=[], acceptance_criteria=["tests pass"])
    assert tp.plan_id is not None
    assert tp.framework == "pytest"


def test_test_result():
    tr = TestResult(test_name="test_auth", status="passed")
    assert tr.status == "passed"
    assert tr.error_message is None


def test_test_report():
    report = TestReport(
        build_id="b1",
        passed=5, failed=0, skipped=1,
        details=[TestResult(test_name="test_auth", status="passed")],
    )
    assert report.report_id is not None
    assert report.passed == 5
    assert report.coverage_pct is None
