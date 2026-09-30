"""Integration tests for GET /api/v1/jobs/{job_id}/applications."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Application, Resume, ResumeSkill
from tests.jobs.conftest import (
    MANAGE_JOBS_OTHER_TOKEN,
    MANAGE_JOBS_OWNER_TOKEN,
    ManageJobsScenario,
    manage_jobs_authorization,
)

pytestmark = pytest.mark.integration


def applicants_path(job_id: object) -> str:
    return f"/api/v1/jobs/{job_id}/applications"


def test_owner_can_list_applicants_for_their_job(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    response = manage_jobs_client.get(
        applicants_path(manage_jobs_scenario.open_job_id),
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == str(manage_jobs_scenario.open_job_id)
    assert body["total_applicant_count"] == 2
    assert len(body["applicants"]) == 2


def test_response_includes_match_counts(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    response = manage_jobs_client.get(
        applicants_path(manage_jobs_scenario.open_job_id),
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 200
    # required_skill_count must equal the number of job skills (1 in the fixture)
    for applicant in response.json()["applicants"]:
        assert applicant["required_skill_count"] == 1
        assert "matched_skill_count" in applicant
        assert "match_score" in applicant


def test_response_includes_safe_profile_fields_only(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    response = manage_jobs_client.get(
        applicants_path(manage_jobs_scenario.open_job_id),
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 200
    for applicant in response.json()["applicants"]:
        profile = applicant["profile"]
        # Only safe profile fields
        assert "candidate_id" in profile
        assert "full_name" in profile
        assert "city" in profile
        assert "state" in profile
        # Sensitive fields must not be present
        assert "cpf" not in profile
        assert "birth_date" not in profile
        assert "phone" not in profile
        assert "email" not in profile


def test_full_match_count_reflects_candidates_meeting_all_requirements(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    # Give candidate_one (already applied) the required skill via a resume
    candidate_one_app = (
        database_session.execute(
            select(Application).where(
                Application.job_id == manage_jobs_scenario.open_job_id
            )
        )
        .scalars()
        .first()
    )
    assert candidate_one_app is not None

    resume = Resume(candidate_id=candidate_one_app.candidate_id)
    database_session.add(resume)
    database_session.flush()
    database_session.add(
        ResumeSkill(resume_id=resume.id, skill_id=manage_jobs_scenario.skill_id)
    )
    database_session.commit()

    response = manage_jobs_client.get(
        applicants_path(manage_jobs_scenario.open_job_id),
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 200
    body = response.json()
    # At least one candidate now has full match (matched == required)
    assert body["full_match_count"] >= 1


def test_nonexistent_job_returns_404(
    manage_jobs_client: TestClient,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    response = manage_jobs_client.get(
        applicants_path(uuid4()),
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "job_not_found"


def test_another_companys_job_returns_404(
    manage_jobs_client: TestClient,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    response = manage_jobs_client.get(
        applicants_path(manage_jobs_scenario.other_company_job_id),
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "job_not_found"


def test_another_company_token_cannot_list_owners_applicants(
    manage_jobs_client: TestClient,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    response = manage_jobs_client.get(
        applicants_path(manage_jobs_scenario.open_job_id),
        headers=manage_jobs_authorization(MANAGE_JOBS_OTHER_TOKEN),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "job_not_found"


def test_unauthenticated_request_is_rejected(
    manage_jobs_client: TestClient,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    response = manage_jobs_client.get(applicants_path(manage_jobs_scenario.open_job_id))

    assert response.status_code == 401


def test_job_with_no_applicants_returns_empty_list(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    response = manage_jobs_client.get(
        applicants_path(manage_jobs_scenario.closed_job_id),
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_applicant_count"] == 0
    assert body["applicants"] == []
    assert body["full_match_count"] == 0
