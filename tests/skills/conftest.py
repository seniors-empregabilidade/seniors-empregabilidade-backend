from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from typing import ClassVar
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import AppUser, Candidate, Company
from app.db.models.enums import CompanyStatus, UserType
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from tests.identity.fakes import FakeIdentityProvider

ADMIN_TOKEN = "skill-catalog-admin"
CANDIDATE_TOKEN = "skill-catalog-candidate"
OTHER_CANDIDATE_TOKEN = "skill-catalog-other-candidate"
COMPANY_TOKEN = "skill-catalog-company"


class CatalogFlowIdentityProvider(FakeIdentityProvider):
    SUBJECTS_BY_TOKEN: ClassVar[dict[str, str]] = {
        ADMIN_TOKEN: "subject-skill-catalog-admin",
        CANDIDATE_TOKEN: "subject-skill-catalog-candidate",
        OTHER_CANDIDATE_TOKEN: "subject-skill-catalog-other-candidate",
        COMPANY_TOKEN: "subject-skill-catalog-company",
    }

    def verify_access_token(self, token: str) -> str:
        try:
            return self.SUBJECTS_BY_TOKEN[token]
        except KeyError:
            raise InvalidAccessTokenError from None


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@dataclass(frozen=True, slots=True)
class CatalogFlowActors:
    administrator_id: UUID
    candidate_id: UUID
    other_candidate_id: UUID
    company_id: UUID


@pytest.fixture
def catalog_flow_actors(database_session: Session) -> CatalogFlowActors:
    subjects = CatalogFlowIdentityProvider.SUBJECTS_BY_TOKEN
    administrator = _user(subjects[ADMIN_TOKEN], UserType.ADMINISTRATOR)
    candidate = _user(subjects[CANDIDATE_TOKEN], UserType.CANDIDATE)
    other_candidate = _user(subjects[OTHER_CANDIDATE_TOKEN], UserType.CANDIDATE)
    company = _user(subjects[COMPANY_TOKEN], UserType.COMPANY)
    database_session.add_all([administrator, candidate, other_candidate, company])
    database_session.flush()
    database_session.add_all(
        [
            _candidate(candidate, "Catalog Candidate"),
            _candidate(other_candidate, "Catalog Other Candidate"),
            Company(
                id=company.id,
                cnpj="47960950000121",
                legal_name="Skill Catalog Company",
                corporate_email=company.email,
                primary_cnae="6201501",
                status=CompanyStatus.APPROVED,
            ),
        ]
    )
    # Committing releases the test savepoint, so a service rolling back a failed
    # request keeps these rows; the test transaction still discards them.
    database_session.commit()
    return CatalogFlowActors(
        administrator_id=administrator.id,
        candidate_id=candidate.id,
        other_candidate_id=other_candidate.id,
        company_id=company.id,
    )


@pytest.fixture
def catalog_flow_client(
    application: FastAPI,
    database_session: Session,
    catalog_flow_actors: CatalogFlowActors,
) -> Iterator[TestClient]:
    del catalog_flow_actors
    provider = CatalogFlowIdentityProvider()
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


def _candidate(user: AppUser, full_name: str) -> Candidate:
    return Candidate(
        id=user.id,
        full_name=full_name,
        cpf=f"{uuid4().int % 10**11:011d}",
        birth_date=date(1968, 5, 20),
        phone="+5551999990000",
        city="Porto Alegre",
        state="RS",
    )
