from uuid import UUID

import pytest

from app.jobs.domain.policies.automatic_match_policy import is_automatic_match
from app.jobs.domain.policies.job_compatibility_policy import JobCompatibilityPolicy

PYTHON = UUID("00000000-0000-0000-0000-00000000000a")
SQL = UUID("00000000-0000-0000-0000-00000000000b")
LEADERSHIP = UUID("00000000-0000-0000-0000-00000000000c")

CANDIDATE = UUID("00000000-0000-0000-0000-000000000001")


@pytest.mark.parametrize(
    ("candidate_skill_ids", "expected"),
    [
        ([PYTHON, SQL, LEADERSHIP], True),
        ([PYTHON, SQL], True),
        ([PYTHON], False),
        ([], False),
    ],
    ids=["100%", "66.67%", "33.33%", "0%"],
)
def test_automatic_match_follows_the_highlight_threshold(
    candidate_skill_ids: list[UUID], expected: bool
) -> None:
    score = JobCompatibilityPolicy([PYTHON, SQL, LEADERSHIP]).score(
        CANDIDATE, candidate_skill_ids
    )

    assert is_automatic_match(score) is expected


def test_exactly_fifty_percent_is_an_automatic_match() -> None:
    score = JobCompatibilityPolicy([PYTHON, SQL]).score(CANDIDATE, [PYTHON])

    assert is_automatic_match(score)
