import os
from collections.abc import Iterator

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.auth.dependencies import require_administrator, require_approved_company
from app.db.models import AppUser, Company
from app.db.models.enums import AccountStatus, CompanyStatus, UserType
from app.db.session import get_session_factory
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import (
    InvalidAccessTokenError,
    InvalidConfirmationCodeError,
    InvalidCredentialsError,
)
from tests.identity.fakes import FakeIdentityProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]
EMAIL = "auth-flow@company.example.invalid"
SUBJECT = "auth-flow-subject"


@pytest.fixture
def provider(application: FastAPI) -> FakeIdentityProvider:
    fake = FakeIdentityProvider()
    fake.subject = SUBJECT
    application.dependency_overrides[get_identity_provider] = lambda: fake
    return fake


@pytest.fixture(autouse=True)
def clean_rows() -> Iterator[None]:
    yield
    with get_session_factory().begin() as session:
        session.execute(delete(AppUser).where(AppUser.email == EMAIL))


def add_user(
    *,
    role: UserType = UserType.CANDIDATE,
    status: AccountStatus = AccountStatus.ACTIVE,
    subject: str | None = SUBJECT,
) -> None:
    with get_session_factory().begin() as session:
        session.add(
            AppUser(
                email=EMAIL,
                identity_subject=subject,
                user_type=role,
                account_status=status,
            )
        )


def test_login_and_me_use_subject_and_database_role(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_user(role=UserType.ADMINISTRATOR)
    response = client.post(
        "/api/v1/auth/login", json={"email": EMAIL.upper(), "password": "synthetic"}
    )
    assert response.status_code == 200
    assert response.json()["user_type"] == "administrator"
    assert response.headers["Cache-Control"] == "no-store"
    me = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer access"})
    assert me.status_code == 200
    assert me.json()["id"] == response.json()["user_id"]
    assert "identity_subject" not in me.json()
    assert provider.calls == ["authenticate", "verify"]


def test_same_email_cannot_authenticate_an_unlinked_local_user(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_user(subject=None)
    response = client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": "synthetic"}
    )
    assert response.status_code == 401
    assert "access_token" not in response.json()


@pytest.mark.parametrize("status", [AccountStatus.SUSPENDED, AccountStatus.BLOCKED])
def test_local_status_blocks_an_otherwise_valid_token(
    client: TestClient, provider: FakeIdentityProvider, status: AccountStatus
) -> None:
    add_user(status=status)
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer access"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": "synthetic"}
        ).status_code
        == 403
    )


def test_missing_or_invalid_token_is_401(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert provider.calls == []
    provider.error = InvalidAccessTokenError()
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer invalid"}
        ).status_code
        == 401
    )


def test_credentials_error_does_not_return_secrets(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    provider.error = InvalidCredentialsError()
    response = client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": "synthetic-password"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"
    assert EMAIL not in response.text and "synthetic-password" not in response.text


def test_client_cannot_choose_role(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": EMAIL, "password": "synthetic", "user_type": "administrator"},
    )
    assert response.status_code == 422
    assert provider.calls == []


def test_confirmation_without_local_user_allows_registration_recovery(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    assert (
        client.post(
            "/api/v1/email-verification/confirm",
            json={"email": EMAIL, "code": "123456"},
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/v1/email-verification/send", json={"email": EMAIL}
        ).status_code
        == 202
    )
    assert provider.calls == ["confirm", "resend"]
    with get_session_factory()() as session:
        assert session.scalar(select(AppUser).where(AppUser.email == EMAIL)) is None


def test_invalid_confirmation_has_field_error(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    provider.error = InvalidConfirmationCodeError()
    response = client.post(
        "/api/v1/email-verification/confirm", json={"email": EMAIL, "code": "123456"}
    )
    assert response.status_code == 422
    assert response.json()["errors"]["code"]
    assert "123456" not in response.text


def test_only_database_administrator_passes_guard(
    application: FastAPI, client: TestClient, provider: FakeIdentityProvider
) -> None:
    application.get("/test-admin", dependencies=[Depends(require_administrator)])(
        lambda: {"ok": True}
    )
    add_user()
    assert (
        client.get(
            "/test-admin", headers={"Authorization": "Bearer access"}
        ).status_code
        == 403
    )
    with get_session_factory().begin() as session:
        user = session.scalar(select(AppUser).where(AppUser.email == EMAIL))
        assert user is not None
        user.user_type = UserType.ADMINISTRATOR
    assert (
        client.get(
            "/test-admin", headers={"Authorization": "Bearer access"}
        ).status_code
        == 200
    )


def test_pending_company_can_identify_but_cannot_use_approved_features(
    application: FastAPI, client: TestClient, provider: FakeIdentityProvider
) -> None:
    application.get("/test-company", dependencies=[Depends(require_approved_company)])(
        lambda: {"ok": True}
    )
    add_user(role=UserType.COMPANY)
    with get_session_factory().begin() as session:
        user = session.scalar(select(AppUser).where(AppUser.email == EMAIL))
        assert user is not None
        session.add(
            Company(
                id=user.id,
                cnpj="11444777000161",
                legal_name="Synthetic Auth Company",
                trade_name="Synthetic",
                corporate_email=EMAIL,
                primary_cnae="6201501",
                status=CompanyStatus.PENDING,
            )
        )
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer access"})
    assert response.status_code == 200
    assert response.json()["company_status"] == "pending"
    assert (
        client.get(
            "/test-company", headers={"Authorization": "Bearer access"}
        ).status_code
        == 403
    )
    with get_session_factory().begin() as session:
        company = session.scalar(
            select(Company).where(Company.corporate_email == EMAIL)
        )
        assert company is not None
        company.status = CompanyStatus.APPROVED
    assert (
        client.get(
            "/test-company", headers={"Authorization": "Bearer access"}
        ).status_code
        == 200
    )
