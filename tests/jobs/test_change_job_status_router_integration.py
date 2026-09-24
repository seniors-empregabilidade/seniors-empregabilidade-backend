from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Job
from app.db.models.enums import JobStatus
from tests.jobs.conftest import (
    MANAGE_JOBS_OTHER_TOKEN,
    MANAGE_JOBS_OWNER_TOKEN,
    ManageJobsScenario,
    manage_jobs_authorization,
)

pytestmark = pytest.mark.integration


def status_path(job_id: object) -> str:
    return f"/api/v1/jobs/{job_id}/status"


def test_owner_can_close_an_open_job(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    response = manage_jobs_client.patch(
        status_path(manage_jobs_scenario.open_job_id),
        json={"status": "closed"},
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 200
    assert response.json()["status"] == JobStatus.CLOSED.value
    job = database_session.get(Job, manage_jobs_scenario.open_job_id)
    assert job is not None
    assert job.status == JobStatus.CLOSED


def test_owner_can_reopen_a_closed_job(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    response = manage_jobs_client.patch(
        status_path(manage_jobs_scenario.closed_job_id),
        json={"status": "open"},
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 200
    assert response.json()["status"] == JobStatus.PUBLISHED.value
    job = database_session.get(Job, manage_jobs_scenario.closed_job_id)
    assert job is not None
    assert job.status == JobStatus.PUBLISHED


def test_closing_an_already_closed_job_is_a_conflict(
    manage_jobs_client: TestClient, manage_jobs_scenario: ManageJobsScenario
) -> None:
    response = manage_jobs_client.patch(
        status_path(manage_jobs_scenario.closed_job_id),
        json={"status": "closed"},
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "job_already_closed"


def test_reopening_an_already_open_job_is_a_conflict(
    manage_jobs_client: TestClient, manage_jobs_scenario: ManageJobsScenario
) -> None:
    response = manage_jobs_client.patch(
        status_path(manage_jobs_scenario.open_job_id),
        json={"status": "open"},
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "job_already_open"


def test_a_nonexistent_job_is_not_found(
    manage_jobs_client: TestClient, manage_jobs_scenario: ManageJobsScenario
) -> None:
    response = manage_jobs_client.patch(
        status_path(uuid4()),
        json={"status": "closed"},
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "job_not_found"


def test_a_company_cannot_close_another_companys_job(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    response = manage_jobs_client.patch(
        status_path(manage_jobs_scenario.other_company_job_id),
        json={"status": "closed"},
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "job_not_found"
    job = database_session.get(Job, manage_jobs_scenario.other_company_job_id)
    assert job is not None
    assert job.status == JobStatus.PUBLISHED


def test_unauthenticated_request_is_rejected(
    manage_jobs_client: TestClient, manage_jobs_scenario: ManageJobsScenario
) -> None:
    response = manage_jobs_client.patch(
        status_path(manage_jobs_scenario.open_job_id), json={"status": "closed"}
    )

    assert response.status_code == 401


def test_another_companys_token_cannot_close_the_owners_job(
    manage_jobs_client: TestClient, manage_jobs_scenario: ManageJobsScenario
) -> None:
    response = manage_jobs_client.patch(
        status_path(manage_jobs_scenario.open_job_id),
        json={"status": "closed"},
        headers=manage_jobs_authorization(MANAGE_JOBS_OTHER_TOKEN),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "job_not_found"
