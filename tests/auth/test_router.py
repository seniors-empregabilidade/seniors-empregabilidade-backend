from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.exceptions import AccountNotActiveError, InvalidCredentialsError
from app.auth.integrations import cognito
from app.auth.integrations.cognito import CognitoIdentityProvider
from app.auth.router import provide_identity_provider
from app.auth.services.identity_provider import IdentityTokens
from app.core.config import Settings, get_settings
from app.db.session import get_session
from tests.auth.conftest import (
    DEMO_USER_ID,
    FakeIdentityProvider,
    FakeSession,
    UserRecord,
)

LOGIN_URL = "/api/v1/auth/login"
CREDENTIALS = {
    "email": "candidate@example.invalid",
    "password": "LocalDemoOnly!2026",
}


@pytest.fixture
def provider(tokens: IdentityTokens) -> FakeIdentityProvider:
    return FakeIdentityProvider(tokens=tokens)


@pytest.fixture
def signed_in(
    application: FastAPI,
    client: TestClient,
    provider: FakeIdentityProvider,
    active_record: UserRecord,
) -> Iterator[TestClient]:
    application.dependency_overrides[provide_identity_provider] = lambda: provider
    application.dependency_overrides[get_session] = lambda: FakeSession(
        record=active_record
    )
    yield client
    application.dependency_overrides.clear()


def test_signing_in_returns_the_session_and_the_role(signed_in: TestClient) -> None:
    response = signed_in.post(LOGIN_URL, json=CREDENTIALS)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["access_token"] == "access-token-value"
    assert body["id_token"] == "id-token-value"
    assert body["token_type"] == "Bearer"
    assert body["user_id"] == str(DEMO_USER_ID)
    assert body["user_type"] == "candidate"


def test_the_password_is_never_returned(signed_in: TestClient) -> None:
    response = signed_in.post(LOGIN_URL, json=CREDENTIALS)

    assert "password" not in response.json()
    assert CREDENTIALS["password"] not in response.text


def test_the_session_response_is_never_cached(signed_in: TestClient) -> None:
    response = signed_in.post(LOGIN_URL, json=CREDENTIALS)

    assert response.headers["cache-control"] == "no-store"


def test_the_email_reaches_the_provider_normalized(
    signed_in: TestClient, provider: FakeIdentityProvider
) -> None:
    signed_in.post(
        LOGIN_URL,
        json={"email": "  CANDIDATE@Example.INVALID  ", "password": "whatever"},
    )

    assert provider.calls == [("candidate@example.invalid", "whatever")]


def test_rejected_credentials_answer_with_a_generic_problem(
    application: FastAPI, client: TestClient, active_record: UserRecord
) -> None:
    provider = FakeIdentityProvider(error=InvalidCredentialsError())
    application.dependency_overrides[provide_identity_provider] = lambda: provider
    application.dependency_overrides[get_session] = lambda: FakeSession(
        record=active_record
    )

    response = client.post(LOGIN_URL, json=CREDENTIALS)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "invalid_credentials"
    assert body["detail"] == "The email or password is incorrect."
    # The failure must not echo the submitted address back to the caller.
    assert CREDENTIALS["email"] not in response.text


def test_a_non_active_account_is_told_apart_from_bad_credentials(
    application: FastAPI, client: TestClient, tokens: IdentityTokens
) -> None:
    provider = FakeIdentityProvider(tokens=tokens)
    application.dependency_overrides[provide_identity_provider] = lambda: provider
    application.dependency_overrides[get_session] = lambda: FakeSession(record=None)

    response = client.post(LOGIN_URL, json=CREDENTIALS)

    assert response.status_code == 403
    assert response.json()["code"] == "account_not_active"


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "candidate@example.invalid"},
        {"password": "LocalDemoOnly!2026"},
        {"email": "candidate@example.invalid", "password": ""},
        {"email": "   ", "password": "LocalDemoOnly!2026"},
        {"email": "candidate@example.invalid", "password": "x", "role": "admin"},
    ],
)
def test_an_invalid_request_never_reaches_the_provider(
    application: FastAPI,
    client: TestClient,
    provider: FakeIdentityProvider,
    payload: dict[str, Any],
) -> None:
    application.dependency_overrides[provide_identity_provider] = lambda: provider
    application.dependency_overrides[get_session] = lambda: FakeSession(record=None)

    response = client.post(LOGIN_URL, json=payload)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert provider.calls == []


def test_the_submitted_password_never_appears_in_a_validation_problem(
    application: FastAPI, client: TestClient, provider: FakeIdentityProvider
) -> None:
    application.dependency_overrides[provide_identity_provider] = lambda: provider

    response = client.post(
        LOGIN_URL, json={"email": "x", "password": "SuperSecret!2026"}
    )

    assert response.status_code == 422
    assert "SuperSecret!2026" not in response.text


def test_a_provider_failure_is_reported_without_its_details(
    application: FastAPI, client: TestClient, active_record: UserRecord
) -> None:
    provider = FakeIdentityProvider(error=AccountNotActiveError())
    application.dependency_overrides[provide_identity_provider] = lambda: provider
    application.dependency_overrides[get_session] = lambda: FakeSession(
        record=active_record
    )

    response = client.post(LOGIN_URL, json=CREDENTIALS)

    assert response.status_code == 403


def test_the_public_contract_documents_its_failures(client: TestClient) -> None:
    operation = client.get("/openapi.json").json()["paths"][LOGIN_URL]["post"]

    assert set(operation["responses"]) >= {"200", "401", "403", "422", "429", "502"}


def test_the_response_schema_exposes_no_credential_field(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()["components"]["schemas"]

    assert "password" not in schema["LoginResponse"]["properties"]
    assert "password_hash" not in schema["LoginResponse"]["properties"]


def test_the_route_wires_the_real_cognito_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cognito, "build_cognito_client", lambda region: object())
    settings = Settings(cognito_region="us-east-1", cognito_client_id="client-123")

    provider = provide_identity_provider(settings)

    assert isinstance(provider, CognitoIdentityProvider)


def test_the_route_reports_an_unconfigured_provider_instead_of_crashing(
    application: FastAPI, client: TestClient
) -> None:
    application.dependency_overrides[get_session] = lambda: FakeSession(record=None)
    monkeypatched = Settings(cognito_client_id="")
    application.dependency_overrides[get_settings] = lambda: monkeypatched

    response = client.post(LOGIN_URL, json=CREDENTIALS)

    assert response.status_code == 502
    assert response.json()["code"] == "identity_provider_unavailable"
