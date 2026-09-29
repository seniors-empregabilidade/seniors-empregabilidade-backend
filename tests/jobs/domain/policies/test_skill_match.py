from uuid import uuid4

from app.jobs.domain.policies.skill_match import match_skills

PYTHON, EXCEL, LEADERSHIP, SPANISH = uuid4(), uuid4(), uuid4(), uuid4()


def test_a_candidate_with_every_required_skill_misses_nothing() -> None:
    match = match_skills(
        candidate_skill_ids={PYTHON, EXCEL, SPANISH},
        required_skill_ids={PYTHON, EXCEL},
    )

    assert (match.matched_count, match.required_count) == (2, 2)
    assert match.missing_skill_ids == frozenset()


def test_only_the_required_skills_the_candidate_lacks_are_missing() -> None:
    match = match_skills(
        candidate_skill_ids={PYTHON, SPANISH},
        required_skill_ids={PYTHON, EXCEL, LEADERSHIP},
    )

    assert (match.matched_count, match.required_count) == (1, 3)
    assert match.missing_skill_ids == {EXCEL, LEADERSHIP}


def test_a_candidate_without_skills_misses_every_required_one() -> None:
    match = match_skills(candidate_skill_ids=set(), required_skill_ids={PYTHON, EXCEL})

    assert (match.matched_count, match.required_count) == (0, 2)
    assert match.missing_skill_ids == {PYTHON, EXCEL}


def test_a_job_without_required_skills_has_nothing_to_match() -> None:
    match = match_skills(candidate_skill_ids={PYTHON}, required_skill_ids=set())

    assert (match.matched_count, match.required_count) == (0, 0)
    assert match.missing_skill_ids == frozenset()
