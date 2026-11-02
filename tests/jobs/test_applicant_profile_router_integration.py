"""Company access to the profile attached to a job application."""

from datetime import date
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Application,
    Certification,
    Company,
    Education,
    Experience,
    Resume,
    ResumeSkill,
)
from app.db.models.enums import CompanyStatus
from tests.jobs.conftest import (
    MANAGE_JOBS_CANDIDATE_TOKEN,
    MANAGE_JOBS_OTHER_TOKEN,
    MANAGE_JOBS_OWNER_TOKEN,
    ManageJobsScenario,
    manage_jobs_authorization,
)

pytestmark = pytest.mark.integration


def profile_path(application_id: object) -> str:
    return f"/api/v1/applications/{application_id}/profile"


@pytest.fixture
def applicant_id(
    database_session: Session, manage_jobs_scenario: ManageJobsScenario
) -> UUID:
    identifier = database_session.scalar(
        select(Application.id).where(
            Application.job_id == manage_jobs_scenario.open_job_id,
            Application.candidate_id == manage_jobs_scenario.candidate_one_id,
        )
    )
    assert identifier is not None
    return identifier


def test_company_reads_only_professional_fields_of_its_applicant(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
    applicant_id: UUID,
) -> None:
    resume = Resume(
        candidate_id=manage_jobs_scenario.candidate_one_id,
        summary="Synthetic professional summary.",
    )
    database_session.add(resume)
    database_session.flush()
    database_session.add_all(
        (
            Experience(
                resume_id=resume.id,
                role="Operations analyst",
                company_name="Synthetic company",
                start_date=date(2020, 1, 1),
                description="Synthetic experience.",
            ),
            Education(
                resume_id=resume.id,
                institution="Synthetic institution",
                degree="Degree",
                field="Operations",
            ),
            Certification(
                resume_id=resume.id,
                name="Synthetic certification",
                issuer="Synthetic issuer",
                issued_date=date(2021, 1, 1),
            ),
            ResumeSkill(resume_id=resume.id, skill_id=manage_jobs_scenario.skill_id),
        )
    )
    database_session.commit()

    response = manage_jobs_client.get(
        profile_path(applicant_id),
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["application_id"] == str(applicant_id)
    assert body["candidate_id"] == str(manage_jobs_scenario.candidate_one_id)
    assert body["summary"] == "Synthetic professional summary."
    assert body["experiences"][0]["role"] == "Operations analyst"
    assert body["education"][0]["institution"] == "Synthetic institution"
    assert body["certifications"][0]["name"] == "Synthetic certification"
    assert set(body["certifications"][0]) == {
        "id",
        "name",
        "issuer",
        "issued_date",
        "expiration_date",
    }
    assert body["skills"][0]["id"] == str(manage_jobs_scenario.skill_id)
    assert set(body) == {
        "application_id",
        "candidate_id",
        "full_name",
        "city",
        "state",
        "summary",
        "experiences",
        "education",
        "certifications",
        "skills",
    }


def test_applicant_without_resume_has_an_empty_professional_profile(
    manage_jobs_client: TestClient, applicant_id: UUID
) -> None:
    response = manage_jobs_client.get(
        profile_path(applicant_id),
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] is None
    for field in ("experiences", "education", "certifications", "skills"):
        assert body[field] == []


def test_other_company_cannot_read_applicant_profile(
    manage_jobs_client: TestClient, applicant_id: UUID
) -> None:
    response = manage_jobs_client.get(
        profile_path(applicant_id),
        headers=manage_jobs_authorization(MANAGE_JOBS_OTHER_TOKEN),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "application_not_found"
    assert response.headers["content-type"] == "application/problem+json"


def test_missing_application_does_not_reveal_profile(
    manage_jobs_client: TestClient, manage_jobs_scenario: ManageJobsScenario
) -> None:
    response = manage_jobs_client.get(
        profile_path(uuid4()),
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "application_not_found"


@pytest.mark.parametrize("token", [None, MANAGE_JOBS_CANDIDATE_TOKEN])
def test_profile_requires_an_approved_company(
    manage_jobs_client: TestClient, applicant_id: UUID, token: str | None
) -> None:
    response = manage_jobs_client.get(
        profile_path(applicant_id),
        headers=manage_jobs_authorization(token) if token else {},
    )

    assert response.status_code == (403 if token else 401)


def test_pending_company_cannot_read_applicant_profile(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
    applicant_id: UUID,
) -> None:
    company = database_session.get(Company, manage_jobs_scenario.owner_company_id)
    assert company is not None
    company.status = CompanyStatus.PENDING
    database_session.commit()

    response = manage_jobs_client.get(
        profile_path(applicant_id),
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 403
