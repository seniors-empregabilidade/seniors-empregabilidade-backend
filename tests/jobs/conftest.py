from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import ClassVar
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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

MANAGE_JOBS_OWNER_TOKEN = "manage-jobs-owner"
MANAGE_JOBS_OTHER_TOKEN = "manage-jobs-other"


class ManageJobsIdentityProvider(FakeIdentityProvider):
    _SUBJECTS_BY_TOKEN: ClassVar[dict[str, str]] = {
        MANAGE_JOBS_OWNER_TOKEN: "subject-manage-jobs-owner",
        MANAGE_JOBS_OTHER_TOKEN: "subject-manage-jobs-other",
    }

    def verify_access_token(self, token: str) -> str:
        try:
            return self._SUBJECTS_BY_TOKEN[token]
        except KeyError:
            raise InvalidAccessTokenError from None


@pytest.fixture
def manage_jobs_identity_provider() -> ManageJobsIdentityProvider:
    return ManageJobsIdentityProvider()


@pytest.fixture
def manage_jobs_client(
    application: FastAPI,
    database_session: Session,
    manage_jobs_identity_provider: ManageJobsIdentityProvider,
) -> Iterator[TestClient]:
    application.dependency_overrides[get_session] = lambda: database_session
    application.dependency_overrides[get_identity_provider] = lambda: (
        manage_jobs_identity_provider
    )
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client
    application.dependency_overrides.clear()


def manage_jobs_authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@dataclass(frozen=True, slots=True)
class ManageJobsScenario:
    owner_company_id: UUID
    other_company_id: UUID
    open_job_id: UUID
    closed_job_id: UUID
    other_company_job_id: UUID
    skill_id: UUID


@pytest.fixture
def manage_jobs_scenario(database_session: Session) -> ManageJobsScenario:
    now = datetime.now(UTC)
    far_future = date.today() + timedelta(days=30)

    owner_user = AppUser(
        email="manage-jobs-owner@company.example.invalid",
        identity_subject=ManageJobsIdentityProvider._SUBJECTS_BY_TOKEN[
            MANAGE_JOBS_OWNER_TOKEN
        ],
        user_type=UserType.COMPANY,
    )
    other_user = AppUser(
        email="manage-jobs-other@company.example.invalid",
        identity_subject=ManageJobsIdentityProvider._SUBJECTS_BY_TOKEN[
            MANAGE_JOBS_OTHER_TOKEN
        ],
        user_type=UserType.COMPANY,
    )
    candidate_one_user = AppUser(
        email="manage-jobs-candidate-one@candidate.example.invalid",
        identity_subject=None,
        user_type=UserType.CANDIDATE,
    )
    candidate_two_user = AppUser(
        email="manage-jobs-candidate-two@candidate.example.invalid",
        identity_subject=None,
        user_type=UserType.CANDIDATE,
    )
    database_session.add_all(
        (owner_user, other_user, candidate_one_user, candidate_two_user)
    )
    database_session.flush()

    owner_company = Company(
        id=owner_user.id,
        cnpj="11444777000161",
        legal_name="Manage Jobs Owner Company",
        corporate_email=owner_user.email,
        primary_cnae="6201501",
        status=CompanyStatus.APPROVED,
    )
    other_company = Company(
        id=other_user.id,
        cnpj="60746948000112",
        legal_name="Manage Jobs Other Company",
        corporate_email=other_user.email,
        primary_cnae="6201501",
        status=CompanyStatus.APPROVED,
    )
    candidate_one = Candidate(
        id=candidate_one_user.id,
        full_name="Manage Jobs Candidate One",
        cpf="11144477735",
        birth_date=date(1970, 1, 1),
        phone="+5551999990000",
    )
    candidate_two = Candidate(
        id=candidate_two_user.id,
        full_name="Manage Jobs Candidate Two",
        cpf="22255588846",
        birth_date=date(1971, 1, 1),
        phone="+5551999990001",
    )
    skill = Skill(
        name="Manage Jobs Python",
        normalized_name="manage jobs python",
        type=SkillType.HARD,
    )
    database_session.add_all(
        (owner_company, other_company, candidate_one, candidate_two, skill)
    )
    database_session.flush()

    open_job = Job(
        company_id=owner_company.id,
        title="Manage Jobs Open Role",
        description="Synthetic open role for manage-jobs tests.",
        work_mode=WorkMode.REMOTE,
        status=JobStatus.PUBLISHED,
        published_at=now,
        closing_date=far_future,
    )
    closed_job = Job(
        company_id=owner_company.id,
        title="Manage Jobs Closed Role",
        description="Synthetic closed role for manage-jobs tests.",
        work_mode=WorkMode.ONSITE,
        status=JobStatus.CLOSED,
        published_at=now,
        closing_date=far_future,
    )
    other_company_job = Job(
        company_id=other_company.id,
        title="Manage Jobs Foreign Role",
        description="Synthetic role owned by another company.",
        work_mode=WorkMode.REMOTE,
        status=JobStatus.PUBLISHED,
        published_at=now,
        closing_date=far_future,
    )
    database_session.add_all((open_job, closed_job, other_company_job))
    database_session.flush()

    database_session.add(JobSkill(job_id=open_job.id, skill_id=skill.id))
    database_session.add_all(
        (
            Application(
                candidate_id=candidate_one.id,
                job_id=open_job.id,
                status=ApplicationStatus.APPLIED,
            ),
            Application(
                candidate_id=candidate_two.id,
                job_id=open_job.id,
                status=ApplicationStatus.APPLIED,
            ),
        )
    )
    database_session.flush()

    return ManageJobsScenario(
        owner_company_id=owner_company.id,
        other_company_id=other_company.id,
        open_job_id=open_job.id,
        closed_job_id=closed_job.id,
        other_company_job_id=other_company_job.id,
        skill_id=skill.id,
    )
