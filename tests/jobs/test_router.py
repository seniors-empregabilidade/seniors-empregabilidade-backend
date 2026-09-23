from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.applications.services.find_similar_jobs import find_similar_jobs
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
MY_JOBS_PATH = "/api/v1/jobs/me"


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
    skill = Skill(
        name="Synthetic Python",
        normalized_name="synthetic python",
        type=SkillType.HARD,
    )
    database_session.add_all((approved, pending, skill))
    database_session.flush()

    return {
        "company_id": company_user.id,
        "pending_company_id": pending_user.id,
        "skill_id": skill.id,
    }


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


def valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Senior Python Developer",
        "description": "Synthetic job description for local tests.",
        "skills": [{"name": "Synthetic Python", "type": SkillType.HARD.value}],
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
        json=valid_payload(closing_date=closing_date.isoformat()),
        headers=authorization("company"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Senior Python Developer"
    assert body["description"] == "Synthetic job description for local tests."
    assert body["skills"] == [
        {
            "id": str(seeded_ids["skill_id"]),
            "name": "Synthetic Python",
            "type": SkillType.HARD.value,
        }
    ]
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
            "skills": [],
            "work_mode": WorkMode.REMOTE.value,
            "closing_date": (date.today() + timedelta(days=30)).isoformat(),
        },
        headers=authorization("company"),
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "validation_error"
    assert "body.title" in response.json()["errors"]
    assert "body.skills" in response.json()["errors"]
    assert seeded_ids["skill_id"]


def test_closing_date_in_the_past_is_rejected(
    jobs_client: TestClient,
    seeded_ids: dict[str, UUID],
) -> None:
    response = jobs_client.post(
        JOBS_PATH,
        json=valid_payload(closing_date=(date.today() - timedelta(days=1)).isoformat()),
        headers=authorization("company"),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "closing_date_in_the_past"
    assert "closing_date" in response.json()["errors"]


def test_a_skill_outside_the_catalog_is_created_with_its_type(
    jobs_client: TestClient,
    database_session: Session,
    seeded_ids: dict[str, UUID],
) -> None:
    response = jobs_client.post(
        JOBS_PATH,
        json=valid_payload(
            skills=[
                {
                    "name": " Liderança  sintética ",
                    "type": SkillType.SOFT.value,
                }
            ]
        ),
        headers=authorization("company"),
    )

    assert response.status_code == 201
    created = response.json()["skills"][0]
    assert created["name"] == "Liderança sintética"
    assert created["type"] == SkillType.SOFT.value
    assert UUID(created["id"]) != seeded_ids["skill_id"]

    skill = database_session.get(Skill, UUID(created["id"]))
    assert skill is not None
    assert skill.normalized_name == "lideranca sintetica"


def test_a_name_already_in_the_catalog_reuses_the_same_skill(
    jobs_client: TestClient,
    seeded_ids: dict[str, UUID],
) -> None:
    response = jobs_client.post(
        JOBS_PATH,
        json=valid_payload(
            skills=[
                {"name": "  sYnThEtIc pYtHoN ", "type": SkillType.SOFT.value},
                {"name": "Synthetic Python", "type": SkillType.HARD.value},
            ]
        ),
        headers=authorization("company"),
    )

    assert response.status_code == 201
    skills = response.json()["skills"]
    assert [skill["id"] for skill in skills] == [str(seeded_ids["skill_id"])]
    assert skills[0]["name"] == "Synthetic Python"
    assert skills[0]["type"] == SkillType.HARD.value


@pytest.mark.parametrize(
    "name",
    ["ß" * 100, "a" * 99 + "\N{HORIZONTAL ELLIPSIS}", "\N{COMBINING ACUTE ACCENT}"],
    ids=["sharp-s", "ellipsis", "accent-only"],
)
def test_a_skill_name_the_catalog_cannot_compare_is_rejected(
    jobs_client: TestClient,
    database_session: Session,
    name: str,
) -> None:
    skills_before = database_session.scalar(select(func.count()).select_from(Skill))
    jobs_before = database_session.scalar(select(func.count()).select_from(Job))

    response = jobs_client.post(
        JOBS_PATH,
        json=valid_payload(skills=[{"name": name, "type": SkillType.HARD.value}]),
        headers=authorization("company"),
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "validation_error"
    assert list(response.json()["errors"]) == ["body.skills.0.name"]
    assert (
        database_session.scalar(select(func.count()).select_from(Skill))
        == skills_before
    )
    assert database_session.scalar(select(func.count()).select_from(Job)) == jobs_before


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
        json=valid_payload(),
        headers=authorization(role) if role else {},
    )

    assert response.status_code == expected


def add_job(
    session: Session,
    *,
    company_id: UUID,
    title: str,
    created_at: datetime,
    status: JobStatus = JobStatus.PUBLISHED,
    skill_ids: tuple[UUID, ...] = (),
) -> Job:
    job = Job(
        company_id=company_id,
        title=title,
        description="Synthetic job stored directly for listing tests.",
        work_mode=WorkMode.HYBRID,
        closing_date=date.today() + timedelta(days=10),
        status=status,
        published_at=created_at if status == JobStatus.PUBLISHED else None,
        created_at=created_at,
    )
    session.add(job)
    session.flush()
    session.add_all(
        JobSkill(job_id=job.id, skill_id=skill_id) for skill_id in skill_ids
    )
    session.flush()
    return job


def count_rows(session: Session, model: type[Job | JobSkill | Skill]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def without_timestamps(job: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in job.items()
        if key not in {"published_at", "created_at"}
    }


def test_a_published_job_is_listed_for_its_company(
    jobs_client: TestClient,
    seeded_ids: dict[str, UUID],
) -> None:
    created = jobs_client.post(
        JOBS_PATH, json=valid_payload(), headers=authorization("company")
    ).json()

    response = jobs_client.get(MY_JOBS_PATH, headers=authorization("company"))

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    listed = response.json()
    assert [job["id"] for job in listed] == [created["id"]]
    assert without_timestamps(listed[0]) == without_timestamps(created)
    for timestamp in ("published_at", "created_at"):
        assert datetime.fromisoformat(listed[0][timestamp]) == datetime.fromisoformat(
            created[timestamp]
        )
    assert listed[0]["company_id"] == str(seeded_ids["company_id"])


def test_a_company_without_jobs_lists_nothing(jobs_client: TestClient) -> None:
    response = jobs_client.get(MY_JOBS_PATH, headers=authorization("company"))

    assert response.status_code == 200
    assert response.json() == []


def test_my_jobs_lists_only_the_company_jobs_newest_first(
    jobs_client: TestClient,
    database_session: Session,
    seeded_ids: dict[str, UUID],
) -> None:
    now = datetime.now(UTC)
    communication = Skill(
        name="Comunicação sintética",
        normalized_name="comunicacao sintetica",
        type=SkillType.SOFT,
    )
    database_session.add(communication)
    database_session.flush()
    add_job(
        database_session,
        company_id=seeded_ids["company_id"],
        title="Older synthetic job",
        created_at=now - timedelta(days=2),
        skill_ids=(seeded_ids["skill_id"], communication.id),
    )
    add_job(
        database_session,
        company_id=seeded_ids["company_id"],
        title="Newer synthetic draft",
        created_at=now - timedelta(days=1),
        status=JobStatus.DRAFT,
    )
    add_job(
        database_session,
        company_id=seeded_ids["pending_company_id"],
        title="Another company's job",
        created_at=now,
    )

    response = jobs_client.get(MY_JOBS_PATH, headers=authorization("company"))

    assert response.status_code == 200
    listed = response.json()
    assert [job["title"] for job in listed] == [
        "Newer synthetic draft",
        "Older synthetic job",
    ]
    assert listed[0]["status"] == JobStatus.DRAFT.value
    assert listed[0]["published_at"] is None
    assert listed[0]["skills"] == []
    assert [skill["name"] for skill in listed[1]["skills"]] == [
        "Comunicação sintética",
        "Synthetic Python",
    ]


@pytest.mark.parametrize(
    ("role", "expected"),
    [(None, 401), ("candidate", 403), ("pending-company", 403)],
)
def test_only_approved_companies_list_their_jobs(
    jobs_client: TestClient,
    role: str | None,
    expected: int,
) -> None:
    response = jobs_client.get(
        MY_JOBS_PATH, headers=authorization(role) if role else {}
    )

    assert response.status_code == expected
    assert response.headers["content-type"].startswith("application/problem+json")


def test_a_failure_while_publishing_leaves_no_partial_job(
    jobs_client: TestClient,
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The company and the catalog exist before the request, so the rollback under
    # test must not reach them. Committing releases only this test's savepoint.
    database_session.commit()
    before = {
        model: count_rows(database_session, model) for model in (Job, JobSkill, Skill)
    }

    def lose_the_connection() -> None:
        raise OperationalError("COMMIT", {}, Exception("synthetic connection loss"))

    monkeypatch.setattr(database_session, "commit", lose_the_connection)
    response = jobs_client.post(
        JOBS_PATH,
        json=valid_payload(
            skills=[
                {"name": "Synthetic Python", "type": SkillType.HARD.value},
                {"name": "Habilidade sintética inédita", "type": SkillType.SOFT.value},
            ]
        ),
        headers=authorization("company"),
    )
    monkeypatch.undo()

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "internal_error"
    after = {
        model: count_rows(database_session, model) for model in (Job, JobSkill, Skill)
    }
    assert after == before
    listed = jobs_client.get(MY_JOBS_PATH, headers=authorization("company"))
    assert listed.json() == []


def test_published_skills_are_comparable_by_catalog_identity(
    jobs_client: TestClient,
    database_session: Session,
) -> None:
    first = jobs_client.post(
        JOBS_PATH,
        json=valid_payload(
            title="Synthetic team lead",
            skills=[
                {"name": "Gestão de equipes sintética", "type": SkillType.SOFT.value}
            ],
        ),
        headers=authorization("company"),
    ).json()
    second = jobs_client.post(
        JOBS_PATH,
        json=valid_payload(
            title="Synthetic operations lead",
            skills=[
                {"name": "  GESTAO DE EQUIPES sintetica ", "type": SkillType.HARD.value}
            ],
        ),
        headers=authorization("company"),
    ).json()

    assert first["skills"] == second["skills"]
    assert first["skills"][0]["type"] == SkillType.SOFT.value
    similar = find_similar_jobs(
        database_session, job_id=UUID(first["id"]), candidate_id=uuid4()
    )
    assert [job.id for job in similar] == [UUID(second["id"])]
