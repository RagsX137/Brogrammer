import pytest
from backend.core.confidence import compute_confidence
from backend.core.models import MandatoryCategories


def test_confidence_basic():
    profile = compute_confidence(
        open_unknowns=2,
        total_unknowns=10,
        validated_count=5,
        total_assumptions=5,
        mandatory_categories=MandatoryCategories(
            accessibility=["screen reader"],
            performance=["latency < 200ms"],
            security=["auth required"],
            state_management=["redux"],
            persistence=["sqlite"],
        ),
        fragility_flag=False,
    )
    assert profile.score == pytest.approx(0.8)
    assert profile.open_unknowns == 2
    assert profile.total_unknowns == 10
    assert profile.validation_ratio == 1.0
    assert profile.fragility_flag is False


def test_confidence_zero_total_unknowns():
    profile = compute_confidence(
        open_unknowns=0,
        total_unknowns=0,
        validated_count=3,
        total_assumptions=3,
        mandatory_categories=MandatoryCategories(
            accessibility=["a"], performance=["b"], security=["c"],
            state_management=["d"], persistence=["e"],
        ),
        fragility_flag=False,
    )
    assert profile.score == 0.5


def test_confidence_capped_by_validation_ratio():
    profile = compute_confidence(
        open_unknowns=1,
        total_unknowns=10,
        validated_count=1,
        total_assumptions=5,
        mandatory_categories=MandatoryCategories(
            accessibility=["a"], performance=["b"], security=["c"],
            state_management=["d"], persistence=["e"],
        ),
        fragility_flag=False,
    )
    assert profile.score == pytest.approx(0.2)


def test_confidence_mandatory_category_penalty():
    profile = compute_confidence(
        open_unknowns=2,
        total_unknowns=10,
        validated_count=5,
        total_assumptions=5,
        mandatory_categories=MandatoryCategories(performance=["x"]),
        fragility_flag=False,
    )
    assert profile.score == pytest.approx(0.4)


def test_confidence_multiple_empty_categories_single_penalty():
    profile = compute_confidence(
        open_unknowns=2,
        total_unknowns=10,
        validated_count=5,
        total_assumptions=5,
        mandatory_categories=MandatoryCategories(),
        fragility_flag=False,
    )
    assert profile.score == pytest.approx(0.4)


def test_confidence_fragility_flag_passed_through():
    profile = compute_confidence(
        open_unknowns=2,
        total_unknowns=10,
        validated_count=5,
        total_assumptions=5,
        mandatory_categories=MandatoryCategories(performance=["x"]),
        fragility_flag=True,
    )
    assert profile.fragility_flag is True


def test_confidence_clamp_negative():
    profile = compute_confidence(
        open_unknowns=10,
        total_unknowns=10,
        validated_count=0,
        total_assumptions=1,
        mandatory_categories=MandatoryCategories(performance=["x"]),
        fragility_flag=False,
    )
    assert profile.score >= 0.0
