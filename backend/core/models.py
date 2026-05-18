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
