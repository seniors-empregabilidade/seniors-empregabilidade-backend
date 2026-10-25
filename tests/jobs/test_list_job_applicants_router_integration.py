"""Integration tests for GET /api/v1/jobs/{job_id}/applications."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import Application, JobSkill, Resume, ResumeSkill, Skill
from app.db.models.enums import ApplicationStatus, SkillType
from tests.jobs.conftest import (
    MANAGE_JOBS_OTHER_TOKEN,
    MANAGE_JOBS_OWNER_TOKEN,
    ManageJobsScenario,
    manage_jobs_authorization,
)

pytestmark = pytest.mark.integration


def applicants_path(job_id: object) -> str:
    return f"/api/v1/jobs/{job_id}/applications"


def add_job_skills(session: Session, *, job_id: UUID, count: int) -> list[UUID]:
    """Add ``count`` synthetic catalog skills to a job and return their ids."""
    skills = [
        Skill(
            name=f"Manage Jobs Extra Skill {index}",
            normalized_name=f"manage jobs extra skill {index}",
            type=SkillType.HARD,
        )
        for index in range(count)
    ]
    session.add_all(skills)
    session.flush()
    session.add_all(JobSkill(job_id=job_id, skill_id=skill.id) for skill in skills)
    session.commit()
    return [skill.id for skill in skills]


def give_resume_skills(
    session: Session, *, candidate_id: UUID, skill_ids: list[UUID]
) -> None:
    resume = Resume(candidate_id=candidate_id)
    session.add(resume)
    session.flush()
    session.add_all(
        ResumeSkill(resume_id=resume.id, skill_id=skill_id) for skill_id in skill_ids
    )
    session.commit()


def list_applicants(client: TestClient, job_id: UUID) -> list[dict[str, Any]]:
    response = client.get(
        applicants_path(job_id),
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )
    assert response.status_code == 200
    applicants: list[dict[str, Any]] = response.json()["applicants"]
    return applicants


def candidate_ids(applicants: list[dict[str, Any]]) -> list[str]:
    return [str(applicant["profile"]["candidate_id"]) for applicant in applicants]


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
        assert "compatibility_percentage" in applicant
        assert "is_highlighted" in applicant


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


@pytest.mark.parametrize("skilled", ["candidate_one_id", "candidate_two_id"])
def test_applicants_are_ordered_by_compatibility_descending(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
    skilled: str,
) -> None:
    skilled_id = getattr(manage_jobs_scenario, skilled)
    unskilled_id = (
        manage_jobs_scenario.candidate_two_id
        if skilled == "candidate_one_id"
        else manage_jobs_scenario.candidate_one_id
    )
    give_resume_skills(
        database_session,
        candidate_id=skilled_id,
        skill_ids=[manage_jobs_scenario.skill_id],
    )

    applicants = list_applicants(manage_jobs_client, manage_jobs_scenario.open_job_id)

    assert candidate_ids(applicants) == [str(skilled_id), str(unskilled_id)]
    assert [a["compatibility_percentage"] for a in applicants] == ["100.00", "0.00"]
    assert [a["is_highlighted"] for a in applicants] == [True, False]


def test_highlighted_applicants_come_before_those_below_fifty_percent(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    extra_skill_ids = add_job_skills(
        database_session, job_id=manage_jobs_scenario.open_job_id, count=2
    )
    give_resume_skills(
        database_session,
        candidate_id=manage_jobs_scenario.candidate_one_id,
        skill_ids=[manage_jobs_scenario.skill_id],
    )
    give_resume_skills(
        database_session,
        candidate_id=manage_jobs_scenario.candidate_two_id,
        skill_ids=extra_skill_ids,
    )

    applicants = list_applicants(manage_jobs_client, manage_jobs_scenario.open_job_id)

    assert candidate_ids(applicants) == [
        str(manage_jobs_scenario.candidate_two_id),
        str(manage_jobs_scenario.candidate_one_id),
    ]
    assert [a["compatibility_percentage"] for a in applicants] == ["66.67", "33.33"]
    assert [a["is_highlighted"] for a in applicants] == [True, False]
    assert [a["matched_skill_count"] for a in applicants] == [2, 1]
    assert [a["required_skill_count"] for a in applicants] == [3, 3]


def test_exactly_fifty_percent_is_highlighted(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    add_job_skills(database_session, job_id=manage_jobs_scenario.open_job_id, count=1)
    give_resume_skills(
        database_session,
        candidate_id=manage_jobs_scenario.candidate_one_id,
        skill_ids=[manage_jobs_scenario.skill_id],
    )

    applicants = list_applicants(manage_jobs_client, manage_jobs_scenario.open_job_id)

    assert applicants[0]["compatibility_percentage"] == "50.00"
    assert applicants[0]["is_highlighted"] is True
    assert applicants[1]["compatibility_percentage"] == "0.00"
    assert applicants[1]["is_highlighted"] is False


def test_job_without_required_skills_lists_applicants_without_a_score(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    database_session.add(
        Application(
            candidate_id=manage_jobs_scenario.candidate_one_id,
            job_id=manage_jobs_scenario.closed_job_id,
            status=ApplicationStatus.APPLIED,
        )
    )
    database_session.commit()

    response = manage_jobs_client.get(
        applicants_path(manage_jobs_scenario.closed_job_id),
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["full_match_count"] == 0
    [applicant] = body["applicants"]
    assert applicant["compatibility_percentage"] is None
    assert applicant["is_highlighted"] is False
    assert applicant["matched_skill_count"] == 0
    assert applicant["required_skill_count"] == 0
    assert applicant["matched_skills"] == []
    assert applicant["missing_skills"] == []


def test_each_applicant_shows_which_skills_matched_and_which_are_missing(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    extra_skill_ids = add_job_skills(
        database_session, job_id=manage_jobs_scenario.open_job_id, count=2
    )
    give_resume_skills(
        database_session,
        candidate_id=manage_jobs_scenario.candidate_one_id,
        skill_ids=[manage_jobs_scenario.skill_id, extra_skill_ids[1]],
    )

    applicants = list_applicants(manage_jobs_client, manage_jobs_scenario.open_job_id)

    [applicant] = [
        row
        for row in applicants
        if row["profile"]["candidate_id"] == str(manage_jobs_scenario.candidate_one_id)
    ]
    assert applicant["matched_skills"] == [
        {"id": str(extra_skill_ids[1]), "name": "Manage Jobs Extra Skill 1"},
        {"id": str(manage_jobs_scenario.skill_id), "name": "Manage Jobs Python"},
    ]
    assert applicant["missing_skills"] == [
        {"id": str(extra_skill_ids[0]), "name": "Manage Jobs Extra Skill 0"},
    ]
    assert applicant["matched_skill_count"] == len(applicant["matched_skills"])
    assert applicant["required_skill_count"] == 3


@pytest.mark.parametrize("earlier", ["candidate_one_id", "candidate_two_id"])
def test_equal_compatibility_keeps_the_oldest_application_first(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
    earlier: str,
) -> None:
    earlier_id = getattr(manage_jobs_scenario, earlier)
    later_id = (
        manage_jobs_scenario.candidate_two_id
        if earlier == "candidate_one_id"
        else manage_jobs_scenario.candidate_one_id
    )
    applied_at = datetime(2026, 1, 1, tzinfo=UTC)
    for candidate_id, created_at in (
        (earlier_id, applied_at),
        (later_id, applied_at + timedelta(days=1)),
    ):
        database_session.execute(
            update(Application)
            .where(
                Application.job_id == manage_jobs_scenario.open_job_id,
                Application.candidate_id == candidate_id,
            )
            .values(created_at=created_at)
        )
    database_session.commit()

    applicants = list_applicants(manage_jobs_client, manage_jobs_scenario.open_job_id)

    assert [a["compatibility_percentage"] for a in applicants] == ["0.00", "0.00"]
    assert candidate_ids(applicants) == [str(earlier_id), str(later_id)]
