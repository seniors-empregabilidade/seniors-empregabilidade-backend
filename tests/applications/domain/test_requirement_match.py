from uuid import uuid4

from app.applications.domain.policies.requirement_match import match_requirements


def test_partial_overlap_counts_only_the_shared_skills() -> None:
    python_id, english_id, spanish_id = uuid4(), uuid4(), uuid4()

    result = match_requirements(
        required_skill_ids=[python_id, english_id],
        candidate_skill_ids=[python_id, spanish_id],
    )

    assert result.matched == 1
    assert result.total == 2


def test_full_overlap_matches_every_requirement() -> None:
    python_id, english_id = uuid4(), uuid4()

    result = match_requirements(
        required_skill_ids=[python_id, english_id],
        candidate_skill_ids=[python_id, english_id, uuid4()],
    )

    assert result.matched == 2
    assert result.total == 2


def test_no_overlap_matches_nothing() -> None:
    result = match_requirements(
        required_skill_ids=[uuid4(), uuid4()],
        candidate_skill_ids=[uuid4()],
    )

    assert result.matched == 0
    assert result.total == 2


def test_a_job_with_no_required_skills_has_zero_total() -> None:
    result = match_requirements(
        required_skill_ids=[],
        candidate_skill_ids=[uuid4(), uuid4()],
    )

    assert result.matched == 0
    assert result.total == 0


def test_duplicate_required_skill_ids_count_once() -> None:
    shared = uuid4()

    result = match_requirements(
        required_skill_ids=[shared, shared],
        candidate_skill_ids=[shared],
    )

    assert result.matched == 1
    assert result.total == 1
