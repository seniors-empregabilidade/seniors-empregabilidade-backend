import os

import pytest

from app.applications.services.find_similar_jobs import find_similar_jobs
from app.db.session import get_session_factory
from tests.applications.conftest import ApplicationsScenario

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]


def test_ranks_published_jobs_by_shared_skill_count(
    scenario: ApplicationsScenario,
) -> None:
    with get_session_factory()() as session:
        suggestions = find_similar_jobs(
            session, job_id=scenario.job_target_id, candidate_id=scenario.owner_id
        )

    ids = [str(job.id) for job in suggestions]
    assert ids[:2] == [
        str(scenario.job_similar_strong_id),
        str(scenario.job_similar_weak_id),
    ]
    assert str(scenario.job_no_match_id) not in ids
    assert str(scenario.job_already_applied_id) not in ids
    assert str(scenario.job_draft_id) not in ids
    assert str(scenario.job_target_id) not in ids


def test_limit_caps_the_number_of_suggestions(
    scenario: ApplicationsScenario,
) -> None:
    with get_session_factory()() as session:
        suggestions = find_similar_jobs(
            session,
            job_id=scenario.job_target_id,
            candidate_id=scenario.owner_id,
            limit=1,
        )

    assert len(suggestions) == 1
    assert suggestions[0].id == scenario.job_similar_strong_id


def test_a_job_with_no_shared_skills_has_no_suggestions(
    scenario: ApplicationsScenario,
) -> None:
    with get_session_factory()() as session:
        suggestions = find_similar_jobs(
            session, job_id=scenario.job_no_match_id, candidate_id=scenario.owner_id
        )

    assert suggestions == []
