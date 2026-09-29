from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Job
from app.db.models.enums import JobStatus, WorkMode
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


def test_keeps_the_fields_the_minhas_vagas_screen_reads(
    manage_jobs_client: TestClient, manage_jobs_scenario: ManageJobsScenario
) -> None:
    response = manage_jobs_client.get(
        LIST_PATH, headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN)
    )

    open_job = next(
        item
        for item in response.json()
        if item["id"] == str(manage_jobs_scenario.open_job_id)
    )
    assert set(open_job) == {
        "id",
        "company_id",
        "title",
        "description",
        "skills",
        "work_mode",
        "closing_date",
        "status",
        "published_at",
        "created_at",
        "application_count",
    }
    assert open_job["company_id"] == str(manage_jobs_scenario.owner_company_id)


def test_a_job_never_published_is_listed_without_a_publication_date(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    draft = Job(
        company_id=manage_jobs_scenario.owner_company_id,
        title="Manage Jobs Draft Role",
        description="Synthetic draft for manage-jobs tests.",
        work_mode=WorkMode.HYBRID,
        closing_date=date.today() + timedelta(days=30),
    )
    database_session.add(draft)
    database_session.commit()

    response = manage_jobs_client.get(
        LIST_PATH, headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN)
    )

    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()}
    assert items[str(draft.id)]["status"] == JobStatus.DRAFT.value
    assert items[str(draft.id)]["published_at"] is None
    assert len(items) == 3
