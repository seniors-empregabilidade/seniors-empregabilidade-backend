import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.companies.router import get_company_registry
from app.companies.schemas.company_request import CompanyRegistrationRequest
from app.companies.schemas.registry_record_response import RegistryRecordResponse
from app.companies.services.company_registry import CompanyRegistry
from app.companies.services.register_company import register_company
from app.db.models import Address, AppUser, Company
from app.db.models.enums import CompanyStatus, UserType
from app.db.session import get_session_factory
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import IdentityProviderUnavailableError
from tests.identity.fakes import FakeIdentityProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]

TEST_EMAIL = "registration-test@company.example.invalid"
TEST_CNPJ = "11222333000181"
SECOND_EMAIL = "second@company.example.invalid"


class FakeRegistry:
    def get_record(self, cnpj: str) -> RegistryRecordResponse:
        return RegistryRecordResponse(
            cnpj=cnpj,
            legal_name="Synthetic Registry Company SA",
            trade_name="Provider name ignored",
            primary_cnae="6201501",
        )


@pytest.fixture(autouse=True)
def identity_provider(application: FastAPI) -> FakeIdentityProvider:
    provider = FakeIdentityProvider()
    application.dependency_overrides[get_identity_provider] = lambda: provider
    return provider


@pytest.fixture(autouse=True)
def clean_registration_rows() -> Iterator[None]:
    factory = get_session_factory()
    with factory.begin() as session:
        company = session.scalar(select(Company).where(Company.cnpj == TEST_CNPJ))
        if company:
            address_id = company.address_id
            session.execute(delete(AppUser).where(AppUser.id == company.id))
            if address_id:
                session.execute(delete(Address).where(Address.id == address_id))
        session.execute(delete(AppUser).where(AppUser.email == TEST_EMAIL))
        session.execute(delete(AppUser).where(AppUser.email == SECOND_EMAIL))
    yield
    with factory.begin() as session:
        company = session.scalar(select(Company).where(Company.cnpj == TEST_CNPJ))
        if company:
            address_id = company.address_id
            session.execute(delete(AppUser).where(AppUser.id == company.id))
            if address_id:
                session.execute(delete(Address).where(Address.id == address_id))
        session.execute(delete(AppUser).where(AppUser.email == TEST_EMAIL))
        session.execute(delete(AppUser).where(AppUser.email == SECOND_EMAIL))


def test_post_persists_complete_company_atomically(
    application: FastAPI, client: TestClient
) -> None:
    def registry_dependency() -> Iterator[CompanyRegistry]:
        yield FakeRegistry()

    application.dependency_overrides[get_company_registry] = registry_dependency

    response = client.post(
        "/api/v1/companies",
        json={
            "cnpj": "11.222.333/0001-81",
            "display_name": "Chosen Display Name",
            "address": {
                "street": "Synthetic Street",
                "number": "42",
                "complement": None,
                "neighborhood": "Test District",
                "city": "Test City",
                "state": "sp",
                "zip_code": "12345-678",
            },
            "corporate_email": "registration-test@Company.Example.Invalid",
            "password": "SyntheticPass!2026",
            "terms_accepted": True,
            "terms_version": "2026-08",
        },
    )

    assert response.status_code == 201
    assert set(response.json()) == {
        "id",
        "email",
        "status",
        "email_confirmation_required",
    }
    factory = get_session_factory()
    with factory() as session:
        company = session.scalar(select(Company).where(Company.cnpj == TEST_CNPJ))
        assert company is not None
        user = session.get(AppUser, company.id)
        address = session.get(Address, company.address_id)
        assert user is not None and address is not None
        assert user.user_type == UserType.COMPANY
        assert user.identity_subject == "synthetic-subject"
        assert "password_hash" not in AppUser.__table__.columns
        assert company.status == CompanyStatus.PENDING
        assert company.legal_name == "Synthetic Registry Company SA"
        assert company.trade_name == "Chosen Display Name"
        assert company.terms_version_accepted == "2026-08"
        assert company.terms_accepted_at is not None
        assert address.neighborhood == "Test District"
        assert address.state == "SP" and address.zip_code == "12345678"


def test_duplicate_cnpj_rolls_back_new_user_and_address(
    application: FastAPI, client: TestClient
) -> None:
    test_post_persists_complete_company_atomically(application, client)
    with get_session_factory()() as session:
        addresses_before = session.scalar(select(func.count()).select_from(Address))
    response = client.post(
        "/api/v1/companies",
        json={
            "cnpj": TEST_CNPJ,
            "display_name": "Duplicate",
            "address": {
                "street": "Other",
                "number": "1",
                "neighborhood": "Other",
                "city": "Other",
                "state": "RS",
                "zip_code": "90000000",
            },
            "corporate_email": SECOND_EMAIL,
            "password": "SyntheticPass!2026",
            "terms_accepted": True,
            "terms_version": "2026-08",
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "company_cnpj_conflict"
    assert "cnpj" in response.json()["errors"]
    with get_session_factory()() as session:
        assert (
            session.scalar(select(func.count()).select_from(Address))
            == addresses_before
        )
    factory = get_session_factory()
    with factory() as session:
        assert (
            session.scalar(select(AppUser).where(AppUser.email == SECOND_EMAIL)) is None
        )


def test_database_uniqueness_handles_concurrent_cnpj_registration(
    application: FastAPI, client: TestClient
) -> None:
    barrier = Barrier(2)

    class ConcurrentRegistry(FakeRegistry):
        def get_record(self, cnpj: str) -> RegistryRecordResponse:
            barrier.wait(timeout=5)
            return super().get_record(cnpj)

    def registry_dependency() -> Iterator[CompanyRegistry]:
        yield ConcurrentRegistry()

    application.dependency_overrides[get_company_registry] = registry_dependency

    def submit(email: str) -> int:
        response = client.post(
            "/api/v1/companies",
            json={
                "cnpj": TEST_CNPJ,
                "display_name": "Concurrent",
                "address": {
                    "street": "Concurrent Street",
                    "number": "1",
                    "neighborhood": "Concurrent District",
                    "city": "Concurrent City",
                    "state": "SP",
                    "zip_code": "12345678",
                },
                "corporate_email": email,
                "password": "SyntheticPass!2026",
                "terms_accepted": True,
                "terms_version": "2026-08",
            },
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(submit, (TEST_EMAIL, SECOND_EMAIL)))

    assert statuses == [201, 409]
    factory = get_session_factory()
    with factory() as session:
        companies = session.scalars(
            select(Company).where(Company.cnpj == TEST_CNPJ)
        ).all()
        assert len(companies) == 1


def registration_request(**changes: object) -> CompanyRegistrationRequest:
    payload: dict[str, object] = {
        "cnpj": TEST_CNPJ,
        "display_name": "Synthetic Company",
        "address": {
            "street": "Synthetic Street",
            "number": "1",
            "neighborhood": "Test",
            "city": "Test",
            "state": "RS",
            "zip_code": "90000000",
        },
        "corporate_email": TEST_EMAIL,
        "password": "SyntheticPass!2026",
        "terms_accepted": True,
        "terms_version": "v1",
    }
    payload.update(changes)
    return CompanyRegistrationRequest.model_validate(payload)


def register_with(session: Session, provider: FakeIdentityProvider) -> None:
    register_company(
        registration_request(),
        session=session,
        registry=FakeRegistry(),
        identity_provider=provider,
        blocked_cnae_prefixes=(),
        personal_email_domains=frozenset(),
    )


def assert_no_partial_registration() -> None:
    with get_session_factory()() as session:
        assert (
            session.scalar(select(AppUser).where(AppUser.email == TEST_EMAIL)) is None
        )
        assert session.scalar(select(Company).where(Company.cnpj == TEST_CNPJ)) is None
        assert (
            session.scalar(
                select(func.count())
                .select_from(Address)
                .where(Address.street == "Synthetic Street")
            )
            == 0
        )


def test_identity_outage_rolls_back_user_company_and_address(
    identity_provider: FakeIdentityProvider,
) -> None:
    identity_provider.error = IdentityProviderUnavailableError()
    with (
        get_session_factory()() as session,
        pytest.raises(IdentityProviderUnavailableError),
    ):
        register_with(session, identity_provider)
    assert_no_partial_registration()
    assert identity_provider.calls == ["register"]


@pytest.mark.parametrize("confirmed", [True, False])
def test_definite_database_failure_keeps_identity_for_a_proven_owner_retry(
    identity_provider: FakeIdentityProvider,
    monkeypatch: pytest.MonkeyPatch,
    confirmed: bool,
) -> None:
    identity_provider.confirmed = confirmed
    with get_session_factory()() as session:

        def fail_commit() -> None:
            raise IntegrityError("synthetic", None, Exception("synthetic constraint"))

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(IntegrityError):
            register_with(session, identity_provider)
    assert_no_partial_registration()
    assert identity_provider.calls == ["register"]


def test_unknown_commit_outcome_never_deletes_identity(
    identity_provider: FakeIdentityProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    with get_session_factory()() as session:
        commit = session.commit

        def commit_then_lose_acknowledgement() -> None:
            commit()
            raise ConnectionError("synthetic lost acknowledgement")

        monkeypatch.setattr(session, "commit", commit_then_lose_acknowledgement)
        with pytest.raises(ConnectionError):
            register_with(session, identity_provider)
    with get_session_factory()() as session:
        user = session.scalar(select(AppUser).where(AppUser.email == TEST_EMAIL))
        assert user is not None and user.identity_subject == identity_provider.subject
    assert identity_provider.calls == ["register"]


def test_failure_before_commit_keeps_identity_for_retry(
    identity_provider: FakeIdentityProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    with get_session_factory()() as session:
        flush = session.flush

        def flush_failure(*args: object, **kwargs: object) -> None:
            if identity_provider.calls:
                raise RuntimeError("synthetic failure before commit")
            flush()

        monkeypatch.setattr(session, "flush", flush_failure)
        with pytest.raises(RuntimeError):
            register_with(session, identity_provider)
    assert_no_partial_registration()
    assert identity_provider.calls == ["register"]


@pytest.mark.parametrize(
    ("changes", "code", "field"),
    [
        ({"cnpj": "00000000000000"}, "invalid_cnpj", "cnpj"),
        (
            {"corporate_email": "synthetic@gmail.com"},
            "company_email_domain_blocked",
            "corporate_email",
        ),
        ({"terms_accepted": False}, "validation_error", "body.terms_accepted"),
        (
            {
                "address": {
                    "street": "Test",
                    "number": "1",
                    "neighborhood": "Test",
                    "city": "Test",
                    "state": "RS",
                    "zip_code": "abcdefgh",
                }
            },
            "validation_error",
            "body.address.zip_code",
        ),
    ],
)
def test_registration_validation_has_field_errors_and_no_identity_call(
    application: FastAPI,
    client: TestClient,
    identity_provider: FakeIdentityProvider,
    changes: dict[str, object],
    code: str,
    field: str,
) -> None:
    application.dependency_overrides[get_company_registry] = lambda: FakeRegistry()
    request = registration_request().model_dump(mode="json")
    request["password"] = "SyntheticPass!2026"
    request.update(changes)
    response = client.post("/api/v1/companies", json=request)
    assert response.status_code == 422
    assert response.json()["code"] == code
    assert field in response.json()["errors"]
    assert identity_provider.calls == []
    assert_no_partial_registration()


def test_unique_subject_cannot_link_two_local_accounts(
    application: FastAPI, client: TestClient, identity_provider: FakeIdentityProvider
) -> None:
    identity_provider.confirmed = True
    with get_session_factory().begin() as session:
        session.add(
            AppUser(
                email=SECOND_EMAIL,
                identity_subject=identity_provider.subject,
                user_type=UserType.CANDIDATE,
            )
        )
    application.dependency_overrides[get_company_registry] = lambda: FakeRegistry()
    payload = registration_request().model_dump(mode="json")
    payload["password"] = "SyntheticPass!2026"
    response = client.post("/api/v1/companies", json=payload)
    assert response.status_code == 409
    assert response.json()["code"] == "identity_conflict"
    assert_no_partial_registration()
    assert identity_provider.calls == ["register"]


def test_retry_after_database_failure_can_confirm_register_and_login(
    application: FastAPI,
    client: TestClient,
    identity_provider: FakeIdentityProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with get_session_factory()() as session:

        def fail_commit() -> None:
            raise IntegrityError("synthetic", None, Exception("synthetic"))

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(IntegrityError):
            register_with(session, identity_provider)
    assert_no_partial_registration()
    response = client.post(
        "/api/v1/email-verification/confirm",
        json={"email": TEST_EMAIL, "code": "123456"},
    )
    assert response.status_code == 204
    application.dependency_overrides[get_company_registry] = lambda: FakeRegistry()
    payload = registration_request().model_dump(mode="json")
    payload["password"] = "SyntheticPass!2026"
    response = client.post("/api/v1/companies", json=payload)
    assert response.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": "SyntheticPass!2026"},
    )
    assert login.status_code == 200
    assert login.json()["user_id"] == response.json()["id"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer access"})
    assert me.status_code == 200 and me.json()["company_status"] == "pending"
    with get_session_factory()() as session:
        company = session.scalar(select(Company).where(Company.cnpj == TEST_CNPJ))
        assert company is not None and company.corporate_email_confirmed


def test_duplicate_email_has_field_error_without_new_identity_or_address(
    application: FastAPI, client: TestClient, identity_provider: FakeIdentityProvider
) -> None:
    test_post_persists_complete_company_atomically(application, client)
    with get_session_factory()() as session:
        addresses_before = session.scalar(select(func.count()).select_from(Address))
    identity_provider.calls.clear()
    payload = registration_request(cnpj="11444777000161").model_dump(mode="json")
    payload["password"] = "SyntheticPass!2026"
    response = client.post("/api/v1/companies", json=payload)
    assert response.status_code == 409
    assert response.json()["code"] == "company_email_conflict"
    assert response.json()["errors"] == {
        "corporate_email": ["An account with this email already exists."]
    }
    assert identity_provider.calls == []
    with get_session_factory()() as session:
        assert (
            session.scalar(select(func.count()).select_from(Address))
            == addresses_before
        )


def test_blocked_segment_never_creates_identity_or_rows(
    application: FastAPI,
    client: TestClient,
    identity_provider: FakeIdentityProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "blocked_cnae_prefixes", ["62"])
    application.dependency_overrides[get_company_registry] = lambda: FakeRegistry()
    payload = registration_request().model_dump(mode="json")
    payload["password"] = "SyntheticPass!2026"
    response = client.post("/api/v1/companies", json=payload)
    assert response.status_code == 422
    assert response.json()["code"] == "company_segment_blocked"
    assert "cnpj" in response.json()["errors"]
    assert identity_provider.calls == []
    assert_no_partial_registration()


def test_linkedin_is_saved_without_marking_it_verified(
    identity_provider: FakeIdentityProvider,
) -> None:
    with get_session_factory()() as session:
        result = register_company(
            registration_request(
                linkedin_url="https://www.linkedin.com/company/synthetic-company"
            ),
            session=session,
            registry=FakeRegistry(),
            identity_provider=identity_provider,
            blocked_cnae_prefixes=(),
            personal_email_domains=frozenset(),
        )
        company = session.get(Company, result.id)
        assert company is not None
        assert (
            company.linkedin_url == "https://www.linkedin.com/company/synthetic-company"
        )
        assert not company.linkedin_verified
