from decimal import Decimal
from uuid import UUID

import pytest

from app.jobs.domain.exceptions import JobWithoutRequiredSkillsError
from app.jobs.domain.policies.job_compatibility_policy import JobCompatibilityPolicy

PYTHON = UUID("00000000-0000-0000-0000-00000000000a")
SQL = UUID("00000000-0000-0000-0000-00000000000b")
LEADERSHIP = UUID("00000000-0000-0000-0000-00000000000c")
EXCEL = UUID("00000000-0000-0000-0000-00000000000d")

CANDIDATE_A = UUID("00000000-0000-0000-0000-000000000001")
CANDIDATE_B = UUID("00000000-0000-0000-0000-000000000002")
CANDIDATE_C = UUID("00000000-0000-0000-0000-000000000003")
CANDIDATE_D = UUID("00000000-0000-0000-0000-000000000004")


def test_full_match_lists_every_required_skill() -> None:
    score = JobCompatibilityPolicy([PYTHON, SQL]).score(
        CANDIDATE_A, [PYTHON, SQL, EXCEL]
    )
    assert score.percentage == Decimal("100.00")
    assert score.is_highlighted
    assert score.matched_skill_ids == {PYTHON, SQL}
    assert score.missing_skill_ids == frozenset()


def test_extra_candidate_skills_do_not_count() -> None:
    score = JobCompatibilityPolicy([PYTHON, SQL]).score(CANDIDATE_A, [PYTHON, EXCEL])
    assert score.matched_skill_ids == {PYTHON}
    assert score.missing_skill_ids == {SQL}
    assert score.percentage == Decimal("50.00")


def test_repeated_skill_ids_count_once() -> None:
    score = JobCompatibilityPolicy([PYTHON, PYTHON, SQL]).score(
        CANDIDATE_A, [PYTHON, PYTHON]
    )
    assert score.required_count == 2
    assert score.percentage == Decimal("50.00")


def test_candidate_without_skills_scores_zero() -> None:
    score = JobCompatibilityPolicy([PYTHON]).score(CANDIDATE_A, [])
    assert score.percentage == Decimal("0.00")
    assert score.missing_skill_ids == {PYTHON}


def test_job_without_required_skills_is_rejected() -> None:
    with pytest.raises(JobWithoutRequiredSkillsError):
        JobCompatibilityPolicy([])


def test_rank_orders_by_percentage_and_keeps_low_scores() -> None:
    ranking = JobCompatibilityPolicy([PYTHON, SQL, LEADERSHIP]).rank(
        {
            CANDIDATE_D: [],
            CANDIDATE_C: [PYTHON],
            CANDIDATE_B: [EXCEL],
            CANDIDATE_A: [PYTHON, SQL, LEADERSHIP],
        }
    )
    assert [score.candidate_id for score in ranking] == [
        CANDIDATE_A,
        CANDIDATE_C,
        CANDIDATE_D,
        CANDIDATE_B,
    ]
    assert [score.is_highlighted for score in ranking] == [True, False, False, False]


def test_rank_keeps_the_given_order_for_ties() -> None:
    ranking = JobCompatibilityPolicy([PYTHON]).rank(
        {CANDIDATE_C: [PYTHON], CANDIDATE_A: [PYTHON], CANDIDATE_B: [PYTHON]}
    )
    assert [score.candidate_id for score in ranking] == [
        CANDIDATE_C,
        CANDIDATE_A,
        CANDIDATE_B,
    ]


def test_rank_without_candidates_is_empty() -> None:
    assert JobCompatibilityPolicy([PYTHON]).rank({}) == []
