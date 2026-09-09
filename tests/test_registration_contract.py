"""US-04-T03: the registration contract, as executable cases.

Every case here is marked `xfail` because `POST /api/v1/professionals` does not
exist yet: US-04-T01 is not merged. They run on every CI build and report as
expected failures, so they cost nothing today and start reporting `XPASS` the
moment the endpoint behaves as agreed. That is the signal to remove the marker.

The request shape, the stable error codes and the status for each failure are
the ones agreed with the frontend for this task. Each case is named after the
behaviour it pins down, so the file stands on its own.
"""

import os
from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_engine, get_session
from app.main import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1",
        reason="requires RUN_DATABASE_INTEGRATION_TESTS=1 and migrated PostgreSQL",
    ),
    pytest.mark.xfail(
        reason="US-04-T01 not merged: POST /api/v1/professionals does not exist",
    ),
]

REGISTER = "/api/v1/professionals"


def synthetic_cpf(base: str) -> str:
    """Complete a nine-digit base with valid check digits.

    Keeps the fixtures synthetic: the numbers are built here rather than copied
    from a real document, which the repository rules forbid.
    """
    digits = [int(digit) for digit in base]
    for first_weight in (10, 11):
        total = sum(
            digit * weight
            for digit, weight in zip(digits, range(first_weight, 1, -1), strict=False)
        )
        check_digit = (total * 10) % 11
        digits.append(0 if check_digit == 10 else check_digit)
    return "".join(str(digit) for digit in digits)


def eligible_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "full_name": "Maria Souza",
        "cpf": synthetic_cpf("111444777"),
        "birth_date": date(1970, 1, 1).isoformat(),
        "phone": "+5551999999999",
        "email": "maria@example.invalid",
        "password": "LocalDemoOnly!2026",
        "terms_version_accepted": "v1",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def session() -> Iterator[Session]:
    connection = get_engine().connect()
    transaction = connection.begin()
    test_session = Session(
        bind=connection,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )

    yield test_session

    test_session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    application = create_app()
    application.dependency_overrides[get_session] = lambda: session
    with TestClient(application, raise_server_exceptions=False) as test_client:
        yield test_client
    application.dependency_overrides.clear()


def test_an_eligible_professional_completes_registration(
    client: TestClient,
) -> None:
    response = client.post(REGISTER, json=eligible_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "maria@example.invalid"
    assert isinstance(body["id"], str)
    assert "email_verification_required" in body


def test_an_invalid_cpf_is_reported_on_the_cpf_field(client: TestClient) -> None:
    response = client.post(REGISTER, json=eligible_payload(cpf="11144477700"))

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_cpf"
    assert "cpf" in body["errors"]


def test_a_duplicate_cpf_is_reported_as_a_conflict(client: TestClient) -> None:
    client.post(REGISTER, json=eligible_payload())

    response = client.post(
        REGISTER, json=eligible_payload(email="outra@example.invalid")
    )

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "cpf_already_registered"
    assert "cpf" in body["errors"]


def test_a_duplicate_email_is_reported_as_a_conflict(client: TestClient) -> None:
    client.post(REGISTER, json=eligible_payload())

    response = client.post(
        REGISTER, json=eligible_payload(cpf=synthetic_cpf("222555888"))
    )

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "email_already_registered"
    assert "email" in body["errors"]


def test_an_applicant_under_45_is_refused(client: TestClient) -> None:
    response = client.post(
        REGISTER, json=eligible_payload(birth_date=date(2000, 1, 1).isoformat())
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "minimum_age_not_met"
    assert "birth_date" in body["errors"]


def test_a_missing_phone_never_reaches_the_database(client: TestClient) -> None:
    payload = eligible_payload()
    del payload["phone"]

    response = client.post(REGISTER, json=payload)

    assert response.status_code == 422


def test_registration_without_consent_is_refused(client: TestClient) -> None:
    payload = eligible_payload()
    del payload["terms_version_accepted"]

    response = client.post(REGISTER, json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "terms_acceptance_required"


def test_no_response_ever_carries_the_cpf_or_the_password(
    client: TestClient,
) -> None:
    payload = eligible_payload()
    created = client.post(REGISTER, json=payload)
    conflict = client.post(REGISTER, json=payload)

    # Asserted first on purpose: without them a 404 would satisfy the leak checks
    # below and the case would pass while proving nothing.
    assert created.status_code == 201
    assert conflict.status_code == 409

    for response in (created, conflict):
        body = response.text
        assert str(payload["cpf"]) not in body
        assert str(payload["password"]) not in body
        assert "password_hash" not in body
