"""Integration tests for GET/PUT /api/v1/companies/me/profile (US-30-T01)."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any, ClassVar
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Address, AppUser, Candidate, Company, Job
from app.db.models.enums import CompanyStatus, JobStatus, UserType, WorkMode
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from tests.identity.fakes import FakeIdentityProvider

pytestmark = pytest.mark.integration

PROFILE_PATH = "/api/v1/companies/me/profile"
OWNER_TOKEN = "profile-owner"
OTHER_TOKEN = "profile-other"
PENDING_TOKEN = "profile-pending"
CANDIDATE_TOKEN = "profile-candidate"
OWNER_CNPJ = "11222333000181"
OWNER_LOGIN_EMAIL = "login@profile-owner.example.invalid"


class ProfileIdentityProvider(FakeIdentityProvider):
    SUBJECTS: ClassVar[dict[str, str]] = {
        token: f"subject-{token}"
        for token in (OWNER_TOKEN, OTHER_TOKEN, PENDING_TOKEN, CANDIDATE_TOKEN)
    }

    def verify_access_token(self, token: str) -> str:
        try:
            return self.SUBJECTS[token]
        except KeyError:
            raise InvalidAccessTokenError from None


@pytest.fixture
def profile_client(
    application: FastAPI, database_session: Session
) -> Iterator[TestClient]:
    provider = ProfileIdentityProvider()
    application.dependency_overrides[get_session] = lambda: database_session
    application.dependency_overrides[get_identity_provider] = lambda: provider
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client
    application.dependency_overrides.clear()


def _user(session: Session, token: str, email: str, user_type: UserType) -> AppUser:
    user = AppUser(
        email=email,
        identity_subject=ProfileIdentityProvider.SUBJECTS[token],
        user_type=user_type,
    )
    session.add(user)
    session.flush()
    return user


def _company(
    session: Session,
    token: str,
    *,
    cnpj: str,
    email: str,
    status: CompanyStatus = CompanyStatus.APPROVED,
    with_address: bool = True,
) -> Company:
    user = _user(session, token, email, UserType.COMPANY)
    address = None
    if with_address:
        address = Address(
            street="Rua Sintética",
            number="10",
            neighborhood="Centro",
            city="Porto Alegre",
            state="RS",
            zip_code="90010000",
        )
        session.add(address)
        session.flush()
    company = Company(
        id=user.id,
        cnpj=cnpj,
        legal_name=f"Legal {token}",
        trade_name=f"Trade {token}",
        corporate_email=email,
        status=status,
        address_id=address.id if address else None,
    )
    session.add(company)
    session.flush()
    return company


@pytest.fixture
def owner(database_session: Session) -> Company:
    company = _company(
        database_session, OWNER_TOKEN, cnpj=OWNER_CNPJ, email=OWNER_LOGIN_EMAIL
    )
    database_session.commit()
    return company


def _candidate(session: Session) -> None:
    user = _user(
        session,
        CANDIDATE_TOKEN,
        "candidate@profile.example.invalid",
        UserType.CANDIDATE,
    )
    session.add(
        Candidate(
            id=user.id,
            full_name="Synthetic Candidate",
            cpf="52998224725",
            birth_date=date(1968, 1, 1),
            phone="+5551999990000",
        )
    )
    session.flush()


def _payload(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "display_name": "Nova Marca",
        "legal_name": "Nova Razão Social Ltda",
        "industry": "Tecnologia",
        "address": {
            "street": "Avenida Nova",
            "number": "200",
            "complement": "Sala 3",
            "neighborhood": "Moinhos",
            "city": "Canoas",
            "state": "rs",
            "zip_code": "92010-000",
        },
        "contact_email": "Contato@Profile-Owner.example.invalid",
        "contact_phone": "+55 51 3333-0000",
    }
    payload.update(changes)
    return payload


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_company_reads_its_own_profile(
    profile_client: TestClient, owner: Company
) -> None:
    response = profile_client.get(PROFILE_PATH, headers=_auth(OWNER_TOKEN))

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {
        "id": str(owner.id),
        "cnpj": OWNER_CNPJ,
        "display_name": f"Trade {OWNER_TOKEN}",
        "legal_name": f"Legal {OWNER_TOKEN}",
        "industry": None,
        "address": {
            "street": "Rua Sintética",
            "number": "10",
            "complement": None,
            "neighborhood": "Centro",
            "city": "Porto Alegre",
            "state": "RS",
            "zip_code": "90010000",
        },
        # Not edited yet: the login e-mail is shown as the contact.
        "contact_email": OWNER_LOGIN_EMAIL,
        "contact_phone": None,
    }


def test_edit_persists_and_keeps_cnpj_and_login_email(
    profile_client: TestClient, database_session: Session, owner: Company
) -> None:
    other = _company(
        database_session,
        OTHER_TOKEN,
        cnpj="11444777000161",
        email="login@profile-other.example.invalid",
    )
    database_session.commit()

    response = profile_client.put(
        PROFILE_PATH,
        json=_payload(cnpj="11.222.333/0001-81"),
        headers=_auth(OWNER_TOKEN),
    )

    assert response.status_code == 200
    reloaded = profile_client.get(PROFILE_PATH, headers=_auth(OWNER_TOKEN)).json()
    assert reloaded == response.json()
    assert reloaded["display_name"] == "Nova Marca"
    assert reloaded["legal_name"] == "Nova Razão Social Ltda"
    assert reloaded["industry"] == "Tecnologia"
    assert reloaded["address"]["city"] == "Canoas"
    assert reloaded["address"]["state"] == "RS"
    assert reloaded["address"]["zip_code"] == "92010000"
    assert reloaded["contact_email"] == "contato@profile-owner.example.invalid"
    assert reloaded["contact_phone"] == "+55 51 3333-0000"

    database_session.expire_all()
    stored = database_session.get_one(Company, owner.id)
    assert stored.cnpj == OWNER_CNPJ
    assert stored.corporate_email == OWNER_LOGIN_EMAIL
    assert stored.status == CompanyStatus.APPROVED
    assert database_session.get_one(AppUser, owner.id).email == OWNER_LOGIN_EMAIL
    assert database_session.get_one(Company, other.id).trade_name == (
        f"Trade {OTHER_TOKEN}"
    )


def test_optional_fields_can_be_cleared(
    profile_client: TestClient, owner: Company
) -> None:
    profile_client.put(PROFILE_PATH, json=_payload(), headers=_auth(OWNER_TOKEN))

    response = profile_client.put(
        PROFILE_PATH,
        json=_payload(industry="", contact_phone=None),
        headers=_auth(OWNER_TOKEN),
    )

    assert response.status_code == 200
    assert response.json()["industry"] is None
    assert response.json()["contact_phone"] is None


def test_company_without_address_gets_one(
    profile_client: TestClient, database_session: Session
) -> None:
    _company(
        database_session,
        OWNER_TOKEN,
        cnpj=OWNER_CNPJ,
        email=OWNER_LOGIN_EMAIL,
        with_address=False,
    )
    database_session.commit()

    response = profile_client.put(
        PROFILE_PATH, json=_payload(), headers=_auth(OWNER_TOKEN)
    )

    assert response.status_code == 200
    assert response.json()["address"]["street"] == "Avenida Nova"


def test_cnpj_change_is_rejected_without_writing(
    profile_client: TestClient, database_session: Session, owner: Company
) -> None:
    response = profile_client.put(
        PROFILE_PATH, json=_payload(cnpj="11444777000161"), headers=_auth(OWNER_TOKEN)
    )

    assert response.status_code == 422
    assert response.json()["code"] == "cnpj_read_only"
    assert list(response.json()["errors"]) == ["cnpj"]
    database_session.expire_all()
    assert database_session.get_one(Company, owner.id).trade_name == (
        f"Trade {OWNER_TOKEN}"
    )


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"display_name": "  "}, "body.display_name"),
        ({"legal_name": None}, "body.legal_name"),
        ({"contact_email": "not-an-email"}, "body.contact_email"),
        ({"contact_phone": "abc"}, "body.contact_phone"),
        (
            {"address": {**_payload()["address"], "zip_code": "123"}},
            "body.address.zip_code",
        ),
        ({"address": {**_payload()["address"], "state": "XX"}}, "body.address.state"),
        ({"corporate_email": "login@other.example.invalid"}, "body.corporate_email"),
    ],
)
def test_invalid_fields_are_reported_per_field(
    profile_client: TestClient,
    database_session: Session,
    owner: Company,
    change: dict[str, Any],
    field: str,
) -> None:
    response = profile_client.put(
        PROFILE_PATH, json=_payload(**change), headers=_auth(OWNER_TOKEN)
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert field in response.json()["errors"]
    database_session.expire_all()
    assert database_session.get_one(Company, owner.id).legal_name == (
        f"Legal {OWNER_TOKEN}"
    )


def test_personal_contact_email_is_rejected(
    profile_client: TestClient, owner: Company
) -> None:
    response = profile_client.put(
        PROFILE_PATH,
        json=_payload(contact_email="empresa@gmail.com"),
        headers=_auth(OWNER_TOKEN),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "company_email_domain_blocked"
    assert list(response.json()["errors"]) == ["contact_email"]


@pytest.mark.parametrize("method", ["get", "put"])
@pytest.mark.parametrize(
    ("token", "user_type"),
    [(PENDING_TOKEN, UserType.COMPANY), (CANDIDATE_TOKEN, UserType.CANDIDATE)],
)
def test_only_approved_companies_reach_the_profile(
    profile_client: TestClient,
    database_session: Session,
    method: str,
    token: str,
    user_type: UserType,
) -> None:
    if user_type == UserType.COMPANY:
        _company(
            database_session,
            token,
            cnpj="11444777000161",
            email="login@profile-pending.example.invalid",
            status=CompanyStatus.PENDING,
        )
    else:
        _candidate(database_session)
    database_session.commit()

    response = profile_client.request(
        method.upper(), PROFILE_PATH, json=_payload(), headers=_auth(token)
    )

    assert response.status_code == 403
    assert response.json()["code"] == "approved_company_required"


def _published_job(session: Session, company_id: UUID) -> Job:
    job = Job(
        company_id=company_id,
        title="Synthetic Role",
        description="Synthetic role for profile tests.",
        work_mode=WorkMode.REMOTE,
        status=JobStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        closing_date=date.today() + timedelta(days=30),
    )
    session.add(job)
    session.commit()
    return job


def _company_in_search(client: TestClient, job: Job) -> dict[str, Any]:
    found = client.get("/api/v1/jobs", headers=_auth(CANDIDATE_TOKEN))
    assert found.status_code == 200
    return next(item for item in found.json() if item["id"] == str(job.id))


def test_jobs_show_the_updated_company_name_industry_and_city(
    profile_client: TestClient, database_session: Session, owner: Company
) -> None:
    _candidate(database_session)
    job = _published_job(database_session, owner.id)

    saved = profile_client.put(
        PROFILE_PATH,
        json=_payload(
            display_name="Marca Atualizada",
            industry="Logística",
            address={**_payload()["address"], "city": "Canoas"},
        ),
        headers=_auth(OWNER_TOKEN),
    )

    assert saved.status_code == 200
    detail = profile_client.get(
        f"/api/v1/jobs/{job.id}", headers=_auth(CANDIDATE_TOKEN)
    ).json()
    searched = _company_in_search(profile_client, job)
    for shown in (detail, searched):
        assert shown["company_name"] == "Marca Atualizada"
        assert shown["company_industry"] == "Logística"
        assert shown["company_city"] == "Canoas"


def test_jobs_of_a_company_without_address_or_industry_show_nulls(
    profile_client: TestClient, database_session: Session
) -> None:
    company = _company(
        database_session,
        OTHER_TOKEN,
        cnpj="11444777000161",
        email="login@profile-other.example.invalid",
        with_address=False,
    )
    _candidate(database_session)
    job = _published_job(database_session, company.id)

    detail = profile_client.get(
        f"/api/v1/jobs/{job.id}", headers=_auth(CANDIDATE_TOKEN)
    ).json()
    searched = _company_in_search(profile_client, job)
    for shown in (detail, searched):
        assert shown["company_industry"] is None
        assert shown["company_city"] is None
