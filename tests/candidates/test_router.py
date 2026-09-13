from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import IdentityPasswordRejectedError
from tests.identity.fakes import FakeIdentityProvider

pytestmark = pytest.mark.integration

REGISTER_PATH = "/api/v1/professionals"


@pytest.fixture
def registration_client(
    application: FastAPI,
    database_session: Session,
    identity_provider: FakeIdentityProvider,
) -> Iterator[TestClient]:
    application.dependency_overrides[get_session] = lambda: database_session
    application.dependency_overrides[get_identity_provider] = lambda: identity_provider
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client
    application.dependency_overrides.clear()


def valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "full_name": "Maria Souza",
        "cpf": "111.444.777-35",
        "birth_date": "1970-01-01",
        "phone": "+55 51 99999-9999",
        "email": "maria@example.com",
        "password": "LocalDemoOnly!2026",
        "terms_version_accepted": "v1",
        "city": "Porto Alegre",
        "state": "RS",
    }
    payload.update(overrides)
    return payload


def test_eligible_professional_is_registered(
    registration_client: TestClient,
) -> None:
    response = registration_client.post(REGISTER_PATH, json=valid_payload())

    assert response.status_code == 201
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["email"] == "maria@example.com"
    assert response.json()["full_name"] == "Maria Souza"
    assert response.json()["email_verification_required"] is True
    assert isinstance(response.json()["id"], str)


def test_invalid_cpf_is_reported_on_the_cpf_field(
    registration_client: TestClient,
) -> None:
    response = registration_client.post(
        REGISTER_PATH, json=valid_payload(cpf="111.111.111-11")
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "invalid_cpf"
    assert "cpf" in response.json()["errors"]


def test_duplicate_email_is_reported_as_a_conflict(
    registration_client: TestClient,
) -> None:
    assert (
        registration_client.post(REGISTER_PATH, json=valid_payload()).status_code == 201
    )

    response = registration_client.post(
        REGISTER_PATH,
        json=valid_payload(cpf="222.555.888-46"),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "email_already_registered"
    assert "email" in response.json()["errors"]


def test_duplicate_cpf_is_reported_as_a_conflict(
    registration_client: TestClient,
) -> None:
    assert (
        registration_client.post(REGISTER_PATH, json=valid_payload()).status_code == 201
    )

    response = registration_client.post(
        REGISTER_PATH,
        json=valid_payload(email="other@example.com"),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "cpf_already_registered"
    assert "cpf" in response.json()["errors"]


def test_professional_under_45_is_rejected(
    registration_client: TestClient,
) -> None:
    response = registration_client.post(
        REGISTER_PATH,
        json=valid_payload(birth_date="2000-01-01"),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "minimum_age_not_met"
    assert "birth_date" in response.json()["errors"]


def test_terms_acceptance_is_required(registration_client: TestClient) -> None:
    payload = valid_payload()
    del payload["terms_version_accepted"]

    response = registration_client.post(REGISTER_PATH, json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "terms_acceptance_required"
    assert "terms_version_accepted" in response.json()["errors"]


def test_provider_password_policy_is_reported_on_the_password_field(
    registration_client: TestClient,
    identity_provider: FakeIdentityProvider,
) -> None:
    identity_provider.error = IdentityPasswordRejectedError()

    response = registration_client.post(REGISTER_PATH, json=valid_payload())

    assert response.status_code == 422
    assert response.json()["code"] == "password_policy_violation"
    assert "password" in response.json()["errors"]


def test_transport_validation_uses_the_shared_problem_contract(
    registration_client: TestClient,
) -> None:
    payload = valid_payload(unexpected="value")
    del payload["phone"]

    response = registration_client.post(REGISTER_PATH, json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert "body.phone" in response.json()["errors"]
    assert "body.unexpected" in response.json()["errors"]


def test_registration_response_never_exposes_sensitive_values(
    registration_client: TestClient,
) -> None:
    payload = valid_payload()

    response = registration_client.post(REGISTER_PATH, json=payload)

    assert response.status_code == 201
    assert str(payload["cpf"]) not in response.text
    assert str(payload["password"]) not in response.text
    assert "identity_subject" not in response.text
    assert "password_hash" not in response.text
