from decimal import Decimal
from uuid import UUID

import pytest

from app.jobs.domain.exceptions import JobWithoutRequiredSkillsError
from app.jobs.domain.value_objects.compatibility_score import CompatibilityScore

CANDIDATE_ID = UUID("00000000-0000-0000-0000-000000000001")


def skill_ids(count: int, start: int = 0) -> frozenset[UUID]:
    return frozenset(UUID(int=1000 + index) for index in range(start, start + count))


def build_score(matched: int, missing: int) -> CompatibilityScore:
    return CompatibilityScore(
        candidate_id=CANDIDATE_ID,
        matched_skill_ids=skill_ids(matched),
        missing_skill_ids=skill_ids(missing, start=matched),
    )


def test_percentage_rounds_half_up_to_two_places() -> None:
    assert build_score(matched=2, missing=1).percentage == Decimal("66.67")


def test_exactly_half_is_highlighted() -> None:
    score = build_score(matched=1, missing=1)
    assert score.percentage == Decimal("50.00")
    assert score.is_highlighted


def test_below_half_is_not_highlighted() -> None:
    assert not build_score(matched=1, missing=2).is_highlighted


def test_rounding_to_fifty_does_not_highlight() -> None:
    score = build_score(matched=5000, missing=5001)
    assert score.percentage == Decimal("50.00")
    assert not score.is_highlighted


def test_no_required_skills_is_rejected() -> None:
    with pytest.raises(JobWithoutRequiredSkillsError):
        build_score(matched=0, missing=0)


def test_skill_cannot_be_matched_and_missing() -> None:
    with pytest.raises(ValueError, match="both matched and missing"):
        CompatibilityScore(
            candidate_id=CANDIDATE_ID,
            matched_skill_ids=skill_ids(1),
            missing_skill_ids=skill_ids(1),
        )
