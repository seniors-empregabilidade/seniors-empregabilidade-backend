from collections.abc import Iterator
from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AppUser, Company, Job, JobSkill, Skill
from app.db.models.enums import (
    CompanyStatus,
    JobStatus,
    SkillType,
    UserType,
    WorkMode,
)
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from tests.identity.fakes import FakeIdentityProvider

pytestmark = pytest.mark.integration

JOBS_PATH = "/api/v1/jobs"


class JobIdentityProvider(FakeIdentityProvider):
    def verify_access_token(self, token: str) -> str:
        if token not in {"company", "pending-company", "candidate"}:
            raise InvalidAccessTokenError
        return f"job-{token}"


@pytest.fixture
def identity_provider() -> JobIdentityProvider:
    return JobIdentityProvider()


@pytest.fixture
def seeded_ids(database_session: Session) -> dict[str, UUID]:
    company_user = AppUser(
        email="publisher@company.example.invalid",
        identity_subject="job-company",
        user_type=UserType.COMPANY,
    )
    pending_user = AppUser(
        email="pending@company.example.invalid",
        identity_subject="job-pending-company",
        user_type=UserType.COMPANY,
    )
    candidate_user = AppUser(
        email="viewer@candidate.example.invalid",
        identity_subject="job-candidate",
        user_type=UserType.CANDIDATE,
    )
    database_session.add_all((company_user, pending_user, candidate_user))
    database_session.flush()

    approved = Company(
        id=company_user.id,
        cnpj="11444777000161",
        legal_name="Synthetic Publisher Company",
        corporate_email=company_user.email,
        primary_cnae="6201501",
        status=CompanyStatus.APPROVED,
    )
    pending = Company(
        id=pending_user.id,
        cnpj="60746948000112",
        legal_name="Synthetic Pending Company",
        corporate_email=pending_user.email,
        primary_cnae="6201501",
        status=CompanyStatus.PENDING,
    )
    skill = Skill(name="Python", type=SkillType.HARD)
    database_session.add_all((approved, pending, skill))
    database_session.flush()

    return {"company_id": company_user.id, "skill_id": skill.id}


@pytest.fixture
def jobs_client(
    application: FastAPI,
    database_session: Session,
    identity_provider: JobIdentityProvider,
    seeded_ids: dict[str, UUID],
) -> Iterator[TestClient]:
    assert seeded_ids
    application.dependency_overrides[get_session] = lambda: database_session
    application.dependency_overrides[get_identity_provider] = lambda: identity_provider
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client
    application.dependency_overrides.clear()


def authorization(role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {role}"}


def valid_payload(skill_id: UUID, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Senior Python Developer",
        "description": "Synthetic job description for local tests.",
        "skill_ids": [str(skill_id)],
        "work_mode": WorkMode.REMOTE.value,
        "closing_date": (date.today() + timedelta(days=30)).isoformat(),
    }
    payload.update(overrides)
    return payload


def test_approved_company_creates_an_open_job(
    jobs_client: TestClient,
    database_session: Session,
    seeded_ids: dict[str, UUID],
) -> None:
    closing_date = date.today() + timedelta(days=30)
    response = jobs_client.post(
        JOBS_PATH,
        json=valid_payload(
            seeded_ids["skill_id"], closing_date=closing_date.isoformat()
        ),
        headers=authorization("company"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Senior Python Developer"
    assert body["description"] == "Synthetic job description for local tests."
    assert body["skill_ids"] == [str(seeded_ids["skill_id"])]
    assert body["work_mode"] == WorkMode.REMOTE.value
    assert body["closing_date"] == closing_date.isoformat()
    assert body["status"] == JobStatus.PUBLISHED.value
    assert body["company_id"] == str(seeded_ids["company_id"])

    job = database_session.scalar(select(Job).where(Job.id == UUID(body["id"])))
    assert job is not None
    assert job.company_id == seeded_ids["company_id"]
    assert job.status == JobStatus.PUBLISHED
    assert job.work_mode == WorkMode.REMOTE
    assert job.closing_date == closing_date
    linked_skill_ids = database_session.scalars(
        select(JobSkill.skill_id).where(JobSkill.job_id == job.id)
    ).all()
    assert linked_skill_ids == [seeded_ids["skill_id"]]


def test_title_and_skills_are_required(
    jobs_client: TestClient,
    seeded_ids: dict[str, UUID],
) -> None:
    response = jobs_client.post(
        JOBS_PATH,
        json={
            "description": "Missing required fields.",
            "skill_ids": [],
            "work_mode": WorkMode.REMOTE.value,
            "closing_date": (date.today() + timedelta(days=30)).isoformat(),
        },
        headers=authorization("company"),
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "validation_error"
    assert "body.title" in response.json()["errors"]
    assert "body.skill_ids" in response.json()["errors"]
    assert seeded_ids["skill_id"]


def test_closing_date_in_the_past_is_rejected(
    jobs_client: TestClient,
    seeded_ids: dict[str, UUID],
) -> None:
    response = jobs_client.post(
        JOBS_PATH,
        json=valid_payload(
            seeded_ids["skill_id"],
            closing_date=(date.today() - timedelta(days=1)).isoformat(),
        ),
        headers=authorization("company"),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "closing_date_in_the_past"
    assert "closing_date" in response.json()["errors"]


def test_unknown_skill_ids_are_rejected(
    jobs_client: TestClient,
    seeded_ids: dict[str, UUID],
) -> None:
    response = jobs_client.post(
        JOBS_PATH,
        json=valid_payload(seeded_ids["skill_id"], skill_ids=[str(uuid4())]),
        headers=authorization("company"),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "unknown_skills"
    assert "skill_ids" in response.json()["errors"]


@pytest.mark.parametrize(
    ("role", "expected"),
    [(None, 401), ("candidate", 403), ("pending-company", 403)],
)
def test_only_approved_companies_can_publish(
    jobs_client: TestClient,
    seeded_ids: dict[str, UUID],
    role: str | None,
    expected: int,
) -> None:
    response = jobs_client.post(
        JOBS_PATH,
        json=valid_payload(seeded_ids["skill_id"]),
        headers=authorization(role) if role else {},
    )

    assert response.status_code == expected
