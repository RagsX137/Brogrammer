from datetime import datetime, timezone
from backend.core.models import (
    Assumption,
    Unknown,
    MandatoryCategories,
    Understanding,
    SkepticCritique,
    ConfidenceProfile,
)


def test_assumption_defaults():
    a = Assumption(statement="Users want visual feedback")
    assert a.id is not None
    assert a.statement == "Users want visual feedback"
    assert a.status == "open"
    assert a.validated_by is None


def test_assumption_validated_status():
    a = Assumption(status="validated", statement="DB is PostgreSQL", validated_by="human")
    assert a.status == "validated"
    assert a.validated_by == "human"


def test_unknown_defaults():
    u = Unknown(question="What DB to use?")
    assert u.id is not None
    assert u.question == "What DB to use?"
    assert u.resolution is None
    assert u.resolved_at is None


def test_unknown_resolved():
    now = datetime.now(timezone.utc)
    u = Unknown(question="What DB?", resolution="SQLite", resolved_at=now)
    assert u.resolution == "SQLite"
    assert u.resolved_at == now


def test_mandatory_categories_defaults():
    mc = MandatoryCategories()
    assert mc.accessibility == []
    assert mc.performance == []
    assert mc.security == []
    assert mc.state_management == []
    assert mc.persistence == []


def test_understanding_full():
    mc = MandatoryCategories(performance=["latency < 200ms"])
    u = Understanding(
        goal="Build a habit tracker",
        assumptions=[Assumption(statement="Users want streaks")],
        unknowns=[Unknown(question="What framework?")],
        mandatory_categories=mc,
    )
    assert u.goal == "Build a habit tracker"
    assert len(u.assumptions) == 1
    assert len(u.unknowns) == 1
    assert u.mandatory_categories.performance == ["latency < 200ms"]


def test_understanding_has_id():
    u = Understanding(goal="test")
    assert u.id is not None


def test_skeptic_critique_defaults():
    sc = SkepticCritique(understanding_id="uid-1")
    assert sc.critique_id is not None
    assert sc.understanding_id == "uid-1"
    assert sc.scenarios == []
    assert sc.questions == []
    assert sc.tool_evidence == []


def test_confidence_profile_defaults():
    cp = ConfidenceProfile(
        score=0.75,
        open_unknowns=2,
        total_unknowns=8,
        validation_ratio=0.5,
    )
    assert cp.score == 0.75
    assert cp.open_unknowns == 2
    assert cp.total_unknowns == 8
    assert cp.validation_ratio == 0.5
    assert cp.fragility_flag is False


def test_confidence_profile_fragile():
    cp = ConfidenceProfile(
        score=0.3,
        open_unknowns=5,
        total_unknowns=10,
        validation_ratio=0.2,
        fragility_flag=True,
    )
    assert cp.fragility_flag is True
