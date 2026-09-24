import pytest
from fastapi.testclient import TestClient

from app.db.models.enums import JobStatus
from tests.jobs.conftest import (
    MANAGE_JOBS_OWNER_TOKEN,
    ManageJobsScenario,
    manage_jobs_authorization,
)

pytestmark = pytest.mark.integration

LIST_PATH = "/api/v1/jobs/me"


def test_unauthenticated_request_is_rejected(
    manage_jobs_client: TestClient, manage_jobs_scenario: ManageJobsScenario
) -> None:
    response = manage_jobs_client.get(LIST_PATH)

    assert response.status_code == 401


def test_only_returns_the_authenticated_companys_jobs(
    manage_jobs_client: TestClient, manage_jobs_scenario: ManageJobsScenario
) -> None:
    response = manage_jobs_client.get(
        LIST_PATH, headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN)
    )

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert str(manage_jobs_scenario.open_job_id) in ids
    assert str(manage_jobs_scenario.closed_job_id) in ids
    assert str(manage_jobs_scenario.other_company_job_id) not in ids


def test_each_job_carries_its_own_status_and_application_count(
    manage_jobs_client: TestClient, manage_jobs_scenario: ManageJobsScenario
) -> None:
    response = manage_jobs_client.get(
        LIST_PATH, headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN)
    )

    items = {item["id"]: item for item in response.json()}
    open_job = items[str(manage_jobs_scenario.open_job_id)]
    closed_job = items[str(manage_jobs_scenario.closed_job_id)]

    assert open_job["status"] == JobStatus.PUBLISHED.value
    assert open_job["application_count"] == 2
    assert closed_job["status"] == JobStatus.CLOSED.value
    assert closed_job["application_count"] == 0


def test_a_jobs_structured_skills_are_included(
    manage_jobs_client: TestClient, manage_jobs_scenario: ManageJobsScenario
) -> None:
    response = manage_jobs_client.get(
        LIST_PATH, headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN)
    )

    items = {item["id"]: item for item in response.json()}
    open_job = items[str(manage_jobs_scenario.open_job_id)]

    assert open_job["skills"] == [
        {
            "id": str(manage_jobs_scenario.skill_id),
            "name": "Manage Jobs Python",
            "type": "hard",
        }
    ]
