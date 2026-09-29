from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.local_date import to_local_date
from app.db.models import Job
from app.db.models.enums import JobStatus, WorkMode
from app.jobs.services import search_jobs
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
    database_session.expire_all()
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
    database_session.expire_all()
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
    database_session.expire_all()
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


def local_today() -> date:
    return to_local_date(datetime.now(UTC))


def titles_candidates_find(session: Session) -> list[str]:
    found = search_jobs(
        session, candidate_id=uuid4(), search="Manage Jobs", limit=100, offset=0
    )
    return [job.title for job in found]


def set_closing_date(session: Session, job_id: UUID, closing_date: date) -> None:
    job = session.get(Job, job_id)
    assert job is not None
    job.closing_date = closing_date
    session.commit()


def test_a_closed_job_leaves_the_candidate_search_until_reopened(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    owner = manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN)
    assert "Manage Jobs Open Role" in titles_candidates_find(database_session)

    closed = manage_jobs_client.patch(
        status_path(manage_jobs_scenario.open_job_id),
        json={"status": "closed"},
        headers=owner,
    )
    assert closed.status_code == 200
    assert "Manage Jobs Open Role" not in titles_candidates_find(database_session)

    reopened = manage_jobs_client.patch(
        status_path(manage_jobs_scenario.open_job_id),
        json={"status": "open"},
        headers=owner,
    )
    assert reopened.status_code == 200
    assert "Manage Jobs Open Role" in titles_candidates_find(database_session)


def test_reopening_past_the_closing_date_requires_a_new_one(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    owner = manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN)
    set_closing_date(
        database_session,
        manage_jobs_scenario.closed_job_id,
        local_today() - timedelta(days=1),
    )

    refused = manage_jobs_client.patch(
        status_path(manage_jobs_scenario.closed_job_id),
        json={"status": "open"},
        headers=owner,
    )

    assert refused.status_code == 422
    assert refused.json()["code"] == "closing_date_in_the_past"
    assert "closing_date" in refused.json()["errors"]
    database_session.expire_all()
    job = database_session.get(Job, manage_jobs_scenario.closed_job_id)
    assert job is not None
    assert job.status == JobStatus.CLOSED

    new_closing_date = local_today() + timedelta(days=15)
    reopened = manage_jobs_client.patch(
        status_path(manage_jobs_scenario.closed_job_id),
        json={"status": "open", "closing_date": new_closing_date.isoformat()},
        headers=owner,
    )

    assert reopened.status_code == 200
    assert reopened.json()["status"] == JobStatus.PUBLISHED.value
    assert reopened.json()["closing_date"] == new_closing_date.isoformat()
    assert "Manage Jobs Closed Role" in titles_candidates_find(database_session)


def test_a_published_job_past_its_closing_date_reopens_with_a_new_one(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    set_closing_date(
        database_session,
        manage_jobs_scenario.open_job_id,
        local_today() - timedelta(days=1),
    )
    new_closing_date = local_today() + timedelta(days=7)

    response = manage_jobs_client.patch(
        status_path(manage_jobs_scenario.open_job_id),
        json={"status": "open", "closing_date": new_closing_date.isoformat()},
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 200
    assert response.json()["closing_date"] == new_closing_date.isoformat()
    assert "Manage Jobs Open Role" in titles_candidates_find(database_session)


@pytest.mark.parametrize("status", ["open", "closed"])
def test_a_draft_does_not_change_status_here(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
    status: str,
) -> None:
    draft = Job(
        company_id=manage_jobs_scenario.owner_company_id,
        title="Manage Jobs Draft Role",
        description="Synthetic draft for manage-jobs tests.",
        work_mode=WorkMode.HYBRID,
        closing_date=local_today() + timedelta(days=30),
    )
    database_session.add(draft)
    database_session.commit()

    response = manage_jobs_client.patch(
        status_path(draft.id),
        json={"status": status},
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "job_status_change_not_allowed"
    database_session.expire_all()
    stored = database_session.get(Job, draft.id)
    assert stored is not None
    assert stored.status == JobStatus.DRAFT
    assert stored.published_at is None
