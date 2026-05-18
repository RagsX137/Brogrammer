from backend.core.models import ConfidenceProfile, MandatoryCategories


_MANDATORY_FIELDS = [
    "accessibility",
    "performance",
    "security",
    "state_management",
    "persistence",
]


def _any_category_empty(mc: MandatoryCategories) -> bool:
    for field in _MANDATORY_FIELDS:
        if not getattr(mc, field):
            return True
    return False


def compute_confidence(
    open_unknowns: int,
    total_unknowns: int,
    validated_count: int,
    total_assumptions: int,
    mandatory_categories: MandatoryCategories,
    fragility_flag: bool = False,
) -> ConfidenceProfile:
    if total_unknowns == 0:
        base_score = 0.5
    else:
        base_score = max(0.0, 1.0 - (open_unknowns / total_unknowns))

    validation_ratio = validated_count / total_assumptions if total_assumptions > 0 else 0.0

    score = min(base_score, validation_ratio)

    if _any_category_empty(mandatory_categories):
        score *= 0.5

    return ConfidenceProfile(
        score=round(score, 4),
        open_unknowns=open_unknowns,
        total_unknowns=total_unknowns,
        validation_ratio=validation_ratio,
        fragility_flag=fragility_flag,
    )
