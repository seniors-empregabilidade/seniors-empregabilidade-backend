from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from typing import ClassVar
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import AppUser, Candidate, Company, Resume
from app.db.models.enums import AccountStatus, CompanyStatus, UserType
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from tests.identity.fakes import FakeIdentityProvider

ADMIN_TOKEN = "account-management-admin"
CANDIDATE_TOKEN = "account-management-candidate"
BLOCKED_TOKEN = "account-management-blocked"


class AccountManagementIdentityProvider(FakeIdentityProvider):
    SUBJECTS_BY_TOKEN: ClassVar[dict[str, str]] = {
        ADMIN_TOKEN: "subject-account-management-admin",
        CANDIDATE_TOKEN: "subject-account-management-candidate",
        BLOCKED_TOKEN: "subject-account-management-blocked",
    }

    def verify_access_token(self, token: str) -> str:
        try:
            return self.SUBJECTS_BY_TOKEN[token]
        except KeyError:
            raise InvalidAccessTokenError from None


@pytest.fixture
def account_management_client(
    application: FastAPI, database_session: Session
) -> Iterator[TestClient]:
    provider = AccountManagementIdentityProvider()
    application.dependency_overrides[get_session] = lambda: database_session
    application.dependency_overrides[get_identity_provider] = lambda: provider
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client
    application.dependency_overrides.clear()


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@dataclass(frozen=True, slots=True)
class AccountManagementScenario:
    administrator_id: UUID
    complete_candidate_id: UUID
    partial_candidate_id: UUID
    no_resume_candidate_id: UUID
    blocked_candidate_id: UUID
    pending_company_id: UUID
    approved_company_id: UUID


def _user(
    email: str,
    user_type: UserType,
    *,
    subject: str | None = None,
    account_status: AccountStatus = AccountStatus.ACTIVE,
) -> AppUser:
    return AppUser(
        email=email,
        identity_subject=subject,
        user_type=user_type,
        account_status=account_status,
    )


def _candidate(user: AppUser, name: str, cpf: str) -> Candidate:
    return Candidate(
        id=user.id,
        full_name=name,
        cpf=cpf,
        birth_date=date(1970, 1, 1),
        phone="+5551999990000",
    )


def _company(user: AppUser, name: str, cnpj: str, status: CompanyStatus) -> Company:
    return Company(
        id=user.id,
        cnpj=cnpj,
        legal_name=name,
        corporate_email=user.email,
        status=status,
    )


@pytest.fixture
def account_management_scenario(database_session: Session) -> AccountManagementScenario:
    subjects = AccountManagementIdentityProvider.SUBJECTS_BY_TOKEN
    administrator = _user(
        "account-admin@seniors.example.invalid",
        UserType.ADMINISTRATOR,
        subject=subjects[ADMIN_TOKEN],
    )
    complete = _user(
        "account-complete@candidate.example.invalid",
        UserType.CANDIDATE,
        subject=subjects[CANDIDATE_TOKEN],
    )
    partial = _user("account-partial@candidate.example.invalid", UserType.CANDIDATE)
    no_resume = _user("account-bare@candidate.example.invalid", UserType.CANDIDATE)
    blocked = _user(
        "account-blocked@candidate.example.invalid",
        UserType.CANDIDATE,
        subject=subjects[BLOCKED_TOKEN],
        account_status=AccountStatus.BLOCKED,
    )
    pending_company = _user("account-pending@company.example.invalid", UserType.COMPANY)
    approved_company = _user(
        "account-approved@company.example.invalid", UserType.COMPANY
    )
    database_session.add_all(
        (
            administrator,
            complete,
            partial,
            no_resume,
            blocked,
            pending_company,
            approved_company,
        )
    )
    database_session.flush()

    candidates = (
        _candidate(complete, "Account Complete Candidate", "90000000001"),
        _candidate(partial, "Account Partial Candidate", "90000000002"),
        _candidate(no_resume, "Account Bare Candidate", "90000000003"),
        _candidate(blocked, "Account Blocked Candidate", "90000000004"),
    )
    database_session.add_all(
        (
            *candidates,
            _company(
                pending_company,
                "Account Pending Company",
                "90000000000001",
                CompanyStatus.PENDING,
            ),
            _company(
                approved_company,
                "Account Approved Company",
                "90000000000002",
                CompanyStatus.APPROVED,
            ),
        )
    )
    database_session.flush()
    database_session.add_all(
        (
            Resume(candidate_id=complete.id, completion_percentage=100),
            Resume(candidate_id=partial.id, completion_percentage=40),
        )
    )
    database_session.commit()

    return AccountManagementScenario(
        administrator_id=administrator.id,
        complete_candidate_id=complete.id,
        partial_candidate_id=partial.id,
        no_resume_candidate_id=no_resume.id,
        blocked_candidate_id=blocked.id,
        pending_company_id=pending_company.id,
        approved_company_id=approved_company.id,
    )
