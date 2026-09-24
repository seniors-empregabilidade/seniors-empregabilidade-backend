import os
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import Application
from app.db.session import get_session_factory
from tests.applications.conftest import (
    SUBMIT_TOKEN,
    SubmissionScenario,
    authorization,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]

CREATE_PATH = "/api/v1/applications"


def test_owner_can_apply_to_an_open_job(
    applications_client: TestClient, submission_scenario: SubmissionScenario
) -> None:
    response = applications_client.post(
        CREATE_PATH,
        json={"job_id": str(submission_scenario.job_open_id)},
        headers=authorization(SUBMIT_TOKEN),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["job_id"] == str(submission_scenario.job_open_id)
    assert body["status"] == "under_review"
    assert body["matched_requirements"] == 1
    assert body["total_requirements"] == 2
    assert body["submitted_at"] is not None

    with get_session_factory()() as session:
        application = session.get(Application, UUID(body["id"]))
        assert application is not None
        assert application.candidate_id == submission_scenario.owner_id
        assert application.matched_requirements == 1
        assert application.total_requirements == 2


def test_duplicate_application_is_a_conflict(
    applications_client: TestClient, submission_scenario: SubmissionScenario
) -> None:
    response = applications_client.post(
        CREATE_PATH,
        json={"job_id": str(submission_scenario.job_already_applied_id)},
        headers=authorization(SUBMIT_TOKEN),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "application_already_exists"
    with get_session_factory()() as session:
        rows = session.scalars(
            select(Application).where(
                Application.candidate_id == submission_scenario.owner_id,
                Application.job_id == submission_scenario.job_already_applied_id,
            )
        ).all()
        assert len(rows) == 1


def test_applying_to_a_draft_job_is_rejected(
    applications_client: TestClient, submission_scenario: SubmissionScenario
) -> None:
    response = applications_client.post(
        CREATE_PATH,
        json={"job_id": str(submission_scenario.job_draft_id)},
        headers=authorization(SUBMIT_TOKEN),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "job_not_open"


def test_applying_to_an_expired_job_is_rejected(
    applications_client: TestClient, submission_scenario: SubmissionScenario
) -> None:
    response = applications_client.post(
        CREATE_PATH,
        json={"job_id": str(submission_scenario.job_expired_id)},
        headers=authorization(SUBMIT_TOKEN),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "job_not_open"


def test_applying_to_a_nonexistent_job_is_not_found(
    applications_client: TestClient, submission_scenario: SubmissionScenario
) -> None:
    response = applications_client.post(
        CREATE_PATH,
        json={"job_id": str(uuid4())},
        headers=authorization(SUBMIT_TOKEN),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "job_not_found"


def test_unauthenticated_request_is_rejected(
    applications_client: TestClient, submission_scenario: SubmissionScenario
) -> None:
    response = applications_client.post(
        CREATE_PATH, json={"job_id": str(submission_scenario.job_open_id)}
    )

    assert response.status_code == 401
    with get_session_factory()() as session:
        rows = session.scalars(
            select(Application).where(
                Application.candidate_id == submission_scenario.owner_id,
                Application.job_id == submission_scenario.job_open_id,
            )
        ).all()
        assert rows == []


def test_concurrent_applications_to_the_same_job_only_create_one(
    applications_client: TestClient, submission_scenario: SubmissionScenario
) -> None:
    def submit(_: int) -> int:
        return applications_client.post(
            CREATE_PATH,
            json={"job_id": str(submission_scenario.job_open_id)},
            headers=authorization(SUBMIT_TOKEN),
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = sorted(executor.map(submit, range(2)))

    assert outcomes == [201, 409]
    with get_session_factory()() as session:
        rows = session.scalars(
            select(Application).where(
                Application.candidate_id == submission_scenario.owner_id,
                Application.job_id == submission_scenario.job_open_id,
            )
        ).all()
        assert len(rows) == 1
