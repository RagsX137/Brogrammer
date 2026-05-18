from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field


class Assumption(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    statement: str
    status: str = "open"
    validated_by: str | None = None


class Unknown(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    question: str
    resolution: str | None = None
    resolved_at: datetime | None = None


class MandatoryCategories(BaseModel):
    accessibility: list[str] = []
    performance: list[str] = []
    security: list[str] = []
    state_management: list[str] = []
    persistence: list[str] = []


class Understanding(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    goal: str
    assumptions: list[Assumption] = []
    unknowns: list[Unknown] = []
    mandatory_categories: MandatoryCategories = MandatoryCategories()


class SkepticCritique(BaseModel):
    critique_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    understanding_id: str = ""
    scenarios: list[str] = []
    questions: list[str] = []
    tool_evidence: list[str] = []


class ConfidenceProfile(BaseModel):
    score: float
    open_unknowns: int
    total_unknowns: int
    validation_ratio: float
    fragility_flag: bool = False


class FileSpec(BaseModel):
    path: str
    purpose: str
    content_type: str  # "code" | "config" | "test" | "doc"


class ComponentSpec(BaseModel):
    name: str
    responsibility: str
    depends_on: list[str] = []


class APIRoute(BaseModel):
    method: str  # GET | POST | PUT | DELETE
    path: str
    description: str


class TechPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    understanding_id: str
    tech_stack: list[str]
    file_tree: list[FileSpec]
    components: list[ComponentSpec]
    api_routes: list[APIRoute] = []
    markdown_summary: str


class BuildArtifact(BaseModel):
    build_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    plan_id: str
    files_created: list[str]
    files_modified: list[str]
    docker_logs: list[str]
    status: str  # "success" | "failed"


class TestPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    build_id: str
    framework: str
    test_files: list[FileSpec]
    acceptance_criteria: list[str]


class TestResult(BaseModel):
    test_name: str
    status: str  # "passed" | "failed" | "skipped"
    error_message: str | None = None


class TestReport(BaseModel):
    report_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    build_id: str
    passed: int
    failed: int
    skipped: int
    coverage_pct: float | None = None
    details: list[TestResult] = []
