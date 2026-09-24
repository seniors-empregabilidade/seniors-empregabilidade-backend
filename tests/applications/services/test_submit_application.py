import os
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.applications.exceptions import (
    ApplicationAlreadyExistsError,
    JobNotFoundError,
    JobNotOpenError,
)
from app.applications.services.submit_application import submit_application
from app.db.models import Application
from app.db.models.enums import ApplicationStatus
from app.db.session import get_session_factory
from tests.applications.conftest import SubmissionScenario

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]


def test_creates_an_application_with_partial_compatibility(
    submission_scenario: SubmissionScenario,
) -> None:
    with get_session_factory()() as session:
        submitted = submit_application(
            session,
            job_id=submission_scenario.job_open_id,
            candidate_id=submission_scenario.owner_id,
            now=submission_scenario.now,
        )

    assert submitted.job_id == submission_scenario.job_open_id
    assert submitted.status == ApplicationStatus.UNDER_REVIEW
    assert submitted.matched_requirements == 1
    assert submitted.total_requirements == 2
    assert submitted.submitted_at is not None

    with get_session_factory()() as session:
        stored = session.get(Application, submitted.id)
        assert stored is not None
        assert stored.candidate_id == submission_scenario.owner_id
        assert stored.status == ApplicationStatus.UNDER_REVIEW
        assert stored.matched_requirements == 1
        assert stored.total_requirements == 2


def test_duplicate_application_is_a_conflict_and_creates_nothing(
    submission_scenario: SubmissionScenario,
) -> None:
    with (
        get_session_factory()() as session,
        pytest.raises(ApplicationAlreadyExistsError),
    ):
        submit_application(
            session,
            job_id=submission_scenario.job_already_applied_id,
            candidate_id=submission_scenario.owner_id,
            now=submission_scenario.now,
        )

    with get_session_factory()() as session:
        rows = session.scalars(
            select(Application).where(
                Application.candidate_id == submission_scenario.owner_id,
                Application.job_id == submission_scenario.job_already_applied_id,
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].id == submission_scenario.application_on_already_applied_job_id


def test_applying_to_a_draft_job_is_rejected(
    submission_scenario: SubmissionScenario,
) -> None:
    with get_session_factory()() as session, pytest.raises(JobNotOpenError):
        submit_application(
            session,
            job_id=submission_scenario.job_draft_id,
            candidate_id=submission_scenario.owner_id,
            now=submission_scenario.now,
        )


def test_applying_to_an_expired_job_is_rejected(
    submission_scenario: SubmissionScenario,
) -> None:
    with get_session_factory()() as session, pytest.raises(JobNotOpenError):
        submit_application(
            session,
            job_id=submission_scenario.job_expired_id,
            candidate_id=submission_scenario.owner_id,
            now=submission_scenario.now,
        )


def test_applying_to_a_nonexistent_job_is_not_found(
    submission_scenario: SubmissionScenario,
) -> None:
    with get_session_factory()() as session, pytest.raises(JobNotFoundError):
        submit_application(
            session,
            job_id=uuid4(),
            candidate_id=submission_scenario.owner_id,
            now=submission_scenario.now,
        )
