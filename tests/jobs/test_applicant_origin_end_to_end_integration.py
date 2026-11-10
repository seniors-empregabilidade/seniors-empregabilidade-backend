"""US-20-T03: the origin of each professional in a job's list, end to end.

A company publishes a job, professionals pick their skills and their automatic
application preference through the API, the automatic application round runs,
one professional applies, and the company reads the list. Every row must say
where it came from, keep the percentage its skills earn whatever the origin, and
expose no contact or identification data.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, ClassVar
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.applications.services.generate_automatic_applications import (
    generate_automatic_applications_for_job,
)
from app.core.config import get_settings
from app.db.models import AppUser, Candidate, Company
from app.db.models.enums import CompanyStatus, UserType
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from tests.identity.fakes import FakeIdentityProvider

pytestmark = pytest.mark.integration

COMPANY_TOKEN = "origin-flow-company"
OTHER_COMPANY_TOKEN = "origin-flow-other-company"
APPLICANT_TOKEN = "origin-flow-applicant"
AUTOMATIC_TOKEN = "origin-flow-automatic"
OPTED_OUT_TOKEN = "origin-flow-opted-out"
PARTIAL_TOKEN = "origin-flow-partial"
LOW_TOKEN = "origin-flow-low"
CANDIDATE_TOKENS = (
    APPLICANT_TOKEN,
    AUTOMATIC_TOKEN,
    OPTED_OUT_TOKEN,
    PARTIAL_TOKEN,
    LOW_TOKEN,
)
SKILL_NAMES = (
    "Origin Flow Conferência de estoque",
    "Origin Flow Atendimento ao cliente",
    "Origin Flow Planilhas",
)
SAFE_PROFILE_FIELDS = {"candidate_id", "full_name", "city", "state"}


class OriginFlowIdentityProvider(FakeIdentityProvider):
    SUBJECTS_BY_TOKEN: ClassVar[dict[str, str]] = {
        token: f"subject-{token}"
        for token in (COMPANY_TOKEN, OTHER_COMPANY_TOKEN, *CANDIDATE_TOKENS)
    }

    def verify_access_token(self, token: str) -> str:
        try:
            return self.SUBJECTS_BY_TOKEN[token]
        except KeyError:
            raise InvalidAccessTokenError from None


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@dataclass(frozen=True, slots=True)
class OriginFlowCandidate:
    id: UUID
    email: str
    cpf: str
    phone: str
    birth_date: date


@dataclass(frozen=True, slots=True)
class OriginFlowActors:
    candidates: dict[str, OriginFlowCandidate]


@pytest.fixture
def origin_flow_actors(database_session: Session) -> OriginFlowActors:
    subjects = OriginFlowIdentityProvider.SUBJECTS_BY_TOKEN
    companies = [
        _user(subjects[token], UserType.COMPANY)
        for token in (COMPANY_TOKEN, OTHER_COMPANY_TOKEN)
    ]
    candidate_users = {
        token: _user(subjects[token], UserType.CANDIDATE) for token in CANDIDATE_TOKENS
    }
    database_session.add_all([*companies, *candidate_users.values()])
    database_session.flush()
    database_session.add_all(
        [
            _company(company, cnpj, name)
            for company, cnpj, name in zip(
                companies,
                ("21876543000190", "21876543000270"),
                ("Origin Flow Company", "Origin Flow Other Company"),
                strict=True,
            )
        ]
    )
    candidates: dict[str, OriginFlowCandidate] = {}
    for index, (token, user) in enumerate(candidate_users.items(), start=1):
        candidate = Candidate(
            id=user.id,
            full_name=f"Origin Flow Professional {index}",
            cpf=f"{71000000000 + index:011d}",
            birth_date=date(1960, 1, index),
            phone=f"+5551977{index:06d}",
            city="Porto Alegre",
            state="RS",
        )
        database_session.add(candidate)
        candidates[token] = OriginFlowCandidate(
            id=user.id,
            email=user.email,
            cpf=candidate.cpf,
            phone=candidate.phone,
            birth_date=candidate.birth_date,
        )
    # Committing releases the test savepoint, so a service rolling back a failed
    # request keeps these rows; the test transaction still discards them.
    database_session.commit()
    return OriginFlowActors(candidates=candidates)


@pytest.fixture
def origin_flow_client(
    application: FastAPI,
    database_session: Session,
    origin_flow_actors: OriginFlowActors,
) -> Iterator[TestClient]:
    del origin_flow_actors
    provider = OriginFlowIdentityProvider()
    application.dependency_overrides[get_session] = lambda: database_session
    application.dependency_overrides[get_identity_provider] = lambda: provider
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client
    application.dependency_overrides.clear()


def _user(subject: str, user_type: UserType) -> AppUser:
    return AppUser(
        email=f"{subject}@{user_type.value}.example.invalid",
        identity_subject=subject,
        user_type=user_type,
    )


def _company(user: AppUser, cnpj: str, legal_name: str) -> Company:
    return Company(
        id=user.id,
        cnpj=cnpj,
        legal_name=legal_name,
        corporate_email=user.email,
        primary_cnae="4711301",
        status=CompanyStatus.APPROVED,
    )


def publish_job(client: TestClient) -> tuple[str, list[str]]:
    """Publish the job; its skills enter the catalog and are returned with ids."""
    response = client.post(
        "/api/v1/jobs",
        json={
            "title": "Origin Flow Auxiliar de loja",
            "description": "Synthetic job for the origin flow.",
            "skills": [{"name": name, "type": "hard"} for name in SKILL_NAMES],
            "work_mode": "onsite",
            "closing_date": (date.today() + timedelta(days=30)).isoformat(),
        },
        headers=authorization(COMPANY_TOKEN),
    )
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    skill_ids_by_name = {skill["name"]: skill["id"] for skill in body["skills"]}
    return body["id"], [skill_ids_by_name[name] for name in SKILL_NAMES]


def select_skills(client: TestClient, token: str, skill_ids: list[str]) -> None:
    response = client.put(
        "/api/v1/professionals/me/skills",
        json={"skill_ids": skill_ids},
        headers=authorization(token),
    )
    assert response.status_code == 200


def turn_off_automatic_application(client: TestClient, token: str) -> None:
    response = client.patch(
        "/api/v1/professionals/me",
        json={"accepts_automatic_application": False},
        headers=authorization(token),
    )
    assert response.status_code == 200
    assert response.json()["accepts_automatic_application"] is False


def apply(client: TestClient, token: str, job_id: str) -> str:
    response = client.post(
        "/api/v1/applications",
        json={"job_id": job_id},
        headers=authorization(token),
    )
    assert response.status_code == 201
    application_id: str = response.json()["id"]
    return application_id


def run_automatic_applications(session: Session, job_id: str) -> int:
    """Run the round that POST /jobs schedules after its response.

    The scheduled task opens its own session, which cannot see this test's
    uncommitted rows, so the test runs the same service on its session.
    """
    return generate_automatic_applications_for_job(
        session,
        job_id=UUID(job_id),
        threshold_percent=get_settings().automatic_application_threshold_percent,
    )


def list_professionals(
    client: TestClient, job_id: str, token: str = COMPANY_TOKEN
) -> Any:
    return client.get(
        f"/api/v1/jobs/{job_id}/applications", headers=authorization(token)
    )


def rows_by_candidate(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["profile"]["candidate_id"]: row for row in body["applicants"]}


@dataclass(frozen=True, slots=True)
class PublishedJob:
    id: str
    applicant_application_id: str


def prepare_professionals(client: TestClient, session: Session) -> PublishedJob:
    """Every professional reaches the job's list in their own way.

    - applicant: all three skills, applies by themselves;
    - automatic: all three skills, keeps the automatic preference on (default);
    - opted out: all three skills, turns the automatic preference off;
    - partial: two of three skills (66.67%), under the 70% automatic threshold;
    - low: one of three skills (33.33%), under the 50% list threshold.
    """
    job_id, skill_ids = publish_job(client)
    for token in (APPLICANT_TOKEN, AUTOMATIC_TOKEN, OPTED_OUT_TOKEN):
        select_skills(client, token, skill_ids)
    select_skills(client, PARTIAL_TOKEN, skill_ids[:2])
    select_skills(client, LOW_TOKEN, skill_ids[:1])
    for token in (APPLICANT_TOKEN, OPTED_OUT_TOKEN):
        turn_off_automatic_application(client, token)

    applicant_application_id = apply(client, APPLICANT_TOKEN, job_id)
    assert run_automatic_applications(session, job_id) == 1
    return PublishedJob(id=job_id, applicant_application_id=applicant_application_id)


def test_each_professional_is_listed_with_the_origin_of_their_row(
    origin_flow_client: TestClient,
    origin_flow_actors: OriginFlowActors,
    database_session: Session,
) -> None:
    job = prepare_professionals(origin_flow_client, database_session)

    response = list_professionals(origin_flow_client, job.id)

    assert response.status_code == 200
    body = response.json()
    candidates = origin_flow_actors.candidates
    rows = rows_by_candidate(body)
    assert str(candidates[LOW_TOKEN].id) not in rows
    applicant = rows[str(candidates[APPLICANT_TOKEN].id)]
    automatic = rows[str(candidates[AUTOMATIC_TOKEN].id)]
    opted_out = rows[str(candidates[OPTED_OUT_TOKEN].id)]
    partial = rows[str(candidates[PARTIAL_TOKEN].id)]

    assert applicant["origin"] == "application"
    assert applicant["application_type"] == "active"
    assert applicant["application_id"] == job.applicant_application_id
    assert applicant["status"] == "under_review"

    assert automatic["origin"] == "application"
    assert automatic["application_type"] == "automatic"
    assert automatic["application_id"] is not None
    assert automatic["status"] == "under_review"

    for match in (opted_out, partial):
        assert match["origin"] == "automatic_match"
        assert match["application_type"] is None
        assert match["application_id"] is None
        assert match["status"] is None
        assert match["match_score"] is None

    # The same skills earn the same percentage, whoever applied and however.
    for row in (applicant, automatic, opted_out):
        assert row["compatibility_percentage"] == "100.00"
        assert row["is_highlighted"] is True
        assert (row["matched_skill_count"], row["required_skill_count"]) == (3, 3)
    assert partial["compatibility_percentage"] == "66.67"
    assert partial["is_highlighted"] is True

    # Equal percentages list applications, of either type, before matches. Rows
    # created in one test transaction share created_at, so the order between the
    # two applications is not asserted here.
    assert [row["origin"] for row in body["applicants"]] == [
        "application",
        "application",
        "automatic_match",
        "automatic_match",
    ]
    assert body["applicants"][2:] == [opted_out, partial]
    assert body["total_applicant_count"] == 2
    assert body["full_match_count"] == 2
    assert body["automatic_match_count"] == 2


def test_applying_turns_an_automatic_match_into_an_application_with_the_same_percentage(
    origin_flow_client: TestClient,
    origin_flow_actors: OriginFlowActors,
    database_session: Session,
) -> None:
    job = prepare_professionals(origin_flow_client, database_session)
    opted_out_id = str(origin_flow_actors.candidates[OPTED_OUT_TOKEN].id)
    before = rows_by_candidate(list_professionals(origin_flow_client, job.id).json())[
        opted_out_id
    ]

    application_id = apply(origin_flow_client, OPTED_OUT_TOKEN, job.id)

    body = list_professionals(origin_flow_client, job.id).json()
    after = rows_by_candidate(body)[opted_out_id]
    assert before["origin"] == "automatic_match"
    assert after["origin"] == "application"
    assert after["application_type"] == "active"
    assert after["application_id"] == application_id
    for field in (
        "compatibility_percentage",
        "is_highlighted",
        "matched_skill_count",
        "required_skill_count",
        "matched_skills",
        "missing_skills",
        "profile",
    ):
        assert after[field] == before[field]
    assert body["total_applicant_count"] == 3
    assert body["automatic_match_count"] == 1
    # A later round does not apply anyone already in the list a second time.
    assert run_automatic_applications(database_session, job.id) == 0


def test_no_origin_exposes_contact_or_identification_data(
    origin_flow_client: TestClient,
    origin_flow_actors: OriginFlowActors,
    database_session: Session,
) -> None:
    job = prepare_professionals(origin_flow_client, database_session)

    response = list_professionals(origin_flow_client, job.id)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    for row in response.json()["applicants"]:
        assert set(row["profile"]) == SAFE_PROFILE_FIELDS
    for candidate in origin_flow_actors.candidates.values():
        for private in (
            candidate.email,
            candidate.cpf,
            candidate.phone,
            candidate.birth_date.isoformat(),
        ):
            assert private not in response.text


def test_only_the_company_that_owns_the_job_sees_its_professionals(
    origin_flow_client: TestClient,
    origin_flow_actors: OriginFlowActors,
    database_session: Session,
) -> None:
    del origin_flow_actors
    job = prepare_professionals(origin_flow_client, database_session)

    other_company = list_professionals(origin_flow_client, job.id, OTHER_COMPANY_TOKEN)
    professional = list_professionals(origin_flow_client, job.id, APPLICANT_TOKEN)

    assert other_company.status_code == 404
    assert other_company.json()["code"] == "job_not_found"
    assert professional.status_code == 403
