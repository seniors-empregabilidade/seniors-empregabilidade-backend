"""Integration tests for the origin of each row in GET /jobs/{job_id}/applications.

US-20: applicants and automatic matches share one list, ranked by the same
compatibility engine, and each row says where it came from.
"""

from datetime import date
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.models import Application, AppUser, Candidate
from app.db.models.enums import (
    AccountStatus,
    ApplicationStatus,
    AvailabilityStatus,
    UserType,
)
from tests.jobs.conftest import (
    MANAGE_JOBS_OWNER_TOKEN,
    ManageJobsScenario,
    manage_jobs_authorization,
)
from tests.jobs.test_list_job_applicants_router_integration import (
    add_job_skills,
    applicants_path,
    candidate_ids,
    give_resume_skills,
)

pytestmark = pytest.mark.integration

SAFE_PROFILE_FIELDS = {"candidate_id", "full_name", "city", "state"}


def add_candidate(
    session: Session,
    *,
    index: int,
    account_status: AccountStatus = AccountStatus.ACTIVE,
    availability: AvailabilityStatus = AvailabilityStatus.AVAILABLE,
) -> UUID:
    """Add a synthetic candidate who has not applied to any job."""
    user = AppUser(
        email=f"origin-candidate-{index}@candidate.example.invalid",
        identity_subject=None,
        user_type=UserType.CANDIDATE,
        account_status=account_status,
    )
    session.add(user)
    session.flush()
    session.add(
        Candidate(
            id=user.id,
            full_name=f"Origin Candidate {index}",
            cpf=f"{90000000000 + index:011d}",
            birth_date=date(1965, 1, 1),
            phone=f"+55519000{index:05d}",
            city="Porto Alegre",
            state="RS",
            availability=availability,
        )
    )
    session.commit()
    return user.id


def list_job(client: TestClient, job_id: UUID) -> dict[str, Any]:
    response = client.get(
        applicants_path(job_id),
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def row_for(body: dict[str, Any], candidate_id: UUID) -> dict[str, Any]:
    rows: list[dict[str, Any]] = body["applicants"]
    [row] = [row for row in rows if row["profile"]["candidate_id"] == str(candidate_id)]
    return row


def test_applicants_are_marked_as_applications(
    manage_jobs_client: TestClient,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    body = list_job(manage_jobs_client, manage_jobs_scenario.open_job_id)

    assert [row["origin"] for row in body["applicants"]] == [
        "application",
        "application",
    ]
    assert body["automatic_match_count"] == 0
    for row in body["applicants"]:
        assert row["application_id"] is not None
        assert row["status"] == "applied"


def test_compatible_profile_appears_without_applying(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    match_id = add_candidate(database_session, index=1)
    give_resume_skills(
        database_session,
        candidate_id=match_id,
        skill_ids=[manage_jobs_scenario.skill_id],
    )

    body = list_job(manage_jobs_client, manage_jobs_scenario.open_job_id)

    match = row_for(body, match_id)
    assert match["origin"] == "automatic_match"
    assert match["application_id"] is None
    assert match["status"] is None
    assert match["match_score"] is None
    assert match["compatibility_percentage"] == "100.00"
    assert match["is_highlighted"] is True
    assert match["matched_skill_count"] == 1
    assert match["required_skill_count"] == 1
    assert body["total_applicant_count"] == 2
    assert body["automatic_match_count"] == 1
    assert len(body["applicants"]) == 3


def test_application_does_not_inflate_the_percentage(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    extra_skill_ids = add_job_skills(
        database_session, job_id=manage_jobs_scenario.open_job_id, count=2
    )
    same_skills = [manage_jobs_scenario.skill_id, extra_skill_ids[0]]
    match_id = add_candidate(database_session, index=1)
    give_resume_skills(database_session, candidate_id=match_id, skill_ids=same_skills)
    give_resume_skills(
        database_session,
        candidate_id=manage_jobs_scenario.candidate_one_id,
        skill_ids=same_skills,
    )

    body = list_job(manage_jobs_client, manage_jobs_scenario.open_job_id)

    applicant = row_for(body, manage_jobs_scenario.candidate_one_id)
    match = row_for(body, match_id)
    assert applicant["origin"] == "application"
    assert match["origin"] == "automatic_match"
    for field in (
        "compatibility_percentage",
        "is_highlighted",
        "matched_skill_count",
        "required_skill_count",
    ):
        assert applicant[field] == match[field]
    assert applicant["compatibility_percentage"] == "66.67"


def test_equal_percentage_lists_the_applicant_before_the_automatic_match(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    match_id = add_candidate(database_session, index=1)
    for candidate_id in (match_id, manage_jobs_scenario.candidate_two_id):
        give_resume_skills(
            database_session,
            candidate_id=candidate_id,
            skill_ids=[manage_jobs_scenario.skill_id],
        )

    body = list_job(manage_jobs_client, manage_jobs_scenario.open_job_id)

    assert candidate_ids(body["applicants"]) == [
        str(manage_jobs_scenario.candidate_two_id),
        str(match_id),
        str(manage_jobs_scenario.candidate_one_id),
    ]
    assert [row["origin"] for row in body["applicants"]] == [
        "application",
        "automatic_match",
        "application",
    ]


def test_more_compatible_automatic_match_ranks_above_an_applicant(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    extra_skill_ids = add_job_skills(
        database_session, job_id=manage_jobs_scenario.open_job_id, count=1
    )
    match_id = add_candidate(database_session, index=1)
    give_resume_skills(
        database_session,
        candidate_id=match_id,
        skill_ids=[manage_jobs_scenario.skill_id, *extra_skill_ids],
    )
    give_resume_skills(
        database_session,
        candidate_id=manage_jobs_scenario.candidate_one_id,
        skill_ids=[manage_jobs_scenario.skill_id],
    )

    body = list_job(manage_jobs_client, manage_jobs_scenario.open_job_id)

    assert candidate_ids(body["applicants"]) == [
        str(match_id),
        str(manage_jobs_scenario.candidate_one_id),
        str(manage_jobs_scenario.candidate_two_id),
    ]
    assert [row["compatibility_percentage"] for row in body["applicants"]] == [
        "100.00",
        "50.00",
        "0.00",
    ]


def test_profile_below_fifty_percent_is_not_an_automatic_match(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    add_job_skills(database_session, job_id=manage_jobs_scenario.open_job_id, count=2)
    below_id = add_candidate(database_session, index=1)
    give_resume_skills(
        database_session,
        candidate_id=below_id,
        skill_ids=[manage_jobs_scenario.skill_id],
    )

    body = list_job(manage_jobs_client, manage_jobs_scenario.open_job_id)

    assert str(below_id) not in candidate_ids(body["applicants"])
    assert body["automatic_match_count"] == 0


def test_profile_without_required_skills_is_not_an_automatic_match(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    unrelated_skill_ids = add_job_skills(
        database_session, job_id=manage_jobs_scenario.closed_job_id, count=1
    )
    unrelated_id = add_candidate(database_session, index=1)
    give_resume_skills(
        database_session, candidate_id=unrelated_id, skill_ids=unrelated_skill_ids
    )

    body = list_job(manage_jobs_client, manage_jobs_scenario.open_job_id)

    assert str(unrelated_id) not in candidate_ids(body["applicants"])


@pytest.mark.parametrize(
    ("account_status", "availability"),
    [
        (AccountStatus.BLOCKED, AvailabilityStatus.AVAILABLE),
        (AccountStatus.SUSPENDED, AvailabilityStatus.AVAILABLE),
        (AccountStatus.ACTIVE, AvailabilityStatus.UNAVAILABLE),
    ],
    ids=["blocked", "suspended", "unavailable"],
)
def test_inactive_or_unavailable_profile_is_not_an_automatic_match(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
    account_status: AccountStatus,
    availability: AvailabilityStatus,
) -> None:
    hidden_id = add_candidate(
        database_session,
        index=1,
        account_status=account_status,
        availability=availability,
    )
    give_resume_skills(
        database_session,
        candidate_id=hidden_id,
        skill_ids=[manage_jobs_scenario.skill_id],
    )

    body = list_job(manage_jobs_client, manage_jobs_scenario.open_job_id)

    assert str(hidden_id) not in candidate_ids(body["applicants"])
    assert body["automatic_match_count"] == 0


def test_withdrawn_applicant_stays_an_application(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    give_resume_skills(
        database_session,
        candidate_id=manage_jobs_scenario.candidate_one_id,
        skill_ids=[manage_jobs_scenario.skill_id],
    )
    database_session.execute(
        update(Application)
        .where(
            Application.job_id == manage_jobs_scenario.open_job_id,
            Application.candidate_id == manage_jobs_scenario.candidate_one_id,
        )
        .values(status=ApplicationStatus.WITHDRAWN)
    )
    database_session.commit()

    body = list_job(manage_jobs_client, manage_jobs_scenario.open_job_id)

    applicant = row_for(body, manage_jobs_scenario.candidate_one_id)
    assert applicant["origin"] == "application"
    assert applicant["status"] == "withdrawn"
    assert body["automatic_match_count"] == 0


def test_automatic_match_exposes_only_safe_profile_fields(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    match_id = add_candidate(database_session, index=1)
    give_resume_skills(
        database_session,
        candidate_id=match_id,
        skill_ids=[manage_jobs_scenario.skill_id],
    )

    body = list_job(manage_jobs_client, manage_jobs_scenario.open_job_id)

    profile = row_for(body, match_id)["profile"]
    assert set(profile) == SAFE_PROFILE_FIELDS
    assert profile["full_name"] == "Origin Candidate 1"


def test_job_without_required_skills_has_no_automatic_matches(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    match_id = add_candidate(database_session, index=1)
    give_resume_skills(
        database_session,
        candidate_id=match_id,
        skill_ids=[manage_jobs_scenario.skill_id],
    )

    body = list_job(manage_jobs_client, manage_jobs_scenario.closed_job_id)

    assert body["applicants"] == []
    assert body["automatic_match_count"] == 0
