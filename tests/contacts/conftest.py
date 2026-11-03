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
    Resume,
    ResumeSkill,
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

OWNER_TOKEN = "contacts-owner"
OTHER_COMPANY_TOKEN = "contacts-other-company"
CANDIDATE_TOKEN = "contacts-candidate"

APPLICANT_EMAIL = "contacts-applicant@candidate.example.invalid"
APPLICANT_CPF = "52998224725"
APPLICANT_PHONE = "+5551999990101"
APPLICANT_NAME = "Contacts Applicant"
COMPANY_TRADE_NAME = "Contacts Trade Name"
JOB_TITLE = "Contacts Open Role"


class ContactsIdentityProvider(FakeIdentityProvider):
    SUBJECTS_BY_TOKEN: ClassVar[dict[str, str]] = {
        OWNER_TOKEN: "subject-contacts-owner",
        OTHER_COMPANY_TOKEN: "subject-contacts-other-company",
        CANDIDATE_TOKEN: "subject-contacts-candidate",
    }

    def verify_access_token(self, token: str) -> str:
        try:
            return self.SUBJECTS_BY_TOKEN[token]
        except KeyError:
            raise InvalidAccessTokenError from None


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def contacts_client(
    application: FastAPI, database_session: Session
) -> Iterator[TestClient]:
    provider = ContactsIdentityProvider()
    application.dependency_overrides[get_session] = lambda: database_session
    application.dependency_overrides[get_identity_provider] = lambda: provider
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client
    application.dependency_overrides.clear()


@dataclass(frozen=True, slots=True)
class ContactsScenario:
    owner_company_id: UUID
    other_company_id: UUID
    job_id: UUID
    other_company_job_id: UUID
    applicant_id: UUID
    automatic_match_id: UUID
    unlisted_id: UUID
    blocked_applicant_id: UUID


def _user(
    session: Session,
    *,
    email: str,
    user_type: UserType,
    token: str | None = None,
    account_status: AccountStatus = AccountStatus.ACTIVE,
) -> AppUser:
    user = AppUser(
        email=email,
        identity_subject=(
            ContactsIdentityProvider.SUBJECTS_BY_TOKEN[token] if token else None
        ),
        user_type=user_type,
        account_status=account_status,
    )
    session.add(user)
    session.flush()
    return user


def _candidate(
    session: Session,
    user: AppUser,
    *,
    full_name: str,
    cpf: str,
    phone: str,
) -> Candidate:
    candidate = Candidate(
        id=user.id,
        full_name=full_name,
        cpf=cpf,
        birth_date=date(1968, 1, 1),
        phone=phone,
        city="Porto Alegre",
        state="RS",
    )
    session.add(candidate)
    session.flush()
    return candidate


def _job(session: Session, *, company_id: UUID, title: str) -> Job:
    job = Job(
        company_id=company_id,
        title=title,
        description="Synthetic role for contact tests.",
        work_mode=WorkMode.REMOTE,
        status=JobStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        closing_date=date.today() + timedelta(days=30),
    )
    session.add(job)
    session.flush()
    return job


@pytest.fixture
def contacts_scenario(database_session: Session) -> ContactsScenario:
    session = database_session
    owner_user = _user(
        session,
        email="contacts-owner@company.example.invalid",
        user_type=UserType.COMPANY,
        token=OWNER_TOKEN,
    )
    other_user = _user(
        session,
        email="contacts-other@company.example.invalid",
        user_type=UserType.COMPANY,
        token=OTHER_COMPANY_TOKEN,
    )
    session.add_all(
        (
            Company(
                id=owner_user.id,
                cnpj="11444777000161",
                legal_name="Contacts Owner Legal Name",
                trade_name=COMPANY_TRADE_NAME,
                corporate_email=owner_user.email,
                status=CompanyStatus.APPROVED,
            ),
            Company(
                id=other_user.id,
                cnpj="60746948000112",
                legal_name="Contacts Other Legal Name",
                corporate_email=other_user.email,
                status=CompanyStatus.APPROVED,
            ),
        )
    )
    session.flush()

    applicant = _candidate(
        session,
        _user(session, email=APPLICANT_EMAIL, user_type=UserType.CANDIDATE),
        full_name=APPLICANT_NAME,
        cpf=APPLICANT_CPF,
        phone=APPLICANT_PHONE,
    )
    automatic_match = _candidate(
        session,
        _user(
            session,
            email="contacts-match@candidate.example.invalid",
            user_type=UserType.CANDIDATE,
            token=CANDIDATE_TOKEN,
        ),
        full_name="Contacts Automatic Match",
        cpf="11144477735",
        phone="+5551999990102",
    )
    unlisted = _candidate(
        session,
        _user(
            session,
            email="contacts-unlisted@candidate.example.invalid",
            user_type=UserType.CANDIDATE,
        ),
        full_name="Contacts Unlisted",
        cpf="22255588846",
        phone="+5551999990103",
    )
    blocked_applicant = _candidate(
        session,
        _user(
            session,
            email="contacts-blocked@candidate.example.invalid",
            user_type=UserType.CANDIDATE,
            account_status=AccountStatus.BLOCKED,
        ),
        full_name="Contacts Blocked Applicant",
        cpf="39053344705",
        phone="+5551999990104",
    )

    skill = Skill(
        name="Contacts Python",
        normalized_name="contacts python",
        type=SkillType.HARD,
    )
    session.add(skill)
    job = _job(session, company_id=owner_user.id, title=JOB_TITLE)
    other_company_job = _job(
        session, company_id=other_user.id, title="Contacts Foreign Role"
    )
    session.add(JobSkill(job_id=job.id, skill_id=skill.id))
    session.add_all(
        Application(
            candidate_id=candidate.id,
            job_id=job.id,
            status=ApplicationStatus.APPLIED,
        )
        for candidate in (applicant, blocked_applicant)
    )
    resume = Resume(candidate_id=automatic_match.id)
    session.add(resume)
    session.flush()
    session.add(ResumeSkill(resume_id=resume.id, skill_id=skill.id))
    session.commit()

    return ContactsScenario(
        owner_company_id=owner_user.id,
        other_company_id=other_user.id,
        job_id=job.id,
        other_company_job_id=other_company_job.id,
        applicant_id=applicant.id,
        automatic_match_id=automatic_match.id,
        unlisted_id=unlisted.id,
        blocked_applicant_id=blocked_applicant.id,
    )
