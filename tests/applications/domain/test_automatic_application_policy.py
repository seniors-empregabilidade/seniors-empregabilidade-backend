from uuid import uuid4

import pytest

from app.applications.domain.policies.automatic_application_policy import (
    qualifies_for_automatic_application,
)
from app.jobs.domain.value_objects.compatibility_score import CompatibilityScore


def _score(matched: int, missing: int) -> CompatibilityScore:
    return CompatibilityScore(
        candidate_id=uuid4(),
        matched_skill_ids=frozenset(uuid4() for _ in range(matched)),
        missing_skill_ids=frozenset(uuid4() for _ in range(missing)),
    )


@pytest.mark.parametrize(
    ("matched", "missing", "expected"),
    [(7, 3, True), (8, 2, True), (10, 0, True), (6, 4, False), (0, 5, False)],
)
def test_threshold_is_inclusive(matched: int, missing: int, expected: bool) -> None:
    assert qualifies_for_automatic_application(_score(matched, missing), 70) is expected


def test_exact_ratio_is_compared_instead_of_the_rounded_percentage() -> None:
    # 2 of 3 is 66.666...%, which rounds to 66.67% but never reaches 67%.
    assert qualifies_for_automatic_application(_score(2, 1), 67) is False
    assert qualifies_for_automatic_application(_score(2, 1), 66) is True


def test_threshold_follows_the_configured_value() -> None:
    score = _score(1, 1)

    assert qualifies_for_automatic_application(score, 50) is True
    assert qualifies_for_automatic_application(score, 51) is False
