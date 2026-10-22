from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.local_date import to_local_date
from app.db.models import (
    Application,
    AppUser,
    Candidate,
    Company,
    Job,
    JobSkill,
    Skill,
)
from app.db.models.enums import (
    AccountStatus,
    ApplicationStatus,
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

FAR_FUTURE = date(2099, 12, 31)


class DetailIdentityProvider(FakeIdentityProvider):
    def verify_access_token(self, token: str) -> str:
        if token not in {"applied", "fresh", "company"}:
            raise InvalidAccessTokenError
        return f"job-detail-{token}"


@dataclass(frozen=True, slots=True)
class DetailScenario:
    open_id: UUID
    skill_id: UUID
    withdrawn_id: UUID
    closed_id: UUID
    paused_id: UUID
    expired_id: UUID
    late_id: UUID
    closing_today_id: UUID
    draft_id: UUID
    under_review_id: UUID
    blocked_company_job_id: UUID


@pytest.fixture
def scenario(database_session: Session) -> DetailScenario:
    marker = f"jobdetail{uuid4().hex[:10]}"
    today = to_local_date(datetime.now(UTC))

    def user(name: str, kind: UserType, subject: str | None) -> AppUser:
        return AppUser(
            email=f"{marker}-{name}@example.invalid",
            identity_subject=subject,
            user_type=kind,
        )

    applied_user = user("applied", UserType.CANDIDATE, "job-detail-applied")
    fresh_user = user("fresh", UserType.CANDIDATE, "job-detail-fresh")
    company_user = user("company", UserType.COMPANY, "job-detail-company")
    blocked_user = user("blocked", UserType.COMPANY, None)
    blocked_user.account_status = AccountStatus.BLOCKED
    database_session.add_all((applied_user, fresh_user, company_user, blocked_user))
    database_session.flush()

    database_session.add_all(
        Candidate(
            id=candidate.id,
            full_name="Synthetic Job Seeker",
            cpf=f"{uuid4().int % 10**11:011d}",
            birth_date=date(1970, 1, 1),
            phone="+5551999990000",
        )
        for candidate in (applied_user, fresh_user)
    )
    database_session.add_all(
        (
            Company(
                id=company_user.id,
                cnpj=f"{uuid4().int % 10**14:014d}",
                legal_name="Detail Synthetic Ltd.",
                trade_name="Detail Synthetic",
                corporate_email=company_user.email,
                status=CompanyStatus.APPROVED,
            ),
            Company(
                id=blocked_user.id,
                cnpj=f"{uuid4().int % 10**14:014d}",
                legal_name="Blocked Synthetic Ltd.",
                corporate_email=blocked_user.email,
                status=CompanyStatus.APPROVED,
            ),
        )
    )
    skill = Skill(
        name=f"{marker} python",
        normalized_name=f"{marker} python",
        type=SkillType.HARD,
    )
    database_session.add(skill)
    database_session.flush()

    def job(
        title: str,
        *,
        owner: AppUser = company_user,
        status: JobStatus = JobStatus.PUBLISHED,
        closing_date: date = FAR_FUTURE,
    ) -> Job:
        return Job(
            company_id=owner.id,
            title=f"{marker} {title}",
            description="Synthetic job for detail tests.",
            work_mode=WorkMode.REMOTE,
            location="Porto Alegre",
            status=status,
            closing_date=closing_date,
            published_at=datetime.now(UTC),
        )

    jobs = {
        "open": job("Open"),
        "withdrawn": job("Withdrawn"),
        "closed": job("Closed", status=JobStatus.CLOSED),
        "paused": job("Paused", status=JobStatus.PAUSED),
        "expired": job("Expired", status=JobStatus.EXPIRED),
        "late": job("Late", closing_date=today - timedelta(days=1)),
        "closing_today": job("Closing today", closing_date=today),
        "draft": job("Draft", status=JobStatus.DRAFT),
        "under_review": job("Review", status=JobStatus.UNDER_REVIEW),
        "blocked": job("Blocked", owner=blocked_user),
    }
    database_session.add_all(jobs.values())
    database_session.flush()
    database_session.add(JobSkill(job_id=jobs["open"].id, skill_id=skill.id))
    database_session.add_all(
        Application(
            candidate_id=applied_user.id,
            job_id=jobs[name].id,
            status=status,
        )
        for name, status in (
            ("open", ApplicationStatus.UNDER_REVIEW),
            ("withdrawn", ApplicationStatus.WITHDRAWN),
            ("closed", ApplicationStatus.UNDER_REVIEW),
        )
    )
    database_session.flush()

    return DetailScenario(
        open_id=jobs["open"].id,
        skill_id=skill.id,
        withdrawn_id=jobs["withdrawn"].id,
        closed_id=jobs["closed"].id,
        paused_id=jobs["paused"].id,
        expired_id=jobs["expired"].id,
        late_id=jobs["late"].id,
        closing_today_id=jobs["closing_today"].id,
        draft_id=jobs["draft"].id,
        under_review_id=jobs["under_review"].id,
        blocked_company_job_id=jobs["blocked"].id,
    )


@pytest.fixture
def detail_client(
    application: FastAPI, database_session: Session, scenario: DetailScenario
) -> Iterator[TestClient]:
    application.dependency_overrides[get_session] = lambda: database_session
    application.dependency_overrides[get_identity_provider] = DetailIdentityProvider
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client
    application.dependency_overrides.clear()


def read(client: TestClient, job_id: UUID, token: str = "fresh") -> Any:
    return client.get(
        f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"}
    )


def test_returns_the_full_job_for_a_candidate_who_has_not_applied(
    detail_client: TestClient, scenario: DetailScenario
) -> None:
    response = read(detail_client, scenario.open_id)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    body = response.json()
    assert body["id"] == str(scenario.open_id)
    assert body["company_name"] == "Detail Synthetic"
    assert body["description"] == "Synthetic job for detail tests."
    assert body["status"] == "published"
    assert body["closing_date"] == FAR_FUTURE.isoformat()
    assert [skill["id"] for skill in body["skills"]] == [str(scenario.skill_id)]
    assert body["skills"][0]["type"] == "hard"
    assert body["already_applied"] is False
    assert body["is_open"] is True
    assert body["is_expired"] is False
    assert body["is_applicable"] is True


def test_flags_a_job_the_candidate_already_applied_to(
    detail_client: TestClient, scenario: DetailScenario
) -> None:
    body = read(detail_client, scenario.open_id, "applied").json()

    assert body["already_applied"] is True
    assert body["is_open"] is True
    assert body["is_applicable"] is False


def test_a_withdrawn_application_still_counts_as_applied(
    detail_client: TestClient, scenario: DetailScenario
) -> None:
    body = read(detail_client, scenario.withdrawn_id, "applied").json()

    assert body["already_applied"] is True
    assert body["is_applicable"] is False


@pytest.mark.parametrize(
    ("job_name", "status", "expired"),
    [
        ("closed_id", "closed", False),
        ("paused_id", "paused", False),
        ("expired_id", "expired", True),
        ("late_id", "published", True),
    ],
)
def test_a_job_that_is_not_open_is_not_applicable(
    detail_client: TestClient,
    scenario: DetailScenario,
    job_name: str,
    status: str,
    expired: bool,
) -> None:
    response = read(detail_client, getattr(scenario, job_name))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == status
    assert body["is_open"] is False
    assert body["is_expired"] is expired
    assert body["is_applicable"] is False


def test_a_job_closing_today_is_still_open(
    detail_client: TestClient, scenario: DetailScenario
) -> None:
    body = read(detail_client, scenario.closing_today_id).json()

    assert body["is_open"] is True
    assert body["is_expired"] is False
    assert body["is_applicable"] is True


def test_a_closed_job_stays_readable_for_who_applied(
    detail_client: TestClient, scenario: DetailScenario
) -> None:
    body = read(detail_client, scenario.closed_id, "applied").json()

    assert body["already_applied"] is True
    assert body["is_applicable"] is False


@pytest.mark.parametrize(
    "job_name", ["draft_id", "under_review_id", "blocked_company_job_id"]
)
def test_a_job_that_is_not_public_is_not_found(
    detail_client: TestClient, scenario: DetailScenario, job_name: str
) -> None:
    response = read(detail_client, getattr(scenario, job_name))

    assert response.status_code == 404
    assert response.json()["code"] == "job_not_found"


def test_an_unknown_job_is_not_found(
    detail_client: TestClient, scenario: DetailScenario
) -> None:
    assert read(detail_client, uuid4()).status_code == 404


def test_requires_a_candidate(
    detail_client: TestClient, scenario: DetailScenario
) -> None:
    anonymous = detail_client.get(f"/api/v1/jobs/{scenario.open_id}")
    company = read(detail_client, scenario.open_id, "company")

    assert anonymous.status_code == 401
    assert company.status_code == 403
    assert company.json()["code"] == "candidate_required"
